const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = Object.fromEntries(['connection-status','connection-refresh','connection-test'].map(id=>[id,{disabled:false,textContent:''}]));
let response, calls=[], timers=new Set();
const context = {document:{getElementById:id=>elements[id]},AbortController,
 setTimeout(fn){timers.add(fn);return fn;},clearTimeout(fn){timers.delete(fn);},
 fetch:async(path,options)=>{calls.push({path,options});return response;}};
vm.runInNewContext(fs.readFileSync('static/clara-connection.js','utf8'),context);
(async()=>{
 assert.equal(calls.length,0); // No checks while signed out or before owner action.
 response={status:200,json:async()=>({selected_route:'openrouter_free',configured:true,remaining_today:11,last_observation:{route:'openrouter_free',model:'vendor/actual-model',status:'ok',duration_ms:123,checked_at:'2026-10-28T00:00:00Z'}})};
 await elements['connection-refresh'].onclick();
 assert.equal(calls[0].options.method,'GET');
 assert.match(elements['connection-status'].textContent,/vendor\/actual-model/);
 assert.match(elements['connection-status'].textContent,/123 ms/);
 await elements['connection-test'].onclick();
 assert.equal(calls[1].path,'/companion/connection/test');
 assert.equal(calls[1].options.body,'{}');
 assert.equal(calls[1].options.headers['X-AgentBroker-Request'],'1');
 response={status:401};await elements['connection-refresh'].onclick();
 assert.match(elements['connection-status'].textContent,/Sign in/);
 response={status:503,json:async()=>{throw Error('private raw error');}};
 await elements['connection-test'].onclick();
 assert.doesNotMatch(elements['connection-status'].textContent,/private raw error/);
 assert.equal(elements['connection-test'].disabled,false);
 assert.equal(timers.size,0);
 console.log('Connection UI: explicit checks, model and timing display, safe errors, authentication and cleanup passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
