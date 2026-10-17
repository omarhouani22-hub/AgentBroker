/* Local-server recognition. Audio leaves the browser only for this origin. */
(function(root){
'use strict';
function wav(samples, rate){
 const n=Math.floor(samples.length*16000/rate),buffer=new ArrayBuffer(44+n*2),v=new DataView(buffer);
 function word(at,text){for(let i=0;i<text.length;i++)v.setUint8(at+i,text.charCodeAt(i));}
 word(0,'RIFF');v.setUint32(4,36+n*2,true);word(8,'WAVE');word(12,'fmt ');v.setUint32(16,16,true);
 v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);word(36,'data');v.setUint32(40,n*2,true);
 for(let i=0;i<n;i++){
  const from=Math.floor(i*rate/16000),to=Math.max(from+1,Math.floor((i+1)*rate/16000));let sum=0;
  for(let j=from;j<to&&j<samples.length;j++)sum+=samples[j];
  const x=Math.max(-1,Math.min(1,sum/(to-from)));v.setInt16(44+i*2,x<0?x*32768:x*32767,true);
 }
 return new Blob([buffer],{type:'audio/wav'});
}
let available=false,enabled=!!(root.document&&root.document.documentElement&&root.document.documentElement.dataset.localOnly==='true');
class Recognition{
 constructor(){this.lang='en-US';this.active=false;this.generation=0;this.controller=null;}
 emit(name,value){if(typeof this[name]==='function')this[name](value);}
 cleanup(){
  if(this.timer)root.clearTimeout(this.timer);this.timer=null;
  if(this.limitTimer)root.clearTimeout(this.limitTimer);this.limitTimer=null;
  if(this.processor){this.processor.onaudioprocess=null;this.processor.disconnect();this.processor=null;}
  if(this.source){this.source.disconnect();this.source=null;}
  if(this.gain){this.gain.disconnect();this.gain=null;}
  if(this.stream){this.stream.getTracks().forEach(t=>t.stop());this.stream=null;}
  if(this.context){this.context.close().catch(()=>{});this.context=null;}
 }
 async start(){
  if(this.active)throw new Error('Recognition already active');
  this.active=true;const id=++this.generation;this.parts=[];this.count=0;this.heard=false;this.lastVoice=0;
  if(!available||!/^en/i.test(this.lang)){this.active=false;this.emit('onerror',{error:'service-not-allowed'});this.emit('onend');return;}
  try{
   this.stream=await root.navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,channelCount:1}});
   if(id!==this.generation||!this.active){this.cleanup();return;}
   const Context=root.AudioContext||root.webkitAudioContext;this.context=new Context();await this.context.resume();
   if(id!==this.generation||!this.active){this.cleanup();return;}
   this.rate=this.context.sampleRate;this.source=this.context.createMediaStreamSource(this.stream);
   this.processor=this.context.createScriptProcessor(4096,1,1);this.gain=this.context.createGain();this.gain.gain.value=0;
   this.source.connect(this.processor);this.processor.connect(this.gain);this.gain.connect(this.context.destination);
   this.processor.onaudioprocess=e=>{
    if(!this.active||id!==this.generation)return;
    const data=new Float32Array(e.inputBuffer.getChannelData(0));this.parts.push(data);this.count+=data.length;
    let energy=0;for(const x of data)energy+=x*x;
    const seconds=this.count/this.rate;
    if(Math.sqrt(energy/data.length)>.012){this.heard=true;this.lastVoice=seconds;}
    if(seconds>=28||(this.heard&&seconds-this.lastVoice>1.8))this.stop();
   };
   this.timer=root.setTimeout(()=>{if(!this.heard)this.stop();},8000);
   this.limitTimer=root.setTimeout(()=>this.stop(),29000);this.emit('onstart');
  }catch(error){if(id!==this.generation)return;this.active=false;this.cleanup();this.emit('onerror',{error:error.name==='NotAllowedError'?'not-allowed':'audio-capture'});this.emit('onend');}
 }
 async stop(){
  if(!this.active)return;this.active=false;const id=this.generation;this.cleanup();
  if(!this.count||!this.heard){this.emit('onerror',{error:'no-speech'});this.emit('onend');return;}
  const samples=new Float32Array(this.count);let offset=0;for(const part of this.parts){samples.set(part,offset);offset+=part.length;}this.parts=[];
  this.controller=new root.AbortController();
  try{
   const response=await root.fetch('/companion/transcribe',{method:'POST',headers:{'Content-Type':'audio/wav','X-AgentBroker-Request':'1'},body:wav(samples,this.rate),signal:this.controller.signal,cache:'no-store'});
   if(id!==this.generation)return;const data=await response.json();if(!response.ok)throw new Error('Internal recognition failed');
   if(data.text){const result=[{transcript:data.text,confidence:1}];result.isFinal=true;this.emit('onresult',{results:[result],resultIndex:0});}
   else this.emit('onerror',{error:'no-speech'});
  }catch(_){if(id===this.generation)this.emit('onerror',{error:'network'});}
  finally{if(id===this.generation){this.controller=null;this.emit('onend');}}
 }
 abort(){this.generation++;this.active=false;if(this.controller)this.controller.abort();this.controller=null;this.cleanup();this.parts=[];this.emit('onend');}
}
const api={Recognition,wav,get enabled(){return enabled;},get available(){return available;},async refresh(){
 try{const response=await root.fetch('/companion/local/status',{cache:'no-store'});const data=await response.json();enabled=response.ok&&data.enabled===true;available=enabled&&data.recognition_available===true&&!!(root.navigator&&root.navigator.mediaDevices&&(root.AudioContext||root.webkitAudioContext));}catch(_){available=false;}
}};
root.ClaraInternalMic=api;
})(window);
