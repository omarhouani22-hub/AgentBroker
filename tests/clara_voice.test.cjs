const assert = require('node:assert/strict');
const {chooseVoice, init} = require('../static/companion-voice.js');
const voices = [{voiceURI:'en-m',name:'Daniel',lang:'en-US'},{voiceURI:'en-f',name:'Samantha',lang:'en-US'},{voiceURI:'ar-f',name:'Salma',lang:'ar-SA'}];
assert.equal(chooseVoice(voices,'ar-JO','en-f').voiceURI,'ar-f');
assert.equal(chooseVoice(voices,'en-US','').voiceURI,'en-f');
assert.equal(chooseVoice([], 'ar-JO', ''), undefined);
function fixture(useTimers=false,useNatural=false,useLocal=false) {
  let timerId=0;const timers=new Map();
  const elements = {};
  const make = () => ({value:'',checked:false,disabled:false,hidden:false,readOnly:false,textContent:'',dataset:{},options:[],append(option){this.options.push(option);},replaceChildren(){this.options=[];}});
  const doc = {hidden:false,getElementById(id){return elements[id] ||= make();},createElement:make,addEventListener(){}};
  let current, utterance, submissions = 0;
  class Recognition { constructor(){current=this;} start(){this.onstart();} stop(){this.onend();} abort(){this.onend();} }
  const storage = new Map();
  const win = {SpeechRecognition:Recognition,SpeechSynthesisUtterance:class {constructor(text){this.text=text;}},speechSynthesis:{getVoices:()=>voices,addEventListener(){},cancel(){},speak(u){utterance=u;if(u.onstart)u.onstart();}},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}};
  if(useLocal)win.ClaraInternalMic={enabled:true};
  if(useTimers){win.setTimeout=fn=>{timers.set(++timerId,fn);return timerId;};win.clearTimeout=id=>timers.delete(id);}
  let naturalHooks;
  if(useNatural)win.ClaraNaturalVoice={init(){return {selected:()=>true,stop(){},refresh:async()=>{},play(text,hooks){naturalHooks=hooks;}};}};
  const ui = init(doc,win);
  doc.getElementById('companion-form').requestSubmit = () => submissions++;
  return {naturalHooks:()=>naturalHooks,tick(){const jobs=[...timers.values()];timers.clear();jobs.forEach(fn=>fn());},ui,el:id=>doc.getElementById(id),recognition:()=>current,utterance:()=>utterance,submissions:()=>submissions};
}
const f = fixture();
assert.equal(f.el('companion-mic-language').value,'en-US');
f.el('companion-mic-language').value='ar-JO';
f.el('companion-mic').onclick();
assert.equal(f.recognition().lang,'ar-JO');
assert.equal(f.el('companion-avatar').dataset.state,'listening');
function event(text, final=true){return {results:[Object.assign([{transcript:text}],{isFinal:final})]};}
f.recognition().onresult(event('مرحبا'));
f.recognition().onresult(event('مرحبا كيفك'));
assert.equal(f.el('companion-input').value,'مرحبا كيفك'); // not appended twice
f.recognition().onend();
assert.equal(f.submissions(),0); // dictation requires review
assert.equal(f.el('companion-input').readOnly,false);
f.el('companion-input').value='';
f.el('companion-voice-mode').checked=true;
f.el('companion-voice-mode').onchange();
assert.equal(f.utterance().text,'I am Clara, your AI assistant. What do you wanna talk about?');
assert.equal(f.utterance().voice.name,'Samantha');
f.utterance().onend();
assert.equal(f.recognition().lang,'ar-JO'); // greeting must not change chosen microphone
f.recognition().onresult(event('بدي مثال'));
f.recognition().onend();
assert.equal(f.submissions(),1);
f.ui.thinking(true);
assert.equal(f.el('companion-avatar').dataset.state,'thinking');
f.ui.thinking(false); f.ui.speak('أكيد، خلينا نحكي.');
assert.equal(f.utterance().voice.name,'Salma');
assert.equal(f.el('companion-avatar').dataset.state,'speaking');
f.utterance().onend();
assert.equal(f.el('companion-avatar').dataset.state,'listening');
f.el('companion-stop').onclick();
assert.equal(f.ui.active(),false);
assert.equal(f.submissions(),1); // Stop cannot send an unfinished recording
assert.equal(f.el('companion-avatar').dataset.state,'idle');
const g=fixture();g.el('companion-voice-mode').checked=true;g.el('companion-mic').onclick();
g.recognition().onerror({error:'not-allowed'});g.recognition().onend();
assert.equal(g.ui.active(),false);assert.equal(g.submissions(),0);
assert.match(g.el('companion-voice-status').textContent,/Allow microphone/);
console.log('Clara voice: language, transcript, female voices, greeting, turn-taking, stop and permission checks passed.');

const en = fixture(); en.el('companion-mic-language').value='en-US'; en.el('companion-voice-mode').checked=true; en.el('companion-voice-mode').onchange(); assert.equal(en.utterance().text, 'I am Clara, your AI assistant. What do you wanna talk about?'); assert.equal(en.utterance().voice.name,'Samantha');

