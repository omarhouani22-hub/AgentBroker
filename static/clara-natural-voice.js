/* Same-origin speech playback. No billing or provider settings are chosen here. */
(function(root){
'use strict';
function init(doc,win,onChange){
 const audio=doc.getElementById('clara-natural-audio'),engine=doc.getElementById('clara-voice-engine'),status=doc.getElementById('natural-voice-status');
 let ready=false,internal=false,maxChars=2000,controller=null,urls=[],cachedText='',serial=0,retryPlay=null;
 let requestTimer=null,startTimer=null,endTimer=null;
 function clearTimer(kind){const id=kind==='request'?requestTimer:kind==='start'?startTimer:endTimer;if(id!==null&&win.clearTimeout)win.clearTimeout(id);if(kind==='request')requestTimer=null;else if(kind==='start')startTimer=null;else endTimer=null;}
 function stop(){
  serial++;retryPlay=null;clearTimer('request');clearTimer('start');clearTimer('end');
  if(controller)controller.abort();controller=null;
  for(const name of ['onplaying','onended','onerror','onpause','onwaiting','onstalled','ontimeupdate','onloadedmetadata'])audio[name]=null;
  audio.pause();audio.currentTime=0;audio.hidden=true;
 }
 function unlock(){
  // Called synchronously on a tap, before any fetch/await. Reuse this element
  // for the real reply; Safari can still require Play, which remains available.
  if(win.claraAvatar?.unlockAudio)win.claraAvatar.unlockAudio(audio);
  if(audio.onplaying)return;
  const active=serial;
  const bytes=new Uint8Array(204),view=new DataView(bytes.buffer);
  const word=(at,text)=>{for(let i=0;i<text.length;i++)bytes[at+i]=text.charCodeAt(i);};
  word(0,'RIFF');view.setUint32(4,196,true);word(8,'WAVE');word(12,'fmt ');view.setUint32(16,16,true);
  view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,8000,true);view.setUint32(28,16000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);word(36,'data');view.setUint32(40,160,true);
  if(!win.btoa)return;
  const source='data:audio/wav;base64,'+win.btoa(String.fromCharCode(...bytes));
  audio.src=source;
  try{Promise.resolve(audio.play()).then(()=>{if(active===serial&&audio.src===source)audio.pause();}).catch(()=>{});}catch(_){}
 }
 async function refresh(){
  if(win.ClaraInternalMic)await win.ClaraInternalMic.refresh();
  if(win.ClaraInternalMic&&win.ClaraInternalMic.enabled){const mic=doc.getElementById('companion-mic-language');if(mic)mic.value='en-US';}
  try{const response=await win.fetch('/companion/speech/status',{cache:'no-store'});const data=await response.json();ready=response.ok&&data.available===true;internal=data.internal===true;maxChars=internal?Math.min(data.max_characters||800,800):2000;}catch(_){ready=false;}
  engine.querySelector('option[value="natural"]').disabled=!ready;
  if(!ready)engine.value='device';else if(internal)engine.value='natural';
  status.textContent=ready?(internal?'Internal Piper voice · English female · no external speech API.':'Natural AI voice is connected. Selected replies are sent to OpenAI for speech generation; API charges apply.'):'Internal voice is unavailable. Device voices remain available.';
 }
 engine.onchange=()=>{if(!ready)engine.value='device';stop();if(onChange)onChange();};
 async function validatedBlob(response){
  if(!response.ok)throw new Error('Speech unavailable');
  const blob=await response.blob();
  const type=blob.type.toLowerCase().split(';')[0];
  if(!['audio/wav','audio/x-wav','audio/mpeg'].includes(type)||!blob.size||blob.size>4000000)throw new Error('Invalid speech media');
  const bytes=new Uint8Array(await blob.arrayBuffer());
  const tag=(at,n)=>String.fromCharCode(...bytes.slice(at,at+n));
  if(type!=='audio/mpeg'){
   if(bytes.length<=44||tag(0,4)!=='RIFF'||tag(8,4)!=='WAVE')throw new Error('Invalid WAV');
   const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let format=false,samples=false;
   if(view.getUint32(4,true)+8>bytes.length)throw new Error('Truncated WAV');
   for(let offset=12;offset+8<=bytes.length;){const length=view.getUint32(offset+4,true),end=offset+8+length;if(end>bytes.length)throw new Error('Truncated WAV chunk');
    if(tag(offset,4)==='fmt '){if(length<16||![1,3].includes(view.getUint16(offset+8,true))||view.getUint16(offset+10,true)<1||view.getUint32(offset+12,true)<8000)throw new Error('Invalid WAV format');format=true;}
    if(tag(offset,4)==='data')samples=length>0;offset=end+(length%2);
   }
   if(!format||!samples)throw new Error('Empty WAV samples');
  }else if(bytes.length<10||!(tag(0,3)==='ID3'||(bytes[0]===255&&(bytes[1]&224)===224)))throw new Error('Invalid MP3');
  return blob;
 }
 async function play(text,hooks){
  const emit=(name)=>{if(typeof hooks[name]==='function')hooks[name]();};
  if(!ready||engine.value!=='natural'){emit('onerror');return;}
  stop();const active=serial;audio.hidden=false;
  status.textContent='Preparing speech…';
  let awaitingPlay=false,index=0,waiting=false,complete=false,lastTime=0;
  const currentMedia=()=>active===serial&&index<urls.length&&audio.src===urls[index];
  function blocked(){if(active!==serial||!awaitingPlay)return;awaitingPlay=false;clearTimer('start');clearTimer('end');status.textContent='Tap Play / Retry audio below Clara.';emit('onblocked');}
  function failed(){if(active!==serial)return;stop();cachedText='';status.textContent='Speech did not finish. Tap Play / Retry audio.';emit('onerror');}
  function watchProgress(){clearTimer('end');if(win.setTimeout)endTimer=win.setTimeout(failed,15000);}
  function startAudio(){
   if(active!==serial)return;
   awaitingPlay=true;clearTimer('start');
   if(win.setTimeout)startTimer=win.setTimeout(blocked,10000);
   try{Promise.resolve(audio.play()).catch(error=>{if(error&&error.name==='NotSupportedError')failed();else blocked();});}catch(_){blocked();}
  }
  retryPlay=startAudio;
  audio.onplaying=()=>{if(!currentMedia())return;const context=win.claraAvatar?.context;if(context?.state==='closed'){failed();return;}if(context&&context.state!=='running'){audio.pause();blocked();return;}awaitingPlay=false;clearTimer('start');lastTime=audio.currentTime;status.textContent='Playing speech';emit('onstart');watchProgress();};
  audio.ontimeupdate=()=>{if(currentMedia()&&!audio.paused&&audio.currentTime>lastTime){lastTime=audio.currentTime;watchProgress();}};
  audio.onpause=()=>{if(!currentMedia()||audio.ended)return;clearTimer('end');emit('onpause');status.textContent='Audio paused. Tap Play / Retry audio.';};
  audio.onwaiting=audio.onstalled=()=>{if(!currentMedia())return;emit('onpause');status.textContent='Waiting for audio…';watchProgress();};
  audio.onloadedmetadata=()=>{if(currentMedia()&&Number.isFinite(audio.duration)&&audio.duration<=0)failed();};
  function nextAudio(){
   if(active!==serial)return;
   if(index<urls.length){waiting=false;audio.src=urls[index];lastTime=0;startAudio();}
   else if(complete){waiting=false;stop();emit('onend');}
   else{waiting=true;emit('onpause');status.textContent='Preparing the next speech segment…';}
  }
  audio.onended=()=>{if(!currentMedia())return;clearTimer('start');clearTimer('end');emit('onpause');index++;nextAudio();};
  audio.onerror=()=>{if(currentMedia())failed();};
  try{
   if(cachedText!==text||!urls.length){
    controller=new win.AbortController();const requestController=controller;
    for(const old of urls)win.URL.revokeObjectURL(old);urls=[];cachedText='';
    const segments=[];for(let offset=0;offset<text.length;offset+=maxChars)segments.push(text.slice(offset,offset+maxChars));
    if(!segments.length||segments.length>5)throw new Error('Invalid speech length');
    for(const segment of segments){
     if(active!==serial)return;
     if(win.setTimeout)requestTimer=win.setTimeout(()=>{if(active===serial)requestController.abort();},45000);
     let response;
     for(let attempt=0;attempt<9;attempt++){
      response=await win.fetch('/companion/speech',{method:'POST',headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},body:JSON.stringify({text:segment}),signal:requestController.signal,cache:'no-store'});
      if(active!==serial)return;
      if(response.status!==409||attempt===8)break;
      status.textContent='Clara is busy; waiting for the voice…';
      await new Promise((resolve,reject)=>{
       const timer=win.setTimeout(()=>{requestController.signal.removeEventListener('abort',abort);resolve();},2000);
       const abort=()=>{win.clearTimeout(timer);reject(new Error('cancelled'));};
       requestController.signal.addEventListener('abort',abort,{once:true});if(requestController.signal.aborted)abort();
      });
     }
     const blob=await validatedBlob(response);if(active!==serial)return;clearTimer('request');
     urls.push(win.URL.createObjectURL(blob));
     if(urls.length===1||waiting)nextAudio();
    }
    cachedText=text;complete=true;if(waiting)nextAudio();return;
   }
   complete=true;nextAudio();
  }catch(_){failed();}
 }
 return {refresh,stop,unlock,retry(){if(!retryPlay)return false;retryPlay();return true;},selected:()=>ready&&engine.value==='natural',play};
}
root.ClaraNaturalVoice={init};
})(window);
