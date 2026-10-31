const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const elements=new Map();
const element=id=>{if(!elements.has(id))elements.set(id,{value:'',hidden:false,disabled:false,readOnly:false,checked:false,textContent:'',setAttribute(){},replaceChildren(){},append(){},scrollIntoView(){},classList:{toggle(){},contains(){return false;}}});return elements.get(id);};
const timers=new Map(),intervals=new Map();let timerId=0, request=0, mode='success', transientFailures=0;
const voice={halt(){},refreshNatural(){},unlock(){},thinking(){},active(){return false;},failed(){},remember(){},speak(){}};
const context={document:{getElementById:element,createElement:()=>element('card'+Math.random()),addEventListener(){}},window:{},AgentBrokerVoice:{init:()=>voice},AgentBrokerCamera:{init:()=>({frame:()=>null,clear(){},close(){}})},ClaraAppearance:{init:()=>({request:()=>({}),advance(){},value:()=>({})})},AbortController,setInterval(fn){intervals.set(++timerId,fn);return timerId;},clearInterval(id){intervals.delete(id);},setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},fetch:async(path,options)=>{
 if(path==='/session/status')return {ok:true,json:async()=>({authenticated:false})};
 request++;
 if(path==='/companion/messages'&&mode==='transient-load'&&transientFailures++===0)return {ok:false,status:503,json:async()=>({error:'Service temporarily unavailable'})};
 if(path==='/companion/messages'&&mode==='bad-load')return {ok:false,status:400,json:async()=>({error:'Bad request'})};
 if(mode==='hang')return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'}))));
 if(mode==='html')return {ok:false,json:async()=>{throw new SyntaxError('HTML response');}};
 return {ok:true,json:async()=>({messages:[{role:'assistant',content:'Reply '+request}],status:'replied'})};
}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/clara-chat.js','utf8'),context);
async function send(text){element('companion-input').value=text;await element('companion-form').onsubmit({preventDefault(){},submitter:{}});}
(async()=>{
 await Promise.resolve();await Promise.resolve();
 await send('First');await send('Second');assert.equal(request,2);assert.equal(element('companion-send').disabled,false);
 mode='hang';const pending=send('Keep my message');await Promise.resolve();
 for(const fn of [...timers.values()])fn();await pending;
 assert.equal(element('companion-input').value,'Keep my message');assert.equal(element('companion-send').disabled,false);assert.equal(element('companion-input').readOnly,false);assert.match(element('companion-status').textContent,/too long/);
 mode='success';await send('Try again');assert.equal(element('companion-input').value,'');
 mode='html';await send('Preserve this too');assert.match(element('companion-status').textContent,/unreadable/);assert.equal(element('companion-input').value,'Preserve this too');assert.equal(element('companion-send').disabled,false);assert.equal(timers.size,0);assert.equal(intervals.size,0);
 mode='transient-load';transientFailures=0;element('private-ui').hidden=false;
 const beforeRetry=request, loading=context.loadConversation();
 for(let i=0;i<8;i++)await Promise.resolve();
 assert.match(element('companion-status').textContent,/Retrying conversation once/);
 for(const [id,fn] of [...timers.entries()]){timers.delete(id);fn();}
 assert.equal(await loading,true);assert.equal(request-beforeRetry,2);
 assert.equal(element('companion-status').textContent,'');
 mode='bad-load';const beforeBad=request;
 assert.equal(await context.loadConversation(),false);assert.equal(request-beforeBad,1);
 assert.match(element('companion-status').textContent,/Could not load conversation/);
 assert.equal(timers.size,0);assert.equal(intervals.size,0);
 console.log('Repeated replies, timeout recovery, retained input, one transient GET retry, no 400 retry, and timer cleanup passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
