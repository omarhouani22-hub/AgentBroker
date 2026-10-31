'use strict';
const get=id=>document.getElementById(id);
const stages=['discovered','reviewed','permission_requested','opted_in','conversation','trial_requested','feedback','closed'];
const feedbacks=['not_tested','restore_passed','restore_failed','access_issue','declined','other'];
let data=null,busy=false;
function node(tag,text,parent){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(parent)parent.append(e);return e;}
async function api(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),120000);
 try{const r=await fetch(path,{method:body===undefined?'GET':'POST',cache:'no-store',credentials:'same-origin',headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
 const d=await r.json();if(!r.ok)throw Error(r.status===401?'Sign in to the owner workspace first.':d.error||'Request failed');return d;}finally{clearTimeout(timer);}
}
async function action(fn){if(busy)return;busy=true;get('notice').textContent='Working…';try{await fn();await load();get('notice').textContent='Saved. No sales were opened.';}catch(e){get('notice').textContent=e.message;}finally{busy=false;}}
function button(parent,text,fn,disabled=false){const b=node('button',text,parent);b.type='button';b.disabled=disabled;b.onclick=()=>action(fn);return b;}
function link(parent,url){const a=node('a',url,parent);a.href=url;a.target='_blank';a.rel='noopener noreferrer';}
function choose(parent,values,current){const e=node('select',undefined,parent);for(const v of values){const o=node('option',v.replaceAll('_',' '),e);o.value=v;}e.value=current;return e;}
function render(){
 for(const id of ['metrics','recommendations','policies','leads','drafts','actions'])get(id).replaceChildren();
 get('enabled').checked=data.settings.enabled;for(const source of ['moltbook','github'])get(source).checked=data.settings.sources.includes(source);
 get('operating-status').textContent=(data.worker_configured?'Background worker configured; best effort while the host is running.':'Background worker is not enabled on the server. Due cycles can be reviewed here; unattended scheduling is not active.')+' Publishing: '+(data.publishing_enabled?'separate approval required for every item.':'disabled. Verified durable storage and explicit server enablement are required.');
 const labels={discovered_use_cases:'Public use-case candidates',owner_verified_public_leads:'Owner-reviewed public leads',verified_conversations:'Verified lead conversations',trial_activations:'Verified trial activations',converted_trials:'Verified converted trials',trial_to_paid_rate:'Trial-to-paid conversion',actual_net_revenue_minor:'Verified net revenue'};
 for(const [key,label] of Object.entries(labels)){const box=node('div',undefined,get('metrics'));box.className='metric';node('span',label,box);let value=data.metrics[key];node('strong',value===null?'Not connected':key==='actual_net_revenue_minor'?'USD '+(value/100).toFixed(2):key==='trial_to_paid_rate'?(100*value).toFixed(1)+'%':String(value),box);}
 for(const r of data.recommendations){const p=node('p',r.action,get('recommendations'));if(r.source_url){node('br',undefined,p);link(p,r.source_url);}}
 for(const p of data.policies){const card=node('article',undefined,get('policies'));node('strong','Policy '+p.id.slice(0,12)+' · '+p.state,card);for(const [k,v] of Object.entries(p.body))node('p',k+': '+v,card);node('small',p.origin,card);button(card,p.state==='approved'?'Revoke approval':'Approve these policy statements',()=>api('/growth/policies/'+p.id+'/review',{action:p.state==='approved'?'revoke':'approve'}));}
 if(!data.leads.length)node('p','No prospects are recorded. Enable permitted sources to collect evidence; no customers are assumed.',get('leads'));
 for(const l of data.leads){const card=node('article',undefined,get('leads'));node('h3',l.author+' · '+l.title,card);node('small',l.verified_historical_conversion?'Verified historical trial-to-paid conversion':l.verified_trial_activation?'Verified staging trial activation':'No verified trial activation',card);link(card,l.url);node('p',l.excerpt,card);node('small','Untrusted public excerpt · signals: '+l.signals.join(', ')+' · '+(l.verified_at?'owner reviewed':'awaiting review'),card);
 const stage=choose(card,stages,l.stage),feedback=choose(card,feedbacks,l.feedback);stage.setAttribute('aria-label','Lead stage');feedback.setAttribute('aria-label','Owner-reported feedback category');const due=node('input',undefined,card);due.type='datetime-local';due.setAttribute('aria-label','Internal follow-up time');if(l.followup_at)due.value=new Date(l.followup_at*1000-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16);
 const note=node('textarea',undefined,card);note.value=l.note;note.maxLength=400;note.setAttribute('aria-label','Private owner summary without contacts or secrets');
 button(card,'Run a synthetic local restore demonstration',()=>api('/growth/leads/'+l.id+'/demo',{}));
 button(card,'Save internal follow-up',()=>api('/growth/leads/'+l.id,{stage:stage.value,feedback:feedback.value,followup_at:due.value?Math.floor(new Date(due.value).getTime()/1000):0,note:note.value,verify_source:false}));
 button(card,'I reviewed this public use case',()=>api('/growth/leads/'+l.id,{stage:'reviewed',feedback:l.feedback,followup_at:l.followup_at,note:l.note,verify_source:true}));}
 if(!data.drafts.length)node('p','No drafts yet. Discovery proposes educational material from actual public use-case evidence.',get('drafts'));
 for(const d of data.drafts){const card=node('article',undefined,get('drafts'));node('h3',d.payload.kind.replaceAll('_',' ')+' · '+d.state,card);link(card,d.payload.source_url);node('small','Exact draft digest: '+d.digest+' · no customer consent inferred',card);const text=node('textarea',undefined,card);text.value=d.payload.content;text.maxLength=1800;text.setAttribute('aria-label','Draft content');const unchanged=()=>{if(text.value!==d.payload.content)throw Error('Save edits as a new pending version before approving or publishing.');};
 if(['pending','approved','rejected'].includes(d.state))button(card,'Save as new pending version',()=>api('/growth/drafts/'+d.id+'/edit',{content:text.value}));
 if(d.state==='pending'){button(card,'Approve this exact draft',()=>{unchanged();return api('/growth/drafts/'+d.id+'/review',{action:'approve',digest:d.digest});});button(card,'Reject',()=>api('/growth/drafts/'+d.id+'/review',{action:'reject',digest:d.digest}));}
 if(d.state==='approved'){button(card,'Return to review',()=>api('/growth/drafts/'+d.id+'/review',{action:'revoke',digest:d.digest}));button(card,'Publish this approved item once',async()=>{unchanged();if(confirm('Publish exactly the reviewed draft to '+d.payload.target_id+'? This is an external action.'))await api('/growth/drafts/'+d.id+'/publish',{digest:d.digest,confirm:'publish-this-exact-draft'});},!data.publishing_enabled);}
 if(d.payload.kind!=='educational_post')button(card,'Prepare a separate Moltbook post',()=>{unchanged();return api('/growth/drafts/'+d.id+'/post',{submolt:'general'});});
 node('small',d.payload.evidence_scope,card);}
 get('report').textContent=JSON.stringify(data.daily_report,null,2);
 for(const a of data.actions){const card=node('article',undefined,get('actions'));node('strong',new Date(a.created_at*1000).toISOString()+' · '+a.kind+' · '+a.state,card);node('pre',JSON.stringify({request:a.request,outcome:a.outcome},null,2),card);}
}
async function load(){data=await api('/growth/status');render();}
get('save-settings').onclick=()=>action(()=>api('/growth/settings',{enabled:get('enabled').checked,sources:['moltbook','github'].filter(s=>get(s).checked)}));
get('scan').onclick=()=>action(()=>api('/growth/run',{}));
get('ask').onclick=()=>action(async()=>{const r=await api('/agentvault/advice',{topic:get('topic').value});get('answer').textContent=r.answer;});
load().then(()=>{get('notice').textContent='Private dashboard ready. Production sales are closed.';}).catch(e=>{get('notice').textContent=e.message;});
setInterval(()=>{if(!busy&&!document.hidden&&!['TEXTAREA','INPUT','SELECT'].includes(document.activeElement?.tagName))load().catch(e=>{get('notice').textContent=e.message;});},60000);
