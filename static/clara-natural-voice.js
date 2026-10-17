/* Optional billed provider is disabled server-side until explicitly configured. */
(function(root){
'use strict';
function init(doc,win,onChange){
 const audio=doc.getElementById('clara-natural-audio'),engine=doc.getElementById('clara-voice-engine'),status=doc.getElementById('natural-voice-status');
 let ready=false,internal=false,maxChars=2000,controller=null,url=null,urls=[],cachedText='',serial=0;
 function stop(){serial++;if(controller)controller.abort();controller=null;audio.onplaying=null;audio.onended=null;audio.onerror=null;audio.pause();audio.currentTime=0;audio.hidden=true;}
 async function refresh(){
  try{const response=await win.fetch('/companion/speech/status',{cache:'no-store'});const data=await response.json();ready=response.ok&&data.available===true;internal=data.internal===true;maxChars=internal?Math.min(data.max_characters||800,800):2000;}catch(_){ready=false;}
  engine.querySelector('option[value="natural"]').disabled=!ready;
  if(!ready)engine.value='device';
  else if(internal)engine.value='natural';
  status.textContent=ready?(internal?'Internal Piper voice · English female · generated on AgentBroker, no external speech API.':'Natural AI voice is connected. Selected replies are sent to OpenAI for speech generation; API charges apply.'):'Internal voice is unavailable. Device voices remain available.';
 }
 engine.onchange=()=>{if(!ready)engine.value='device';stop();if(onChange)onChange();};
 async function play(text,hooks){
  if(!ready || engine.value!=='natural'){hooks.onerror();return;}
  stop();const active=serial;audio.hidden=false;
  status.textContent='Preparing natural AI speech…';
  audio.onplaying=()=>{if(active===serial){status.textContent='Natural AI voice';hooks.onstart();}};
  let index=0;
  audio.onended=()=>{if(active===serial){if(++index<urls.length){audio.src=urls[index];audio.play().catch(()=>{status.textContent='Tap Play to continue.';hooks.onblocked();});}else{audio.hidden=true;hooks.onend();}}};
  audio.onerror=()=>{if(active===serial)hooks.onerror();};
  try{
   if(cachedText!==text||!url){
    controller=new win.AbortController();
    for(const old of urls)win.URL.revokeObjectURL(old);urls=[];url=null;cachedText='';
    const segments=[];for(let offset=0;offset<text.length;offset+=maxChars)segments.push(text.slice(offset,offset+maxChars));
    if(segments.length>5)throw new Error('Speech reply too long');
    for(const segment of segments){
     const response=await win.fetch('/companion/speech',{method:'POST',headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},body:JSON.stringify({text:segment}),signal:controller.signal,cache:'no-store'});
     if(!response.ok)throw new Error('Natural speech unavailable');
     const blob=await response.blob();if(active!==serial)return;
     urls.push(win.URL.createObjectURL(blob));
    }
    url=urls[0];cachedText=text;
   }
   if(active!==serial)return;audio.src=url;
   try{await audio.play();}catch(_){if(active===serial){status.textContent='Tap Play below to hear the natural voice. Replaying this audio does not request speech again.';hooks.onblocked();}}
  }catch(_){if(active===serial){audio.hidden=true;status.textContent='Natural voice unavailable. Device voice fallback; no paid retry.';hooks.onerror();}}
 }
 return {refresh,stop,selected:()=>ready&&engine.value==='natural',play};
}
root.ClaraNaturalVoice={init};
})(window);
