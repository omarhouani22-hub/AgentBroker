/* One deterministic state owner; no character swapping or phoneme-sync claim. */
(function(root){
'use strict';
const transitions={idle:['listening','thinking','speaking','error'],listening:['idle','thinking','speaking','error'],thinking:['idle','speaking','error'],speaking:['idle','thinking','error'],error:['idle','listening','thinking','speaking']};
class ClaraAvatarEngine{
 constructor(elementId='claraAvatar',doc=root.document,win=root){
  this.avatar=doc.getElementById(elementId);if(!this.avatar)throw Error('Clara avatar element not found');
  this.doc=doc;this.win=win;this.state='idle';this.destroyed=false;this.blinkTimer=null;this.blinkEndTimer=null;this.frame=null;this.cycle=0;
  this.reduced=win.matchMedia?win.matchMedia('(prefers-reduced-motion: reduce)'):null;
  this.onVisibility=()=>{if(doc.hidden)this.setState('idle');if(this.reduced?.matches)this.stopMeter();else if(this.state==='speaking')this.meter();this.scheduleBlink();};
  this.onPageHide=()=>{this.clearBlink();this.setState('idle');};this.onPageShow=()=>{this.setState('idle');this.scheduleBlink();};
  doc.addEventListener('visibilitychange',this.onVisibility);win.addEventListener('pagehide',this.onPageHide);win.addEventListener('pageshow',this.onPageShow);
  this.reduced?.addEventListener?.('change',this.onVisibility);this.avatar.dataset.state='idle';this.scheduleBlink();
 }
 clearBlink(){this.win.clearTimeout(this.blinkTimer);this.win.clearTimeout(this.blinkEndTimer);this.blinkTimer=this.blinkEndTimer=null;this.avatar.classList.remove('blinking');}
 scheduleBlink(){this.clearBlink();if(this.destroyed||this.doc.hidden||this.reduced?.matches)return;
  const delays=[3900,5100,4400,6200];this.blinkTimer=this.win.setTimeout(()=>{this.blinkTimer=null;if(this.destroyed||this.doc.hidden)return;
   this.avatar.classList.add('blinking');this.blinkEndTimer=this.win.setTimeout(()=>{this.avatar.classList.remove('blinking');this.scheduleBlink();},170);
  },delays[this.cycle++%delays.length]);
 }
 closeMouth(){this.mouthOpen=0;this.energy=0;this.referencePeak=0;this.avatar.style?.setProperty('--clara-mouth-open','0');}
 suppressMouth(){this.stopMeter();this.avatar.dataset.mouthSuppressed='true';}
 bindAudio(audio){
  if(this.audio===audio)return;
  if(this.audio)throw Error('One media element per avatar');
  this.audio=audio;this.mediaActive=Boolean(audio.src&&!audio.src.startsWith('data:')&&!audio.paused&&!audio.ended);
  const start=()=>{if(audio.src?.startsWith('data:'))return;this.mediaActive=true;if(this.state==='speaking')this.meter();};
  const close=()=>{if(this.mediaActive){this.mediaActive=false;this.suppressMouth();}};
  const volume=()=>{if(!this.mediaActive)return;if(audio.muted||audio.volume===0)this.suppressMouth();else if(this.state==='speaking')this.meter();};
  this.audioListeners=[['playing',start],['pause',close],['ended',close],['error',close],['abort',close],['emptied',close],['waiting',close],['stalled',close],['volumechange',volume]];
  for(const [name,handler] of this.audioListeners)audio.addEventListener?.(name,handler);
 }
 unlockAudio(audio){
  if(!audio||this.destroyed)return;
  try{
   this.bindAudio(audio);
   if(!this.context){const Context=this.win.AudioContext||this.win.webkitAudioContext;if(!Context)return;
    const context=new Context(),analyser=context.createAnalyser(),silent=context.createGain();
    analyser.fftSize=512;silent.gain.value=0;analyser.connect(silent);silent.connect(context.destination);
    const source=context.createMediaElementSource(audio);
    // Keep an independent audible path. Analysis never changes playback volume.
    source.connect(context.destination);this.context=context;this.source=source;
    try{source.connect(analyser);this.analyser=analyser;this.samples=new Float32Array(analyser.fftSize);this.bytes=new Uint8Array(analyser.fftSize);}catch(_){/* Direct sound path stays intact if only analysis fails. */}
    this.onContextState=()=>{if(this.state!=='speaking'||!this.mediaActive)return;if(context.state==='running')this.meter();else this.suppressMouth();};
    context.addEventListener?.('statechange',this.onContextState);
   }
   // Called synchronously from the user's tap, before awaiting a network reply.
   Promise.resolve(this.context.resume()).then(()=>{if(!this.destroyed&&this.state==='speaking'&&this.mediaActive)this.meter();}).catch(()=>this.suppressMouth());
  }catch(_){/* Existing playback/Play retry remains available; no provider switch. */}
 }
 stopMeter(){this.meterSerial=(this.meterSerial||0)+1;if(this.frame!==null)this.win.cancelAnimationFrame?.(this.frame);this.frame=null;this.closeMouth();}
 meter(){
  this.stopMeter();const energy=Boolean(this.analyser&&this.mediaActive);
  this.avatar.dataset.mouthTiming=energy?'energy':'approximate';this.avatar.dataset.mouthSuppressed='false';
  if(this.reduced?.matches||this.doc.hidden)return;
  if(this.mediaActive&&(this.audio.muted||this.audio.volume===0||this.audio.paused||this.audio.ended||this.audio.readyState<2||(energy&&this.context?.state!=='running'))){this.suppressMouth();return;}
  if(!energy)return;
  const active=this.meterSerial;let last=null;const sample=now=>{
   if(active!==this.meterSerial||this.destroyed||this.state!=='speaking'||this.doc.hidden||!this.mediaActive)return;
   if(this.audio.muted||this.audio.volume===0||this.audio.paused||this.audio.ended||this.context.state!=='running'){this.suppressMouth();return;}
   if(last===null||now-last>=30){
    const dt=last===null?33:Math.min(100,now-last);last=now;
    if(this.analyser.getFloatTimeDomainData)this.analyser.getFloatTimeDomainData(this.samples);
    else{this.analyser.getByteTimeDomainData(this.bytes);for(let i=0;i<this.bytes.length;i++)this.samples[i]=(this.bytes[i]-128)/128;}
    let sum=0,mean=0;for(const v of this.samples){sum+=v*v;mean+=v;}mean/=this.samples.length;
    this.energy=Math.sqrt(Math.max(0,sum/this.samples.length-mean*mean));
    // Normalize to recent speech peaks so quiet replies still move the mouth.
    // This affects animation only; playback gain/volume is never changed.
    this.referencePeak=Math.max(.02,this.energy,(this.referencePeak||0)*Math.exp(-dt/1200));
    const target=Math.min(1,Math.max(0,(this.energy-.001)/(this.referencePeak-.001)))*.95;
    const coefficient=1-Math.exp(-dt/(target>(this.mouthOpen||0)?40:90));
    this.mouthOpen=(this.mouthOpen||0)+(target-(this.mouthOpen||0))*coefficient;
    if(this.mouthOpen<.005)this.mouthOpen=0;
    this.avatar.style?.setProperty('--clara-mouth-open',this.mouthOpen.toFixed(4));
   }
   this.frame=this.win.requestAnimationFrame(sample);
  };this.frame=this.win.requestAnimationFrame(sample);
 }

 setState(value){if(!transitions[value]||(this.destroyed&&value!=='idle')||(value!==this.state&&!transitions[this.state].includes(value)))return false;
  this.stopMeter();this.state=value;this.avatar.dataset.state=value;if(value==='speaking')this.meter();return true;
 }
 startSpeaking(){this.setState('speaking');}stopSpeaking(){this.setState('idle');}startListening(){this.setState('listening');}startThinking(){this.setState('thinking');}
 destroy(){this.destroyed=true;this.clearBlink();this.stopMeter();this.doc.removeEventListener('visibilitychange',this.onVisibility);this.win.removeEventListener('pagehide',this.onPageHide);this.win.removeEventListener('pageshow',this.onPageShow);this.reduced?.removeEventListener?.('change',this.onVisibility);this.setState('idle');for(const [name,handler] of this.audioListeners||[])this.audio?.removeEventListener?.(name,handler);this.context?.removeEventListener?.('statechange',this.onContextState);if(this.context)Promise.resolve(this.context.close()).catch(()=>{});}
}
if(typeof module!=='undefined'&&module.exports)module.exports={ClaraAvatarEngine};else{
 root.ClaraAvatarEngine=ClaraAvatarEngine;root.claraAvatar=new ClaraAvatarEngine('companion-avatar');
 root.onClaraSpeechStart=()=>root.claraAvatar.startSpeaking();root.onClaraSpeechEnd=()=>root.claraAvatar.stopSpeaking();
}
})(typeof window!=='undefined'?window:globalThis);
