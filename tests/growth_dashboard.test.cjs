const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map(),requests=[];let interval;
function element(){return {children:[],textContent:'',value:'',checked:false,hidden:false,disabled:false,append(e){this.children.push(e);},replaceChildren(){this.children=[];},setAttribute(k,v){this[k]=v;},set innerHTML(_){throw Error('Untrusted HTML must not be inserted');}};}
const get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
const state={settings:{enabled:false,sources:[]},worker_configured:false,publishing_enabled:false,
 metrics:{discovered_use_cases:1,owner_verified_public_leads:0,verified_conversations:0,trial_activations:null,converted_trials:null,trial_to_paid_rate:null,actual_net_revenue_minor:null},
 recommendations:[{action:'Review evidence',source_url:'https://www.moltbook.com/post/fixture'}],
 policies:[{id:'policy',state:'pending',body:{product:'Sales are closed.'},origin:'Synthetic fixture'}],
 leads:[{id:'lead',author:'<img src=x onerror=alert(1)>',title:'Agent restart',url:'https://www.moltbook.com/post/fixture',excerpt:'Synthetic agent loses state.',signals:['state_loss'],stage:'discovered',followup_at:0,feedback:'not_tested',note:'',verified_at:0}],
 drafts:[{id:'draft',lead_id:'lead',digest:'digest',state:'pending',payload:{kind:'educational_comment',source_url:'https://www.moltbook.com/post/fixture',content:'A synthetic restore demonstration.',evidence_scope:'Not a customer.'}}],actions:[],daily_report:{sales_enabled:false}};
const ctx={document:{getElementById:get,createElement:element,hidden:false},AbortController,console,Date,confirm:()=>true,
 setTimeout:()=>1,clearTimeout(){},setInterval(fn){interval=fn;},fetch:async(path,options)=>{requests.push({path,options});return {ok:true,status:200,json:async()=>path==='/growth/status'?state:{saved:true,answer:'Approved policy answer'}};}};
vm.runInNewContext(fs.readFileSync('static/growth.js','utf8'),ctx);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function descendants(e){return [e,...e.children.flatMap(descendants)];}
(async()=>{
 await flush();
 assert.equal(requests.length,1);assert.equal(requests[0].path,'/growth/status');
 assert.ok(descendants(get('metrics')).some(e=>e.textContent==='Not connected'));
 assert.ok(descendants(get('leads')).some(e=>e.textContent.includes('<img src=x')));
 const approve=descendants(get('drafts')).find(e=>e.textContent==='Approve this exact draft');
 const edit=descendants(get('drafts')).find(e=>e.value==='A synthetic restore demonstration.');edit.value='Unsaved changed draft';await approve.onclick();
 assert.equal(requests.filter(r=>r.path.endsWith('/drafts/draft/review')).length,0);assert.match(get('notice').textContent,/Save edits/);
 edit.value='A synthetic restore demonstration.';await approve.onclick();
 const review=requests.find(r=>r.path.endsWith('/drafts/draft/review'));assert.equal(JSON.parse(review.options.body).digest,'digest');
 assert.equal(review.options.headers['X-AgentBroker-Request'],'1');
 assert.equal(requests.filter(r=>r.path.includes('/publish')).length,0);
 get('enabled').checked=true;get('github').checked=true;await get('save-settings').onclick();
 assert.deepEqual(JSON.parse(requests.find(r=>r.path==='/growth/settings').options.body),{enabled:true,sources:['github']});
 const before=requests.length;await interval();await flush();assert.ok(requests.slice(before).every(r=>r.path==='/growth/status'));
 assert.equal(requests.filter(r=>r.path.includes('paypal')||r.path.includes('moltbook.com')).length,0);
 console.log('Growth dashboard: private fetch, unknown metrics, inert source text, exact approval, permissions and read-only polling passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
