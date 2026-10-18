const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(available=true){
 const calls=[],urls=[],revoked=[],timers=new Map();let blocked=false,hangPlay=false,hangSpeech=false,timerId=0;
 const audio={hidden:true,currentTime:0,play(){if(hangPlay)return new Promise(()=>{});if(blocked)return Promise.reject(new Error('autoplay'));if(this.onplaying)this.onplaying();return Promise.resolve();},pause(){}};
 const engine={value:'device',querySelector(){return this.option;},option:{disabled:true}},status={textContent:''};
 const doc={getElementById:id=>({'clara-natural-audio':audio,'clara-voice-engine':engine,'natural-voice-status':status})[id]};
 const win={AbortController,setTimeout(fn,ms){timers.set(++timerId,{fn,ms});return timerId;},clearTimeout(id){timers.delete(id);},URL:{createObjectURL(){const u='blob:test-'+urls.length;urls.push(u);return u;},revokeObjectURL(u){revoked.push(u);}},async fetch(path,options={}){calls.push({path,options});if(hangSpeech&&path==='/companion/speech')return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('aborted'))));return path.endsWith('/status')?{ok:true,json:async()=>({available})}:{ok:true,blob:async()=>({type:'audio/mpeg'})};}};
 vm.runInNewContext(fs.readFileSync('static/clara-natural-voice.js','utf8'),{window:win});
 return {ui:win.ClaraNaturalVoice.init(doc,win),engine,audio,status,calls,block:()=>{blocked=true;},hangPlay:()=>{hangPlay=true;},hangSpeech:()=>{hangSpeech=true;},fire(ms){for(const [id,t] of [...timers])if(t.ms===ms){timers.delete(id);t.fn();}},timerCount:()=>timers.size};
}
(async()=>{
 const off=fixture(false);await off.ui.refresh();assert.equal(off.ui.selected(),false);let errors=0;await off.ui.play('Hello',{onerror(){errors++;}});assert.equal(errors,1);assert.equal(off.calls.length,1);assert.equal(off.calls[0].path,'/companion/speech/status');
 const f=fixture();await f.ui.refresh();f.engine.value='natural';assert.equal(f.ui.selected(),true);let started=0,ended=0,blocked=0;
 const hooks={onstart(){started++;},onend(){ended++;},onerror(){throw new Error('Unexpected error');},onblocked(){blocked++;}};
 await f.ui.play('Hello Omar',hooks);assert.equal(started,1);assert.equal(f.audio.hidden,false);f.audio.onended();assert.equal(ended,1);
 await f.ui.play('Hello Omar',hooks);assert.equal(f.calls.filter(x=>x.path==='/companion/speech').length,1); // cache avoids duplicate billed render
 f.ui.stop();assert.equal(f.audio.hidden,true);assert.equal(f.audio.onended,null);
 f.block();await f.ui.play('Hello Omar',hooks);assert.equal(blocked,1);assert.equal(f.audio.hidden,false);assert.match(f.status.textContent,/Tap Play/);
 f.audio.onplaying();assert.equal(started,3); // manual native Play remains usable
 f.ui.stop();
 const stalled=fixture();await stalled.ui.refresh();stalled.engine.value='natural';stalled.hangPlay();let waiting=0;
 await stalled.ui.play('Hello',{onblocked(){waiting++;},onstart(){},onend(){},onerror(){throw Error('Unexpected error');}});
 stalled.fire(10000);assert.equal(waiting,1);assert.equal(stalled.audio.hidden,false);
 stalled.audio.onplaying();stalled.ui.stop();assert.equal(stalled.timerCount(),0);
 const request=fixture();await request.ui.refresh();request.engine.value='natural';request.hangSpeech();let failed=0;
 const pending=request.ui.play('Hello',{onerror(){failed++;}});request.fire(45000);await pending;
 assert.equal(failed,1);assert.equal(request.audio.hidden,true);assert.equal(request.timerCount(),0);
 const cancelled=fixture();await cancelled.ui.refresh();cancelled.engine.value='natural';cancelled.hangSpeech();let late=0;
 const old=cancelled.ui.play('Hello',{onerror(){late++;}});cancelled.ui.stop();await old;
 assert.equal(late,0);assert.equal(cancelled.timerCount(),0);
 console.log('Natural voice: disabled gate, private transport, replay cache, stop and mobile native-play fallback passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
