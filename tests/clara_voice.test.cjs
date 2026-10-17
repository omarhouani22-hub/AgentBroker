const assert = require('node:assert/strict');
const {chooseVoice, init} = require('../static/companion-voice.js');
const voices = [{voiceURI:'en-m',name:'Daniel',lang:'en-US'},{voiceURI:'en-f',name:'Samantha',lang:'en-US'},{voiceURI:'ar-f',name:'Salma',lang:'ar-SA'}];
assert.equal(chooseVoice(voices,'ar-JO','en-f').voiceURI,'ar-f');
assert.equal(chooseVoice(voices,'en-US','').voiceURI,'en-f');
assert.equal(chooseVoice([], 'ar-JO', ''), undefined);
function fixture() {
  const elements = {};
  const make = () => ({value:'',checked:false,disabled:false,hidden:false,readOnly:false,textContent:'',dataset:{},options:[],append(option){this.options.push(option);},replaceChildren(){this.options=[];}});
  const doc = {hidden:false,getElementById(id){return elements[id] ||= make();},createElement:make,addEventListener(){}};
  let current, utterance, submissions = 0;
  class Recognition { constructor(){current=this;} start(){this.onstart();} stop(){this.onend();} abort(){this.onend();} }
  const storage = new Map();
  const win = {SpeechRecognition:Recognition,SpeechSynthesisUtterance:class {constructor(text){this.text=text;}},speechSynthesis:{getVoices:()=>voices,addEventListener(){},cancel(){},speak(u){utterance=u;u.onstart();}},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}};
  const ui = init(doc,win);
  doc.getElementById('companion-form').requestSubmit = () => submissions++;
  return {ui,el:id=>doc.getElementById(id),recognition:()=>current,utterance:()=>utterance,submissions:()=>submissions};
}
const f = fixture();
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
