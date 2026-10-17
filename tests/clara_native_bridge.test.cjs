const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const commands = [], events = [];
const window = {webkit:{messageHandlers:{clara:{postMessage:body=>commands.push(body)}}}, document:{dispatchEvent:e=>events.push(e.type)}, Event:class {constructor(type){this.type=type;}}};
vm.runInNewContext(fs.readFileSync('ios/Clara/NativeBridge.js','utf8'), {window});
const bridge = window.ClaraNativeSpeech;
assert.equal(commands[0].action, 'voices');
let changed = 0;
bridge.speechSynthesis.addEventListener('voiceschanged', ()=>changed++);
bridge._receive({type:'voices', voices:[{voiceURI:'salma',lang:'ar-JO',name:'Salma Female Enhanced'}]});
assert.equal(changed,1);assert.equal(bridge.speechSynthesis.getVoices()[0].voiceURI,'salma');
let started = 0, text = '', final = false, ended = 0;
const input = new bridge.Recognition();input.lang='ar-JO';input.onstart=()=>started++;input.onresult=e=>{text=e.results[0][0].transcript;final=e.results[0].isFinal;};input.onend=()=>ended++;
input.start();const id=commands.at(-1).id;
assert.equal(commands.at(-1).language,'ar-JO');
assert.throws(()=>new bridge.Recognition().start(), /already active/);
bridge._receive({type:'recognitionResult',id:id+1,text:'stale',final:true});assert.equal(text,'');
bridge._receive({type:'recognitionStart',id});assert.equal(started,1);
bridge._receive({type:'recognitionResult',id,text:'مرحبا',final:false});assert.equal(text,'مرحبا');assert.equal(final,false);
input.stop();assert.equal(commands.at(-1).action,'finishRecognition');assert.equal(ended,0);
bridge._receive({type:'recognitionResult',id,text:'مرحبا كلارا',final:true});assert.equal(final,true);
bridge._receive({type:'recognitionEnd',id});assert.equal(ended,1);
input.start();const canceled=commands.at(-1).id;input.abort();assert.equal(ended,2);
bridge._receive({type:'recognitionResult',id:canceled,text:'late',final:true});assert.equal(text,'مرحبا كلارا');
let speechStart=0,speechEnd=0;
const utterance=new bridge.Utterance('Hello');utterance.onstart=()=>speechStart++;utterance.onend=()=>speechEnd++;
bridge.speechSynthesis.speak(utterance);const sid=commands.at(-1).id;
bridge._receive({type:'speechStart',id:sid});assert.equal(speechStart,1);
bridge.speechSynthesis.cancel();bridge._receive({type:'speechEnd',id:sid});assert.equal(speechEnd,0);
input.start();bridge._suspend();assert.equal(ended,3);assert.deepEqual(events,['clara-native-pause']);
console.log('Native bridge: voice refresh, Arabic dictation, final/partial results, stale-event isolation, cancellation and background stop passed.');

// Exercise the actual website voice controller using native-only APIs (no Web Speech fallback).
const {init} = require('../static/companion-voice.js');
const elements = {}, handlers = new Map();
const element = () => ({value:'',checked:false,disabled:false,hidden:false,readOnly:false,textContent:'',dataset:{},options:[],append(option){this.options.push(option);},replaceChildren(){this.options=[];}});
const doc = window.document = {
  hidden:false, getElementById(id){return elements[id] ||= element();}, createElement:element,
  addEventListener(name,callback){handlers.set(name,callback);},
  dispatchEvent(event){handlers.get(event.type)?.();}
};
window.localStorage={getItem:()=>null,setItem(){}};
const ui=init(doc,window);let submissions=0;
doc.getElementById('companion-form').requestSubmit=()=>submissions++;
doc.getElementById('companion-call').onclick();
const greeting=commands.at(-1);assert.equal(greeting.action,'speak');assert.match(greeting.text,/I am Clara/);
bridge._receive({type:'speechStart',id:greeting.id});assert.equal(elements['companion-avatar'].dataset.state,'speaking');
bridge._receive({type:'speechEnd',id:greeting.id});const rid=commands.at(-1).id;assert.equal(commands.at(-1).action,'recognize');
bridge._receive({type:'recognitionStart',id:rid});
bridge._receive({type:'recognitionResult',id:rid,text:'Hello Clara',final:true});
bridge._receive({type:'recognitionEnd',id:rid});assert.equal(submissions,1);assert.equal(elements['companion-input'].value,'Hello Clara');
ui.thinking(true);ui.thinking(false);ui.speak('مرحبا يا عمر');
assert.equal(commands.at(-1).language,'ar-JO');
bridge._suspend();assert.equal(ui.active(),false);assert.equal(elements['companion-avatar'].dataset.state,'idle');
console.log('Native integration: actual Clara voice controller greets, listens, submits one final turn, switches Arabic and stops on background.');
