/* Only known local scenes/outfits; user requests never become URLs or executable code. */
(function(root){
'use strict';
const scenes=['studio','kitchen','bedroom','beach'],outfits=['business','casual','summer','shorts'];
function normalize(text){return String(text||'').toLowerCase().replace(/[\u064b-\u065f\u0670\u0640]/g,'').replace(/[أإآ]/g,'ا').replace(/ة/g,'ه').replace(/ى/g,'ي').trim();}
function parseRequest(text){
 const t=normalize(text), result={};
 if(/\b(?:don't|do not|never)\b|لا (?:تغير|تبدل|تروح|تكون)|ما بدي/.test(t))return result;
 const command=/^(?:clara[, :]+)?(?:please\s+)?(?:let's\s+|let us\s+|can you\s+|could you\s+)?(?:change|switch|go|move|take|wear|put|be|act|show|turn|dress|make|set|stand|sit)\b/.test(t)
   ||/^(?:يا )?(?:كلارا[،,: ]*)?(?:خلينا|يلا|غيري|بدلي|روحي|انتقلي|البسي|لبسي|كوني|خليكي|حطي|خلي المشهد|وقفي|قومي|اقعدي|اجلسي)/.test(t)
   ||/^بدي (?:اياكي|اشوفك|تكوني|نروح|نغير|المشهد|الملابس|لبسك)/.test(t);
 const request=t.replace(/^(?:clara|كلارا)[،,: ]+/,'').replace(/^(?:please|can you|could you)\s+/,'').replace(/[.!?؟،,]+$/,'').trim();
 if(/^(?:come closer|move closer|come here|come to me|closer|zoom in)(?: to me| please)?$|^(?:قربي|تعالي اقرب|قربي شوي|اقربي|اقتربي|تعالي|تعالي لعندي|تعالي هون|قربي مني|تعالي شوي)$/.test(request))result.motion='approach';
 if(/^(?:step back|move back|go back|zoom out)(?: please)?$|^(?:ابعدي|ارجعي لورا|ارجعي شوي)$/.test(request))result.motion='step_back';
 if(!command && !Object.keys(result).length)return result;
 if(/\bstand up\b|\bstanding\b|وقفي|قومي/.test(t)){result.pose='standing';result.outfit='business';}
 if(/\bsit down\b|\bseated\b|اقعدي|اجلسي/.test(t))result.pose='seated';
 if(/\bkitchen\b|مطبخ/.test(t))result.scene='kitchen';
 else if(/\bbedroom\b|غرف[هت] النوم/.test(t))result.scene='bedroom';
 else if(/\bbeach\b|\bseaside\b|بحر|شاط[ئي]/.test(t))result.scene='beach';
 else if(/\bstudio\b|استوديو/.test(t))result.scene='studio';
 if(/\bshorts\b|\bsandals\b|شورت|صندل/.test(t))result.outfit='shorts';
 else if(/\bcasual\b|\bjeans\b|\bsweater\b|كاجوال|جينز|كنزه/.test(t))result.outfit='casual';
 else if(/\bsummer\b|\bdress\b|فستان|صيفي/.test(t))result.outfit='summer';
 else if(/\bbusiness\b|\bprofessional\b|\bformal\b|رسمي|ملابس العمل/.test(t))result.outfit='business';
 if(/\bfrisky\b|مشاكس[ه]?|غزل/.test(t))result.tone='frisky';
 else if(/\bplayful\b|مرح[ه]?|مزح/.test(t))result.tone='playful';
 else if(/\bfunny\b|فكاهي|مضحك/.test(t))result.tone='funny';
 else if(/\bserious\b|جدي[ه]?/.test(t))result.tone='serious';
 return result;
}
function init(doc,win){
 const get=id=>doc.getElementById(id), stage=get('clara-call-stage'),scene=get('clara-scene'),outfit=get('clara-outfit'),status=get('appearance-status'),framing=get('clara-framing'),pose=get('clara-pose');
 function read(key,allowed,fallback){try{const value=win.localStorage.getItem(key);return allowed.includes(value)?value:fallback;}catch(_){return fallback;}}
 scene.value=read('clara-scene',scenes,'studio');outfit.value=read('clara-outfit',outfits,'business');
 framing.value=read('clara-framing',['wide','medium','close'],'wide');pose.value=read('clara-pose',['seated','standing'],'seated');

 let generation=0,pending=Promise.resolve(true),committed=null;const loaded=new Map();
 function load(url){if(!win.Image)return Promise.resolve();if(!loaded.has(url)){
  const image=new win.Image();const job=new Promise((resolve,reject)=>{let done=false;const finish=ok=>{if(done)return;done=true;win.clearTimeout(timer);ok?resolve():reject(Error('Image unavailable'));};
   const timer=win.setTimeout(()=>finish(false),8000);image.onerror=()=>finish(false);if(!image.decode)image.onload=()=>finish(true);
   image.src=url;if(image.decode)image.decode().then(()=>finish(true),()=>finish(false));
  });loaded.set(url,job);job.catch(()=>{if(loaded.get(url)===job)loaded.delete(url);});
 }return loaded.get(url);}
 function commit(){
  if(!scenes.includes(scene.value))scene.value='studio';if(!outfits.includes(outfit.value))outfit.value='business';
  if(pose.value==='standing')outfit.value='business';
  if(!['wide','medium','close'].includes(framing.value))framing.value='wide';
  stage.dataset.scene=scene.value;stage.dataset.outfit=outfit.value;stage.dataset.framing=framing.value;stage.dataset.pose=pose.value;
  try{win.localStorage.setItem('clara-scene',scene.value);win.localStorage.setItem('clara-outfit',outfit.value);win.localStorage.setItem('clara-framing',framing.value);win.localStorage.setItem('clara-pose',pose.value);}catch(_){}
  status.textContent='Scene: '+scene.options[scene.selectedIndex].textContent+' · Outfit: '+outfit.options[outfit.selectedIndex].textContent+' · '+pose.value+' · '+framing.value+' view';
 }
 function apply(){
  if(!win.Image){commit();committed={scene:scene.value,outfit:outfit.value,framing:framing.value,pose:pose.value};return;}
  const active=++generation,next={scene:scene.value,outfit:outfit.value,framing:framing.value,pose:pose.value};
  const asset=next.pose==='standing'?'clara-standing-business.webp':'clara-outfit-'+(outfits.includes(next.outfit)?next.outfit:'business')+'.webp';
  stage.dataset.assetStatus='loading';
  pending=Promise.all([load('/static/'+asset),load('/static/clara-scene-atlas.webp')]).then(()=>{
   if(active!==generation)return false;Object.assign(scene,{value:next.scene});outfit.value=next.outfit;framing.value=next.framing;pose.value=next.pose;
   commit();committed={scene:scene.value,outfit:outfit.value,framing:framing.value,pose:pose.value};stage.dataset.assetStatus='ready';return true;
  }).catch(()=>{if(active!==generation)return false;if(committed){scene.value=committed.scene;outfit.value=committed.outfit;framing.value=committed.framing;pose.value=committed.pose;}
   stage.dataset.assetStatus='error';status.textContent='Appearance image unavailable; kept the last loaded view. Try another preset.';return false;});
 }
 function advance(){apply();} // Compatibility: ordinary conversation never changes appearance.

 scene.onchange=apply;outfit.onchange=()=>{if(outfit.value!=='business')pose.value='seated';apply();};framing.onchange=apply;pose.onchange=apply;apply();
 return {advance,ready:()=>pending,value:()=>({scene:scene.value,outfit:outfit.value,framing:framing.value,pose:pose.value}),request(text){const change=parseRequest(text);if(change.scene)scene.value=change.scene;if(change.outfit){outfit.value=change.outfit;if(change.outfit!=='business')pose.value='seated';}if(change.pose)pose.value=change.pose;if(change.motion==='approach')framing.value='close';if(change.motion==='step_back')framing.value='wide';if(change.tone)get('companion-tone').value=change.tone;if(change.scene||change.outfit||change.framing||change.pose||change.motion)apply();return change;}};
}
const api={parseRequest,init};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ClaraAppearance=api;
})(typeof window!=='undefined'?window:globalThis);