// Long replies are chunked, keep their language, and resume listening only once.
const long = fixture(); long.el('companion-voice-mode').checked=true;
long.ui.speak('This is a spoken sentence. '.repeat(30));
let count=0;
while(long.el('companion-avatar').dataset.state==='speaking') {
  assert.ok(long.utterance().text.length<=180);
  assert.equal(long.utterance().voice.name,'Samantha');
  long.utterance().onend(); if(++count>20)throw new Error('Speech did not finish');
}
assert.ok(count>1);assert.equal(long.el('companion-avatar').dataset.state,'listening');
const retry=fixture();retry.ui.remember('Hello Omar.');retry.el('companion-avatar').onclick();
assert.equal(retry.utterance().text,'Hello Omar.');retry.utterance().onerror({error:'not-allowed'});
assert.equal(retry.el('companion-avatar').dataset.state,'idle');
assert.match(retry.el('companion-voice-status').textContent,/Tap Clara or Replay/);
retry.el('companion-avatar').onclick();assert.equal(retry.el('companion-avatar').dataset.state,'speaking');
retry.ui.halt();const stopped=retry.utterance();stopped.onend();assert.equal(retry.ui.active(),false);
const ar=fixture();ar.ui.speak('مرحبا يا عمر');assert.equal(ar.utterance().lang,'ar-JO');assert.equal(ar.utterance().voice.name,'Salma');
const unlock=fixture();unlock.ui.unlock();unlock.ui.speak('English voice works.');assert.equal(unlock.utterance().voice.name,'Samantha');
console.log('Mobile voice: English default, chunking, explicit replay, blocked audio and gesture unlock checks passed.');

const call=fixture();call.el('companion-call').onclick();
assert.equal(call.ui.active(),true);assert.equal(call.utterance().text,'I am Clara, your AI assistant. What do you wanna talk about?');
assert.match(call.el('companion-call').textContent,/End call/);call.utterance().onend();
assert.equal(call.el('companion-avatar').dataset.state,'listening');call.el('companion-call').onclick();
assert.equal(call.ui.active(),false);assert.equal(call.el('companion-avatar').dataset.state,'idle');
assert.match(call.el('companion-call').textContent,/Start call/);
console.log('Call controls: start, greeting, listen and end checks passed.');

const partial=fixture();partial.el('companion-mic').onclick();partial.recognition().onresult(event('قربي مني',false));partial.recognition().onend();assert.equal(partial.el('companion-input').value,'قربي مني');assert.equal(partial.submissions(),0);assert.match(partial.el('companion-voice-status').textContent,/partial transcript/);
const quiet=fixture(true);quiet.el('companion-voice-mode').checked=true;quiet.el('companion-mic').onclick();
quiet.recognition().onerror({error:'no-speech'});quiet.recognition().onend();assert.equal(quiet.ui.active(),true);const old=quiet.recognition();quiet.tick();assert.notEqual(quiet.recognition(),old);assert.equal(quiet.el('companion-avatar').dataset.state,'listening');
quiet.recognition().onerror({error:'no-speech'});quiet.recognition().onend();quiet.ui.halt();quiet.tick();assert.equal(quiet.ui.active(),false);assert.equal(quiet.el('companion-avatar').dataset.state,'idle');
assert.equal(chooseVoice([...voices,{voiceURI:'en-premium',name:'Samantha Premium',lang:'en-US'}],'en-US','').voiceURI,'en-premium');
console.log('Listening recovery: partial transcript preservation, bounded silence restart, Stop cancellation and enhanced voice preference passed.');
const unavailable=fixture();unavailable.el('companion-voice-mode').checked=true;
unavailable.ui.failed('وصلتني رسالتك لكن المزوّد وصل لحد الاستخدام.',true);
assert.equal(unavailable.ui.active(),false);assert.equal(unavailable.utterance().lang,'ar-JO');
assert.match(unavailable.el('companion-voice-status').textContent,/حد الاستخدام/);
unavailable.utterance().onend();assert.equal(unavailable.el('companion-avatar').dataset.state,'idle');assert.equal(unavailable.recognition(),undefined);
console.log('Provider notice: spoken in the error language, remains visible, and never restarts the call.');

const blockedCall=fixture(false,true);blockedCall.el('companion-call').onclick();
blockedCall.naturalHooks().onblocked();
assert.equal(blockedCall.ui.active(),true);
assert.equal(blockedCall.recognition(),undefined); // Never listen while playback needs a gesture.
assert.match(blockedCall.el('companion-voice-status').textContent,/Tap Play/);
blockedCall.naturalHooks().onstart();blockedCall.naturalHooks().onend();
assert.equal(blockedCall.el('companion-avatar').dataset.state,'listening');
blockedCall.ui.speak('Another reply.');const staleHooks=blockedCall.naturalHooks();
staleHooks.onblocked();blockedCall.el('companion-call').onclick();
staleHooks.onstart();staleHooks.onend();assert.equal(blockedCall.ui.active(),false);
assert.equal(blockedCall.el('companion-avatar').dataset.state,'idle');
// A failing local Piper voice must fall back to free device speech on iPhone.
const localFallback=fixture(false,true,true);
localFallback.ui.speak('Clara is ready.');
localFallback.naturalHooks().onerror();
assert.equal(localFallback.utterance().text,'Clara is ready.');
assert.equal(localFallback.el('clara-voice-engine').value,'device');
assert.match(localFallback.el('natural-voice-status').textContent,/Switched to device voice/);
const localUnavailable=fixture(false,false,true);
localUnavailable.ui.speak('Device fallback is ready.');
assert.equal(localUnavailable.utterance().text,'Device fallback is ready.');
console.log('Local speech recovery: internal voice failure or unavailability falls back to device voice.');
console.log('Natural call recovery: manual Play resumes listening; End call cancels stale callbacks.');
