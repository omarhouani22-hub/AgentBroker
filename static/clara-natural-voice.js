/* Optional billed provider is disabled server-side until explicitly configured. */
(function(root){
'use strict';
function init(doc,win,onChange){
 const audio=doc.getElementById('clara-natural-audio'),engine=doc.getElementById('clara-voice-engine'),status=doc.getElementById('natural-voice-status');
 let ready=false,internal=false,maxChars=2000,controller=null,url=null,urls=[],cachedText='',serial=0;
 let requestTimer=null,startTimer=null,endTimer=null;
 function clearTimer(kind){const id=kind==='request'?requestTimer:kind==='start'?startTimer:endTimer;if(id!==null&&win.clearTimeout)win.clearTimeout(id);if(kind==='request')requestTimer=null;else if(kind==='start')startTimer=null;else endTimer=null;}
 function stop(){serial++;clearTimer('request');clearTimer('start');clearTimer('end');if(controller)controller.abort();controller=null;audio.onplaying=null;audio.onended=null;audio.onerror=null;audio.pause();audio.currentTime=0;audio.hidden=true;}
 async function refresh(){
  if(win.ClaraInternalMic)await win.ClaraInternalMic.refresh();
  if(win.ClaraInternalMic&&win.ClaraInternalMic.enabled){
   const mic=doc.getElementById('companion-mic-language');if(mic)mic.value='en-US';
  }
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
  let awaitingPlay=false;
  function blocked(){if(active!==serial||!awaitingPlay)return;awaitingPlay=false;clearTimer('start');status.textContent='Tap Play below Clara to continue the call.';hooks.onblocked();}
  function failed(){if(active!==serial)return;stop();status.textContent='Speech did not finish. Tap Replay to try the saved reply.';hooks.onerror();}
  function startAudio(){
   awaitingPlay=true;clearTimer('start');
   if(win.setTimeout)startTimer=win.setTimeout(blocked,10000);
   try{Promise.resolve(audio.play()).catch(blocked);}catch(_){blocked();}
  }
  audio.onplaying=()=>{if(active===serial){awaitingPlay=false;clearTimer('start');clearTimer('end');status.textContent='Natural AI voice';hooks.onstart();
   const seconds=Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:text.length/10;
   if(win.setTimeout)endTimer=win.setTimeout(failed,Math.min(600000,Math.max(15000,(seconds+20)*1000)));
  }};
  let index=0;
  audio.onended=()=>{if(active===serial){clearTimer('end');if(++index<urls.length){audio.src=urls[index];startAudio();}else{audio.hidden=true;hooks.onend();}}};
  audio.onerror=failed;
  try{
   if(cachedText!==text||!url){
    controller=new win.AbortController();
    for(const old of urls)win.URL.revokeObjectURL(old);urls=[];url=null;cachedText='';
    const segments=[];for(let offset=0;offset<text.length;offset+=maxChars)segments.push(text.slice(offset,offset+maxChars));
    if(segments.length>5)throw new Error('Speech reply too long');
    for(const segment of segments){
     if(win.setTimeout)requestTimer=win.setTimeout(()=>{if(active===serial&&controller)controller.abort();},45000);
     const response=await win.fetch('/companion/speech',{method:'POST',headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},body:JSON.stringify({text:segment}),signal:controller.signal,cache:'no-store'});
     if(!response.ok)throw new Error('Natural speech unavailable');
     const blob=await response.blob();if(active!==serial)return;
     clearTimer('request');
     urls.push(win.URL.createObjectURL(blob));
    }
    url=urls[0];cachedText=text;
   }
   if(active!==serial)return;audio.src=url;
   startAudio();
  }catch(_){failed();}
 }
 return {refresh,stop,selected:()=>ready&&engine.value==='natural',play};
}
root.ClaraNaturalVoice={init};
})(window);
