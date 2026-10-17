/* Optional billed provider is disabled server-side until explicitly configured. */
(function(root){
'use strict';
function init(doc,win,onChange){
 const audio=doc.getElementById('clara-natural-audio'),engine=doc.getElementById('clara-voice-engine'),status=doc.getElementById('natural-voice-status');
 let ready=false,controller=null,url=null,cachedText='',serial=0;
 function stop(){serial++;if(controller)controller.abort();controller=null;audio.onplaying=null;audio.onended=null;audio.onerror=null;audio.pause();audio.currentTime=0;audio.hidden=true;}
 async function refresh(){
  try{const response=await win.fetch('/companion/speech/status',{cache:'no-store'});const data=await response.json();ready=response.ok&&data.available===true;}catch(_){ready=false;}
  engine.querySelector('option[value="natural"]').disabled=!ready;
  if(!ready)engine.value='device';
  status.textContent=ready?'Natural AI voice is connected. Selected replies are sent to OpenAI for speech generation; API charges apply.':'Natural voice is not connected. Device voices are active; API billing approval is required for the upgrade.';
 }
 engine.onchange=()=>{if(!ready)engine.value='device';stop();if(onChange)onChange();};
 async function play(text,hooks){
  if(!ready || engine.value!=='natural'){hooks.onerror();return;}
  stop();const active=serial;audio.hidden=false;
  status.textContent='Preparing natural AI speech…';
  audio.onplaying=()=>{if(active===serial){status.textContent='Natural AI voice';hooks.onstart();}};
  audio.onended=()=>{if(active===serial){audio.hidden=true;hooks.onend();}};
  audio.onerror=()=>{if(active===serial)hooks.onerror();};
  try{
   if(cachedText!==text||!url){
    controller=new win.AbortController();
    const response=await win.fetch('/companion/speech',{method:'POST',headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},body:JSON.stringify({text}),signal:controller.signal,cache:'no-store'});
    if(!response.ok)throw new Error('Natural speech unavailable');
    const blob=await response.blob();if(active!==serial)return;
    if(url)win.URL.revokeObjectURL(url);url=win.URL.createObjectURL(blob);cachedText=text;
   }
   if(active!==serial)return;audio.src=url;
   try{await audio.play();}catch(_){if(active===serial){status.textContent='Tap Play below to hear the natural voice. Replaying this audio does not request speech again.';hooks.onblocked();}}
  }catch(_){if(active===serial){audio.hidden=true;status.textContent='Natural voice unavailable. Device voice fallback; no paid retry.';hooks.onerror();}}
 }
 return {refresh,stop,selected:()=>ready&&engine.value==='natural',play};
}
root.ClaraNaturalVoice={init};
})(window);
