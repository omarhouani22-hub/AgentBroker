const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(available=true){
 const calls=[],urls=[],revoked=[];let blocked=false;
 const audio={hidden:true,currentTime:0,play(){if(blocked)return Promise.reject(new Error('autoplay'));if(this.onplaying)this.onplaying();return Promise.resolve();},pause(){}};
 const engine={value:'device',querySelector(){return this.option;},option:{disabled:true}},status={textContent:''};
 const doc={getElementById:id=>({'clara-natural-audio':audio,'clara-voice-engine':engine,'natural-voice-status':status})[id]};
 const win={AbortController,URL:{createObjectURL(){const u='blob:test-'+urls.length;urls.push(u);return u;},revokeObjectURL(u){revoked.push(u);}},async fetch(path,options={}){calls.push({path,options});return path.endsWith('/status')?{ok:true,json:async()=>({available})}:{ok:true,blob:async()=>({type:'audio/mpeg'})};}};
 vm.runInNewContext(fs.readFileSync('static/clara-natural-voice.js','utf8'),{window:win});
 return {ui:win.ClaraNaturalVoice.init(doc,win),engine,audio,status,calls,block:()=>{blocked=true;}};
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
 console.log('Natural voice: disabled gate, private transport, replay cache, stop and mobile native-play fallback passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
