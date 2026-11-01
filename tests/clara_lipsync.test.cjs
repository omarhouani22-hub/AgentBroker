const assert=require('node:assert/strict');
const {ClaraAvatarEngine}=require('../static/clara-avatar.js');
function fixture({webkit=false,byteOnly=false,analysisFailure=false}={}){
 let next=0,time=0,level=0,contexts=0,sources=0;const frames=new Map(),timers=new Map(),listeners=new Map(),props=new Map(),contextEvents=new Map(),connections=[];
 const avatar={dataset:{},style:{setProperty:(k,v)=>props.set(k,v)},classList:{add(){},remove(){}}};
 const doc={hidden:false,getElementById:()=>avatar,addEventListener(){},removeEventListener(){}};
 const audio={src:'blob:synthetic-speech',paused:true,ended:false,muted:false,volume:1,readyState:4,
  addEventListener(n,f){listeners.set(n,f);},removeEventListener(n){listeners.delete(n);}};
 const analyser={fftSize:512,connect(){},getFloatTimeDomainData(a){for(let i=0;i<a.length;i++)a[i]=i%2?level:-level;},getByteTimeDomainData(a){for(let i=0;i<a.length;i++)a[i]=128+(i%2?1:-1)*Math.round(level*128);}};
 if(byteOnly)delete analyser.getFloatTimeDomainData;
 class Context{
  constructor(){contexts++;this.state='suspended';this.destination={out:true};}
  createAnalyser(){return analyser;}createGain(){return {gain:{value:1},connect(){}};}
  createMediaElementSource(){sources++;return {connect(target){if(analysisFailure&&target===analyser)throw Error('synthetic analysis failure');connections.push(target);}};}
  resume(){return Promise.resolve();}close(){return Promise.resolve();}
  addEventListener(n,f){contextEvents.set(n,f);}removeEventListener(n){contextEvents.delete(n);}
 }
 const win={setTimeout(f){timers.set(++next,f);return next;},clearTimeout:n=>timers.delete(n),matchMedia:()=>({matches:false}),addEventListener(){},removeEventListener(){},requestAnimationFrame(f){frames.set(++next,f);return next;},cancelAnimationFrame:n=>frames.delete(n)};
 win[webkit?'webkitAudioContext':'AudioContext']=Context;
 const engine=new ClaraAvatarEngine('avatar',doc,win);
 function emit(name){listeners.get(name)?.();}
 function tick(n=1){for(let i=0;i<n;i++){time+=34;const pending=[...frames.values()];frames.clear();for(const fn of pending)fn(time);}}
 function start(){audio.paused=false;engine.context.state='running';emit('playing');engine.startSpeaking();}
 return {engine,audio,avatar,props,frames,timers,connections,analyser,contextEvents,emit,tick,start,level:v=>{level=v;},counts:()=>({contexts,sources}),value:()=>Number(props.get('--clara-mouth-open')||0)};
}
(async()=>{
 const f=fixture();f.engine.unlockAudio(f.audio);f.engine.unlockAudio(f.audio);assert.deepEqual(f.counts(),{contexts:1,sources:1});
 f.start();f.level(.15);f.tick();const first=f.value();assert.ok(first>0&&first<.65,'Attack is smoothed, not binary');
 f.tick(5);const open=f.value();assert.ok(open>first&&open<1);
 f.level(0);f.tick();assert.ok(f.value()>0&&f.value()<open,'Silence has a release envelope');f.tick(20);assert.equal(f.value(),0);
 f.level(.2);f.tick(4);assert.ok(f.value()>0);f.audio.muted=true;f.emit('volumechange');assert.equal(f.value(),0);assert.equal(f.frames.size,0);
 f.audio.muted=false;f.emit('volumechange');f.tick(4);assert.ok(f.value()>0);
 f.audio.volume=0;f.emit('volumechange');assert.equal(f.value(),0);f.audio.volume=1;f.emit('volumechange');f.tick(3);assert.ok(f.value()>0);
 for(const event of ['pause','ended','error','abort','emptied','waiting','stalled']){f.audio.paused=false;f.emit('playing');f.engine.startSpeaking();f.tick(3);assert.ok(f.value()>0,event);f.emit(event);assert.equal(f.value(),0,event);assert.equal(f.frames.size,0,event);}
 f.audio.paused=false;f.emit('playing');f.engine.startSpeaking();f.tick(2);f.engine.context.state='suspended';f.contextEvents.get('statechange')();assert.equal(f.value(),0);
 f.engine.context.state='running';f.contextEvents.get('statechange')();f.tick(3);assert.ok(f.value()>0,'Late context resume restarts measurement');
 const stale=[...f.frames.values()][0];f.engine.stopSpeaking();stale(10000);assert.equal(f.value(),0);assert.equal(f.frames.size,0);
 f.audio.paused=false;f.emit('playing');f.engine.startSpeaking();f.level(.004);f.tick(6);assert.ok(f.value()>.05,'Quiet audible speech below the old .012 threshold must animate');f.level(.0005);f.tick(20);assert.equal(f.value(),0,'Sub-gate noise must close the mouth');
 f.engine.destroy();assert.equal(f.value(),0);
 const safari=fixture({webkit:true,byteOnly:true});safari.engine.unlockAudio(safari.audio);safari.start();safari.level(.13);safari.tick(5);assert.ok(safari.value()>0);safari.engine.stopSpeaking();assert.equal(safari.value(),0);
 const fallback=fixture({analysisFailure:true});fallback.engine.unlockAudio(fallback.audio);fallback.start();assert.equal(fallback.avatar.dataset.mouthTiming,'approximate');assert.equal(fallback.connections.length,1,'Audible destination remains connected even if analysis fails');fallback.engine.destroy();
 console.log('Lip sync: live RMS attack/release, silence, mute/volume, completion/errors, resumed contexts, stale frames, WebKit byte sampling and direct-audio fallback passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
