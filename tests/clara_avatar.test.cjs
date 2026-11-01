const assert=require('node:assert/strict');
const {ClaraAvatarEngine}=require('../static/clara-avatar.js');
function fixture(reduced=false){
 const timers=new Map(),classes=new Set(),events=new Map();let next=0;
 const avatar={dataset:{},classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)}};
 const doc={hidden:false,getElementById:()=>avatar,addEventListener:(e,f)=>events.set(e,f),removeEventListener:e=>events.delete(e)};
 const media={matches:reduced,addEventListener(){},removeEventListener(){}};
 const win={setTimeout(f,ms){timers.set(++next,{f,ms});return next;},clearTimeout:id=>timers.delete(id),matchMedia:()=>media,addEventListener:(e,f)=>events.set(e,f),removeEventListener:e=>events.delete(e)};
 const engine=new ClaraAvatarEngine('claraAvatar',doc,win);
 return {engine,doc,events,avatar,classes,timers,fire(){const [id,job]=timers.entries().next().value;timers.delete(id);job.f();}};
}
const f=fixture();assert.equal(f.timers.size,1);f.engine.scheduleBlink();assert.equal(f.timers.size,1);
f.fire();assert.ok(f.classes.has('blinking'));f.fire();assert.ok(!f.classes.has('blinking'));assert.equal(f.timers.size,1);
f.engine.startSpeaking();assert.equal(f.avatar.dataset.state,'speaking');f.engine.setState('invalid');assert.equal(f.engine.state,'speaking');
f.engine.stopSpeaking();assert.equal(f.avatar.dataset.state,'idle');
f.doc.hidden=true;f.events.get('visibilitychange')();assert.equal(f.timers.size,0);assert.ok(!f.classes.has('blinking'));
f.doc.hidden=false;f.events.get('visibilitychange')();assert.equal(f.timers.size,1);
const late=f.timers.values().next().value.f;f.engine.startSpeaking();f.engine.destroy();late();
assert.equal(f.avatar.dataset.state,'idle');assert.equal(f.timers.size,0);assert.equal(f.events.size,0);f.engine.startSpeaking();assert.equal(f.avatar.dataset.state,'idle');
assert.equal(fixture(true).timers.size,0);
assert.throws(()=>new ClaraAvatarEngine('missing',{getElementById:()=>null},{}),/not found/);
console.log('Avatar engine: blink lifecycle, no duplicate timers, hidden/reduced-motion cleanup and stale state rejection passed.');
const machine=fixture();machine.engine.setState('error');assert.equal(machine.engine.state,'error');machine.engine.setState('thinking');assert.equal(machine.engine.state,'thinking');machine.engine.startSpeaking();assert.equal(machine.engine.setState('listening'),false);assert.equal(machine.engine.state,'speaking');machine.engine.stopSpeaking();assert.equal(machine.engine.setState('listening'),true);machine.engine.destroy();
console.log('Deterministic state machine: explicit error, valid transitions and blocked speaking-to-listening transition passed.');
