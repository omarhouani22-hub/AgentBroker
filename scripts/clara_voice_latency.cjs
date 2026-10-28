/* Deterministic playback scheduling benchmark; no model, speech API or private data. */
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
function fixture(source){
 let now=0,pending=[],requests=[],plays=[],revoked=[],timers=new Map(),timer=0;
 const audio={hidden:true,currentTime:0,pause(){},play(){plays.push({at:now,src:this.src});this.onplaying?.();return Promise.resolve();}};
 const engine={value:'device',querySelector(){return {disabled:false};}},status={textContent:''};
 const doc={getElementById:id=>({'clara-natural-audio':audio,'clara-voice-engine':engine,'natural-voice-status':status})[id]};
 const win={AbortController,setTimeout(fn,ms){timers.set(++timer,{fn,ms});return timer;},clearTimeout(id){timers.delete(id);},URL:{createObjectURL:blob=>'blob:'+blob.id,revokeObjectURL:url=>revoked.push(url)},fetch(path,options={}){
  if(path.endsWith('/status'))return Promise.resolve({ok:true,json:async()=>({available:true,internal:true,max_characters:800})});
  requests.push({path,options});return new Promise(resolve=>pending.push({resolve,options,id:requests.length}));
 }};
 vm.runInNewContext(source,{window:win});
 return {ui:win.ClaraNaturalVoice.init(doc,win),audio,engine,status,requests,plays,revoked,timers,
  async release(ms,ok=true){now+=ms;const item=pending.shift();assert.ok(item,'expected a queued speech request');item.resolve({ok,status:ok?200:503,blob:async()=>({id:item.id})});await flush();},
  pending:()=>pending.length};
}
async function flush(){for(let i=0;i<20;i++)await Promise.resolve();}
const hooks={onstart(){},onend(){},onblocked(){},onerror(){throw Error('Unexpected speech failure');}};
async function measure(source){
 const f=fixture(source);await f.ui.refresh();const done=f.ui.play('English voice latency fixture. '.repeat(60),hooks);
 for(const ms of [120,180,240])await f.release(ms);
 await done;const result={segments:f.requests.length,first_play_ms:f.plays[0].at,all_audio_ready_ms:540};f.ui.stop();return result;
}
async function regressions(source){
 let checks=0;
 const f=fixture(source);await f.ui.refresh();let ended=0;
 const done=f.ui.play('English voice latency fixture. '.repeat(60),{...hooks,onend(){ended++;}});
 await f.release(120);assert.equal(f.plays.length,1);assert.equal(f.pending(),1);checks++;
 f.audio.onended();assert.equal(ended,0);assert.equal(f.plays.length,1);checks++;
 await f.release(180);assert.equal(f.plays.length,2);assert.equal(f.audio.src,'blob:2');checks++;
 await f.release(240);await done;f.audio.onended();assert.equal(f.audio.src,'blob:3');f.audio.onended();assert.equal(ended,1);checks++;
 await f.ui.play('English voice latency fixture. '.repeat(60),hooks);assert.equal(f.requests.length,3);assert.equal(f.audio.src,'blob:1');f.ui.stop();checks++;
 const cancelled=fixture(source);await cancelled.ui.refresh();let late=0;
 const old=cancelled.ui.play('English voice latency fixture. '.repeat(60),{onstart(){},onend(){late++;},onerror(){late++;}});
 await cancelled.release(120);cancelled.ui.stop();await cancelled.release(180);await old;
 assert.equal(late,0);assert.equal(cancelled.requests.length,2);assert.equal(cancelled.plays.length,1);assert.equal(cancelled.timers.size,0);checks++;
 // An obsolete response cannot append audio to a replacement reply.
 const replacement=cancelled.ui.play('New English reply.',hooks);await cancelled.release(100);await replacement;assert.equal(cancelled.audio.src,'blob:3');cancelled.ui.stop();checks++;
 const overlap=fixture(source);await overlap.ui.refresh();
 const stale=overlap.ui.play('English voice latency fixture. '.repeat(60),{onerror(){throw Error('Stale error');}});
 const fresh=overlap.ui.play('Replacement English reply.',hooks);
 await overlap.release(100);await stale;assert.equal(overlap.plays.length,0);
 await overlap.release(100);await fresh;assert.equal(overlap.audio.src,'blob:2');assert.equal(overlap.requests.length,2);overlap.ui.stop();checks++;
 const short=fixture(source);await short.ui.refresh();const single=short.ui.play('One short English reply.',hooks);await short.release(120);await single;assert.equal(short.plays[0].at,120);assert.equal(short.requests.length,1);short.ui.stop();checks++;
 const failed=fixture(source);await failed.ui.refresh();let errors=0;
 const failure=failed.ui.play('English voice latency fixture. '.repeat(60),{onstart(){},onerror(){errors++;}});
 await failed.release(120);await failed.release(180,false);await failure;assert.equal(errors,1);assert.equal(failed.audio.hidden,true);assert.equal(failed.timers.size,0);checks++;
 const limited=fixture(source);await limited.ui.refresh();let rejected=0;await limited.ui.play('x'.repeat(4001),{onerror(){rejected++;}});assert.equal(rejected,1);assert.equal(limited.requests.length,0);checks++;
 for(const request of f.requests){assert.equal(request.path,'/companion/speech');assert.equal(request.options.headers['X-AgentBroker-Request'],'1');assert.equal(request.options.cache,'no-store');assert.ok(JSON.parse(request.options.body).text.length<=800);}checks++;
 return checks;
}
async function main(){
 const args=process.argv.slice(2),option=name=>args.includes(name)?args[args.indexOf(name)+1]:null;
 const source=fs.readFileSync(option('--source')||'static/clara-natural-voice.js','utf8');
 const measured=await measure(source);
 if(args.includes('--measure-only')){console.log(JSON.stringify(measured));return;}
 const skill=fs.readFileSync('skills/clara-self-improvement/SKILL.md','utf8');assert.match(skill,/name: clara-self-improvement/);
 assert.equal(measured.segments,3);assert.equal(measured.first_play_ms,120);
 const checks=await regressions(source);
 const report={skill:'clara-self-improvement',skill_sha256:crypto.createHash('sha256').update(skill).digest('hex'),source_sha256:crypto.createHash('sha256').update(source).digest('hex'),objective:'Start playback after first segment, before remaining synthesis completes',scope:'synthetic_browser_scheduling_not_real_audio_or_model_latency',...measured,regression_checks:checks,passed:true,paid_calls:0,production_changed:false};
 if(option('--report'))fs.writeFileSync(option('--report'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}
if(require.main===module)main().catch(error=>{console.error(error);process.exitCode=1;});
module.exports={fixture,measure,regressions};
