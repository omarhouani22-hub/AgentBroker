const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(available=true){
 const calls=[],urls=[],revoked=[],timers=new Map();let blocked=false,hangPlay=false,hangSpeech=false,timerId=0,busy=0,badBlob=null;
 const audio={hidden:true,currentTime:0,paused:true,play(){this.paused=false;if(hangPlay)return new Promise(()=>{});if(blocked)return Promise.reject(new Error('autoplay'));if(this.onplaying)this.onplaying();return Promise.resolve();},pause(){this.paused=true;}};
 const engine={value:'device',querySelector(){return this.option;},option:{disabled:true}},status={textContent:''};
 const doc={getElementById:id=>({'clara-natural-audio':audio,'clara-voice-engine':engine,'natural-voice-status':status})[id]};
 const win={AbortController,setTimeout(fn,ms){timers.set(++timerId,{fn,ms});return timerId;},clearTimeout(id){timers.delete(id);},URL:{createObjectURL(){const u='blob:test-'+urls.length;urls.push(u);return u;},revokeObjectURL(u){revoked.push(u);}},async fetch(path,options={}){calls.push({path,options});if(hangSpeech&&path==='/companion/speech')return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('aborted'))));if(path==='/companion/speech'&&busy>0){busy--;return {ok:false,status:409};}return path.endsWith('/status')?{ok:true,json:async()=>({available})}:{ok:true,blob:async()=>badBlob||new Blob(['ID3synthetic-test-mp3'],{type:'audio/mpeg'})};}};
 vm.runInNewContext(fs.readFileSync('static/clara-natural-voice.js','utf8'),{window:win});
 return {context(state){win.claraAvatar={context:{state}};},bad(blob){badBlob=blob;},busy(n){busy=n;},ui:win.ClaraNaturalVoice.init(doc,win),engine,audio,status,calls,block:()=>{blocked=true;},hangPlay:()=>{hangPlay=true;},hangSpeech:()=>{hangSpeech=true;},fire(ms){for(const [id,t] of [...timers])if(t.ms===ms){timers.delete(id);t.fn();}},timerCount:()=>timers.size};
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
 const busy=fixture();await busy.ui.refresh();busy.engine.value='natural';busy.busy(1);let played=0;
 const retry=busy.ui.play('Hello',{onstart(){played++;},onend(){},onblocked(){},onerror(){throw Error('retry failed');}});
 await new Promise(resolve=>setImmediate(resolve));assert.match(busy.status.textContent,/busy/);busy.fire(2000);await retry;assert.equal(played,1);assert.equal(busy.calls.filter(x=>x.path==='/companion/speech').length,2);busy.ui.stop();
 const cancelledBusy=fixture();await cancelledBusy.ui.refresh();cancelledBusy.engine.value='natural';cancelledBusy.busy(3);let lateError=0;
 const waitingRetry=cancelledBusy.ui.play('Hello',{onerror(){lateError++;}});await new Promise(resolve=>setImmediate(resolve));cancelledBusy.ui.stop();await waitingRetry;assert.equal(lateError,0);assert.equal(cancelledBusy.timerCount(),0);

 for(const blob of [new Blob([],{type:'audio/wav'}),new Blob(['<html>error</html>'],{type:'text/html'}),new Blob(['not really audio'],{type:'audio/wav'})]){
  const invalid=fixture();await invalid.ui.refresh();invalid.engine.value='natural';invalid.bad(blob);let errors=0;
  await invalid.ui.play('Hello',{onerror(){errors++;}});assert.equal(errors,1);assert.equal(invalid.audio.hidden,true);
 }
 const progress=fixture();await progress.ui.refresh();progress.engine.value='natural';let pauses=0,progressErrors=0;
 await progress.ui.play('Hello',{onstart(){},onpause(){pauses++;},onerror(){progressErrors++;}});
 progress.audio.onwaiting();assert.equal(pauses,1);progress.fire(15000);assert.equal(progressErrors,1);assert.equal(progress.timerCount(),0);
 const paused=fixture();await paused.ui.refresh();paused.engine.value='natural';let starts=0,pauseCount=0;
 await paused.ui.play('Hello',{onstart(){starts++;},onpause(){pauseCount++;},onend(){}});
 paused.audio.onpause();assert.equal(pauseCount,1);assert.equal(paused.ui.retry(),true);assert.equal(starts,2);
 paused.audio.onended();assert.equal(paused.ui.retry(),false);assert.equal(paused.timerCount(),0);
 const muted=fixture();await muted.ui.refresh();muted.engine.value='natural';muted.audio.muted=true;muted.audio.volume=.25;await muted.ui.play('Respect mute',{onstart(){}});assert.equal(muted.audio.muted,true);assert.equal(muted.audio.volume,.25);muted.ui.stop();
 const suspended=fixture();await suspended.ui.refresh();suspended.engine.value='natural';suspended.context('suspended');let startedContext=0,blockedContext=0;await suspended.ui.play('Hello',{onstart(){startedContext++;},onblocked(){blockedContext++;}});assert.equal(startedContext,0);assert.equal(blockedContext,1);assert.equal(suspended.audio.paused,true);suspended.context('running');assert.equal(suspended.ui.retry(),true);assert.equal(startedContext,1);suspended.ui.stop();
 const closedContext=fixture();await closedContext.ui.refresh();closedContext.engine.value='natural';closedContext.context('closed');let contextErrors=0;await closedContext.ui.play('Hello',{onerror(){contextErrors++;}});assert.equal(contextErrors,1);assert.equal(closedContext.audio.hidden,true);
 console.log('Playback validation: empty/non-audio/truncated bodies, buffering watchdog, pause/retry and end cleanup passed.');
 console.log('Natural voice: disabled gate, private transport, replay cache, stop and mobile native-play fallback passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
