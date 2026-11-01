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
 unlockAudio(audio){
  if(!audio||this.destroyed)return;
  try{
   if(!this.context){const Context=this.win.AudioContext||this.win.webkitAudioContext;if(!Context)return;
    const context=new Context(),analyser=context.createAnalyser();analyser.fftSize=256;
    analyser.connect(context.destination);const source=context.createMediaElementSource(audio);source.connect(analyser);
    this.context=context;this.analyser=analyser;this.samples=new Float32Array(256);this.audio=audio;
   }
   this.context.resume().catch(()=>{});
  }catch(_){/* Keep native playback and event-only approximate animation available. */}
 }
 stopMeter(){if(this.frame!==null)this.win.cancelAnimationFrame?.(this.frame);this.frame=null;this.avatar.style?.setProperty('--clara-mouth-open','0');}
 meter(){this.stopMeter();const energy=this.analyser&&this.audio&&!this.audio.paused&&this.context?.state==='running';
  this.avatar.dataset.mouthTiming=energy?'energy':'approximate';if(!energy||this.reduced?.matches||this.doc.hidden)return;
  let last=0;const sample=now=>{if(this.destroyed||this.state!=='speaking'||this.doc.hidden)return;
   if(now-last>=33){last=now;this.analyser.getFloatTimeDomainData(this.samples);let sum=0;for(const v of this.samples)sum+=v*v;
    this.energy=Math.sqrt(sum/this.samples.length);this.avatar.style?.setProperty('--clara-mouth-open',this.energy>.012?'1':'0');}
   this.frame=this.win.requestAnimationFrame(sample);
  };this.frame=this.win.requestAnimationFrame(sample);
 }
 setState(value){if(!transitions[value]||(this.destroyed&&value!=='idle')||(value!==this.state&&!transitions[this.state].includes(value)))return false;
  this.stopMeter();this.state=value;this.avatar.dataset.state=value;if(value==='speaking')this.meter();return true;
 }
 startSpeaking(){this.setState('speaking');}stopSpeaking(){this.setState('idle');}startListening(){this.setState('listening');}startThinking(){this.setState('thinking');}
 destroy(){this.destroyed=true;this.clearBlink();this.stopMeter();this.doc.removeEventListener('visibilitychange',this.onVisibility);this.win.removeEventListener('pagehide',this.onPageHide);this.win.removeEventListener('pageshow',this.onPageShow);this.reduced?.removeEventListener?.('change',this.onVisibility);this.setState('idle');this.context?.close().catch(()=>{});}
}
if(typeof module!=='undefined'&&module.exports)module.exports={ClaraAvatarEngine};else{
 root.ClaraAvatarEngine=ClaraAvatarEngine;root.claraAvatar=new ClaraAvatarEngine('companion-avatar');
 root.onClaraSpeechStart=()=>root.claraAvatar.startSpeaking();root.onClaraSpeechEnd=()=>root.claraAvatar.stopSpeaking();
}
})(typeof window!=='undefined'?window:globalThis);
