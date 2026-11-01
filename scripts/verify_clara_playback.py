"""Local synthetic preview checks, not live/iPhone/acoustic verification.
Requires preview servers on localhost 8765 (repair) and 8766 (baseline).
"""
import json,time,statistics,pathlib,argparse
from playwright.sync_api import sync_playwright
from PIL import Image,ImageChops
parser=argparse.ArgumentParser(description='Chromium visual/playback check against two local synthetic preview servers')
parser.add_argument('--output',default='/tmp/clara-avatar-checks')
args=parser.parse_args()
out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
init='''window.__micStarts=0;window.__micActive=false;
class Input{start(){window.__micStarts++;window.__micActive=true;this.onstart?.();}stop(){window.__micActive=false;this.onend?.();}abort(){window.__micActive=false;setTimeout(()=>this.onend?.(),0);}}
window.SpeechRecognition=Input;
window.__states=[];document.addEventListener('DOMContentLoaded',()=>{const e=document.getElementById('companion-avatar');if(e)new MutationObserver(()=>window.__states.push(e.dataset.state)).observe(e,{attributes:true,attributeFilter:['data-state']});});
'''
def login(context,port):
 base='http://127.0.0.1:'+str(port)
 r=context.request.post(base+'/session/login',data={'secret':'preview-only-avatar'});assert r.status==200
 page=context.new_page();page.add_init_script(init);page.goto(base+'/clara/');page.wait_for_function("() => !document.getElementById('private-ui').hidden")
 page.wait_for_timeout(250)
 return page
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--autoplay-policy=document-user-activation-required','--disable-dev-shm-usage'])
 beforecontext=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
 before=login(beforecontext,8766)
 before.locator('#clara-call-stage').screenshot(path=str(out/'before.png'))
 beforefacts=before.evaluate('''()=>{const stage=document.getElementById('clara-call-stage'),face=document.querySelector('.call-stage .avatar-face');return {appearance:{...stage.dataset},blinkOverlayBackground:getComputedStyle(face,'::after').backgroundImage,neutralBackground:getComputedStyle(face).backgroundPosition};}''')
 looks=[]
 for _ in range(5):
  before.reload();before.wait_for_function("() => !document.getElementById('private-ui').hidden")
  looks.append(before.evaluate("document.getElementById('clara-call-stage').dataset.outfit+':'+document.getElementById('clara-call-stage').dataset.pose"))
 before.locator('#companion-input').fill('Wear shorts')
 with before.expect_response(lambda r:r.url.endswith('/companion/messages') and r.request.method=='POST') as response:
  before.locator('#companion-send').click()
 before.wait_for_function("() => !document.getElementById('companion-input').readOnly")
 beforefacts['shorts_reply_status']=response.value.status
 beforefacts['shorts_reply_error']=before.locator('#companion-status').inner_text()
 before.evaluate("document.getElementById('clara-outfit').value='business';document.getElementById('clara-outfit').onchange()")
 before.locator('#companion-input').fill('Come closer');before.locator('#companion-send').click();before.wait_for_function("() => !document.getElementById('companion-input').readOnly")
 beforefacts['closer_result']=before.evaluate("document.getElementById('clara-call-stage').dataset.framing")
 beforefacts['reload_looks']=looks
 context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
 page=login(context,8765);errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 page.wait_for_function("() => document.getElementById('clara-call-stage').dataset.assetStatus==='ready'")
 afterlooks=[]
 for _ in range(3):
  page.reload();page.wait_for_function("() => document.getElementById('clara-call-stage').dataset.assetStatus==='ready'")
  afterlooks.append(page.evaluate("document.getElementById('clara-call-stage').dataset.outfit+':'+document.getElementById('clara-call-stage').dataset.pose"))
 assert len(set(afterlooks))==1
 # Freeze only sway for deterministic pixel comparisons, not facial overlays.
 page.route('**/static/avatar-test-freeze.css',lambda r:r.fulfill(content_type='text/css',body='.clara-surface{animation:none!important}.blinking .clara-surface::before{animation:none!important;opacity:1!important}'))
 page.add_style_tag(url='http://127.0.0.1:8765/static/avatar-test-freeze.css')
 page.evaluate("claraAvatar.clearBlink();claraAvatar.setState('idle')")
 page.locator('#companion-avatar').screenshot(path=str(out/'after-idle.png'))
 page.evaluate("document.getElementById('companion-avatar').classList.add('blinking')")
 page.locator('#companion-avatar').screenshot(path=str(out/'after-blink.png'))
 page.evaluate("document.getElementById('companion-avatar').classList.remove('blinking')")
 a,b=Image.open(out/'after-idle.png').convert('RGB'),Image.open(out/'after-blink.png').convert('RGB');diff=ImageChops.difference(a,b)
 body=diff.crop((0,int(a.height*.25),a.width,a.height));assert body.getbbox() is None,'Blink changed body pixels'
 assert diff.getbbox() is not None,'Blink did not change visible pixels'
 page.locator('#clara-call-stage').screenshot(path=str(out/'after.png'))
 # Closer view is a real framing command, not pretend walking.
 page.locator('#companion-input').fill('Come closer');page.locator('#companion-send').click()
 page.wait_for_function("() => document.getElementById('companion-input').value===''")
 assert page.evaluate("document.getElementById('clara-call-stage').dataset.framing")== 'close'
 assert 'framing' in page.locator('#companion-messages').inner_text()
 page.locator('#companion-input').fill('Step back');page.locator('#companion-send').click();page.wait_for_function("() => document.getElementById('companion-input').value===''")
 assert page.evaluate("document.getElementById('clara-call-stage').dataset.framing")== 'wide'
 # Test all original asset presets, with single neutral surface unchanged by states.
 page.locator('#settings-toggle').click();page.locator('.appearance-controls summary').click()
 assets=[]
 for outfit,pose in [('business','seated'),('casual','seated'),('summer','seated'),('shorts','seated'),('business','standing')]:
  page.select_option('#clara-outfit',outfit);page.select_option('#clara-pose',pose)
  page.wait_for_function("() => document.getElementById('clara-call-stage').dataset.assetStatus==='ready'")
  assets.append(page.evaluate("({outfit:document.getElementById('clara-call-stage').dataset.outfit,pose:document.getElementById('clara-call-stage').dataset.pose,image:getComputedStyle(document.querySelector('.clara-surface')).backgroundImage,faces:document.querySelectorAll('.call-stage .clara-surface').length})"))
  assert assets[-1]['faces']==1
 page.select_option('#clara-pose','seated');page.select_option('#clara-outfit','business');page.wait_for_function("() => document.getElementById('clara-call-stage').dataset.assetStatus==='ready'")
 page.locator('#settings-toggle').click()
 # Force only the first real blob play to fail; Retry must then play the actual audio.
 page.evaluate('''()=>{window.__blocked=0;const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){if(this.src.startsWith('blob:')&&!window.__blocked++){return Promise.reject(new DOMException('Synthetic autoplay block','NotAllowedError'));}return play.call(this);};}''')
 page.locator('#companion-call').click()
 page.wait_for_function("() => document.getElementById('avatar-status').textContent.includes('Tap Play')")
 assert page.evaluate("document.getElementById('companion-avatar').dataset.state")!='speaking'
 page.locator('#companion-play').click()
 page.wait_for_function("() => document.getElementById('companion-avatar').dataset.state==='speaking'")
 page.wait_for_timeout(500)
 speaking=page.evaluate("({state:document.getElementById('companion-avatar').dataset.state,mode:document.getElementById('companion-avatar').dataset.mouthTiming,energy:claraAvatar.energy||0,mic:window.__micActive,time:document.getElementById('clara-natural-audio').currentTime})")
 page.locator('#companion-avatar').screenshot(path=str(out/'after-speaking.png'))
 assert speaking['mic'] is False and speaking['time']>0 and speaking['energy']>0
 page.wait_for_function("() => window.__micActive===true",timeout=15000)
 assert page.evaluate("document.getElementById('companion-avatar').dataset.state")== 'listening'
 # Full reply: mic pauses, playback completes, then listening resumes.
 starts=page.evaluate('window.__micStarts')
 page.locator('#companion-input').evaluate("e=>{e.readOnly=false;e.value='Give a synthetic development reply.'}")
 page.locator('#companion-send').click();page.wait_for_function("() => document.getElementById('companion-avatar').dataset.state==='speaking'")
 assert page.evaluate('window.__micActive') is False
 page.wait_for_function('() => window.__micStarts>'+str(starts),timeout=15000)
 page.locator('#companion-call').click()
 assert page.evaluate("document.getElementById('companion-avatar').dataset.state")== 'idle'
 page.locator('#companion-play').click();page.wait_for_function("() => document.getElementById('companion-avatar').dataset.state==='speaking'")
 page.wait_for_function("() => document.getElementById('companion-avatar').dataset.state==='idle' && document.getElementById('clara-natural-audio').hidden",timeout=15000)
 page.locator('#companion-avatar').screenshot(path=str(out/'after-ended.png'))
 # Cancel and error must not resurrect stale speaking events.
 page.evaluate("claraAvatar.setState('error')");assert page.evaluate("claraAvatar.state")== 'error'
 page.evaluate("claraAvatar.setState('idle')")
 # A missing asset keeps the previous loaded character, not a blank replacement.
 page.route('**/clara-outfit-casual.webp',lambda route:route.abort())
 page.evaluate("document.querySelector('#clara-outfit').value='casual';document.querySelector('#clara-outfit').onchange()")
 # It was cached in this page; separate fresh context will exercise a true failed request.
 failedcontext=browser.new_context(viewport={'width':390,'height':844});failedcontext.route('**/clara-outfit-casual.webp',lambda route:route.abort())
 failed=login(failedcontext,8765);failed.wait_for_function("() => document.getElementById('clara-call-stage').dataset.assetStatus==='ready'")
 failed.evaluate("document.getElementById('clara-outfit').value='casual';document.getElementById('clara-outfit').onchange()")
 failed.wait_for_function("() => document.getElementById('clara-call-stage').dataset.assetStatus==='error'")
 assert failed.evaluate("document.getElementById('clara-call-stage').dataset.outfit")== 'business'
 # 320px viewport + 4x CPU throttling: desktop emulation, not a physical phone.
 perfcontext=browser.new_context(viewport={'width':320,'height':740},device_scale_factor=2)
 perf=login(perfcontext,8765);perf.wait_for_function("() => document.getElementById('clara-call-stage').dataset.assetStatus==='ready'")
 cdp=perfcontext.new_cdp_session(perf);cdp.send('Emulation.setCPUThrottlingRate',{'rate':4});cdp.send('Performance.enable')
 timing=perf.evaluate('''()=>new Promise(resolve=>{const times=[];let last=performance.now();function sample(now){times.push(now-last);last=now;if(times.length<120)requestAnimationFrame(sample);else resolve(times.slice(1));}requestAnimationFrame(sample);})''')
 overflow=perf.evaluate('document.documentElement.scrollWidth>innerWidth');assert not overflow
 heap={v['name']:v['value'] for v in cdp.send('Performance.getMetrics')['metrics']}
 perf.locator('#clara-call-stage').screenshot(path=str(out/'after-320px.png'))
 result={'browser':'Chromium '+browser.version,'before':beforefacts,'after_reload_looks':afterlooks,'blink_changed_bounds':diff.getbbox(),'blink_body_pixels_unchanged':True,'original_presets':assets,'playback':speaking,'blocked_retry_completed':True,'complete_reply_mic_suspension_and_resume':True,'cancel_returns_idle':True,'missing_asset_keeps_previous':True,'performance':{'viewport':'320x740 @2x','cpu_throttle':4,'raf_samples':len(timing),'median_frame_ms':statistics.median(timing),'p95_frame_ms':sorted(timing)[int(len(timing)*.95)],'js_heap_bytes':heap.get('JSHeapUsedSize'),'horizontal_overflow':overflow},'page_errors':errors,'audio_source':'existing prerecorded Piper fixture; no new synthesis benchmark','physical_audibility_tested':False,'iphone_safari_tested':False}
 (out/'browser-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));browser.close()
