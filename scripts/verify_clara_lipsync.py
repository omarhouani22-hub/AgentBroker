"""Loopback synthetic preview only. Actual Chromium decoding, not device audibility."""
import argparse,json,statistics
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image,ImageChops
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8775');parser.add_argument('--output',default='/tmp/clara-lipsync');args=parser.parse_args()
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--autoplay-policy=document-user-activation-required'])
 context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2)
 context.request.post(args.url+'/session/login',data={'secret':'preview-only-avatar'})
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(args.url+'/clara/');page.wait_for_function("()=>document.getElementById('clara-call-stage').dataset.assetStatus==='ready'")
 page.wait_for_timeout(200)
 # Fix only scene geometry/sway for pixel comparison: native controls change stage height.
 height=page.locator('#clara-call-stage').bounding_box()['height']+120
 css='.call-stage{height:'+str(height)+'px!important}.call-stage .presence{flex-shrink:0}.clara-surface{animation:none!important}button:focus-visible{outline:none!important}.blinking .clara-surface::before{animation:none!important;opacity:1!important}'
 page.route('**/static/lipsync-visual-test.css',lambda r:r.fulfill(content_type='text/css',body=css))
 page.add_style_tag(url=args.url+'/static/lipsync-visual-test.css');page.evaluate('claraAvatar.clearBlink()')
 page.locator('#companion-avatar').screenshot(path=str(out/'closed.png'))
 page.locator('#companion-avatar').click()
 page.wait_for_function("()=>claraAvatar.mouthOpen>.08 && document.getElementById('clara-natural-audio').currentTime>.2")
 before=page.evaluate("({mode:document.getElementById('companion-avatar').dataset.mouthTiming,open:claraAvatar.mouthOpen,rms:claraAvatar.energy,context:claraAvatar.context.state,muted:document.getElementById('clara-natural-audio').muted,volume:document.getElementById('clara-natural-audio').volume})")
 page.locator('#companion-avatar').screenshot(path=str(out/'speaking.png'))
 page.evaluate("document.getElementById('clara-natural-audio').muted=true")
 page.wait_for_function('()=>claraAvatar.mouthOpen===0');page.locator('#companion-avatar').screenshot(path=str(out/'muted.png'))
 assert page.evaluate("document.getElementById('clara-natural-audio').paused") is False
 page.evaluate("document.getElementById('clara-natural-audio').muted=false")
 page.wait_for_function('()=>claraAvatar.mouthOpen>.04')
 levels=page.evaluate('''()=>new Promise(resolve=>{const values=[];const timer=setInterval(()=>{values.push(claraAvatar.mouthOpen||0);if(values.length===55){clearInterval(timer);resolve(values);}},34);})''')
 assert len({round(v,3) for v in levels})>10
 assert any(0<v<1 for v in levels)
 page.wait_for_function("()=>claraAvatar.state==='idle' && document.getElementById('clara-natural-audio').hidden",timeout=15000)
 assert page.evaluate('claraAvatar.mouthOpen')==0
 assert page.evaluate('claraAvatar.frame') is None
 page.locator('#companion-avatar').screenshot(path=str(out/'ended.png'))
 closed=Image.open(out/'closed.png').convert('RGB');speaking=Image.open(out/'speaking.png').convert('RGB');ended=Image.open(out/'ended.png').convert('RGB')
 diff=ImageChops.difference(closed,speaking);bbox=diff.getbbox();assert bbox is not None,'No visible mouth movement'
 # All changes must stay in the mouth patch, not eyes/head/body.
 assert bbox[1]>=int(closed.height*.14) and bbox[3]<=int(closed.height*.205),bbox
 assert ImageChops.difference(closed,ended).getbbox() is None,'Mouth did not close to neutral after playback'
 assert ImageChops.difference(closed,Image.open(out/'muted.png').convert('RGB')).getbbox() is None,'Muted mouth did not close visually'
 page.evaluate("document.getElementById('companion-avatar').classList.add('blinking')")
 page.locator('#companion-avatar').screenshot(path=str(out/'blink.png'))
 blink=ImageChops.difference(ended,Image.open(out/'blink.png').convert('RGB')).getbbox();assert blink is not None
 assert blink[3]<int(closed.height*.14),'Blink changed the mouth'
 page.evaluate("document.getElementById('companion-avatar').classList.remove('blinking');document.getElementById('clara-natural-audio').volume=.25")
 # Replay must preserve user volume and create no second source for the element.
 page.locator('#companion-play').click();page.wait_for_function('()=>claraAvatar.mouthOpen>.01')
 assert page.evaluate("document.getElementById('clara-natural-audio').volume")==.25
 page.locator('#companion-stop').click();assert page.evaluate('claraAvatar.mouthOpen')==0
 # Simulate a blocked first blob play, retaining native Play/Retry recovery.
 blocked=browser.new_context(viewport={'width':390,'height':844})
 blocked.request.post(args.url+'/session/login',data={'secret':'preview-only-avatar'})
 q=blocked.new_page();q.add_init_script('''const original=HTMLMediaElement.prototype.play;let once=false;HTMLMediaElement.prototype.play=function(){if(!once&&this.src.startsWith('blob:')){once=true;return Promise.reject(new DOMException('Synthetic blocked play','NotAllowedError'));}return original.call(this);};''')
 q.goto(args.url+'/clara/');q.wait_for_function("()=>document.getElementById('clara-call-stage').dataset.assetStatus==='ready'");q.wait_for_timeout(200)
 q.locator('#companion-avatar').click();q.wait_for_function("()=>document.getElementById('avatar-status').textContent.includes('Tap Play')")
 assert q.evaluate('claraAvatar.mouthOpen||0')==0
 q.locator('#companion-play').click();q.wait_for_function('()=>claraAvatar.mouthOpen>.03')
 q.locator('#companion-stop').click();assert q.evaluate('claraAvatar.mouthOpen')==0
 result={'browser':'Chromium '+browser.version,'viewport':'390x844 @2x','audible_media_path':before,'smoothed_level_samples':len(levels),'unique_rounded_levels':len({round(v,3) for v in levels}),'mouth_pixel_change_bounds':bbox,'blink_pixel_change_bounds':blink,'neutral_after_completion':True,'muted_closes_during_playback':True,'volume_preserved_on_replay':True,'stop_closes':True,'autoplay_blocked_closes_and_retry_recovers':True,'page_errors':errors,'speech_source':'existing prerecorded English Piper fixture, not a new provider call','physical_speaker_audibility_verified':False,'physical_iphone_safari_tested':False}
 assert not errors
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));browser.close()
