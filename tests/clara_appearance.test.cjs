const assert=require('node:assert/strict');
const {parseRequest,init}=require('../static/clara-appearance.js');
assert.deepEqual(parseRequest('Change to the beach'),{scene:'beach'});
assert.deepEqual(parseRequest('خلينا بالمطبخ'),{scene:'kitchen'});
assert.deepEqual(parseRequest('Change to the bedroom and wear a summer dress'),{scene:'bedroom',outfit:'summer'});
assert.deepEqual(parseRequest('Come closer'),{motion:'approach'});
assert.deepEqual(parseRequest('قربي شوي'),{motion:'approach'});
assert.deepEqual(parseRequest('Step back'),{motion:'step_back'});
assert.deepEqual(parseRequest('Stand up'),{pose:'standing',outfit:'business'});
assert.deepEqual(parseRequest('Be frisky'),{tone:'frisky'});
for(const query of ['What is a kitchen?','My bedroom is small',"Don't change to the beach",'لا تغيري المطبخ','Take your clothes off'])assert.deepEqual(parseRequest(query),{});
const elements={};
function select(values){let current=values[0];return {options:values.map(v=>({value:v,textContent:v})),get value(){return current;},set value(v){current=v;},get selectedIndex(){return values.indexOf(current);}};}
elements['clara-scene']=select(['studio','kitchen','bedroom','beach']);elements['clara-outfit']=select(['business','casual','summer','shorts']);elements['clara-framing']=select(['wide','medium','close']);elements['clara-pose']=select(['seated','standing']);elements['clara-call-stage']={dataset:{}};elements['appearance-status']={textContent:''};elements['companion-tone']=select(['auto','playful','frisky','funny','serious']);
const storage=new Map([['clara-scene','https://evil.test'],['clara-framing','close']]);
const ui=init({getElementById:id=>elements[id]},{localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}});
assert.equal(ui.value().scene,'studio');ui.request('Change to the beach and wear casual clothes');assert.equal(ui.value().scene,'beach');assert.equal(ui.value().outfit,'casual');
ui.request('Stand up');assert.equal(ui.value().pose,'standing');assert.equal(ui.value().outfit,'business');ui.request('Come closer');assert.equal(ui.value().framing,'close');ui.request('Step back');assert.equal(ui.value().framing,'wide');
ui.request('Wear a summer dress');assert.equal(ui.value().pose,'seated');assert.equal(ui.value().outfit,'summer');ui.request('Be frisky');assert.equal(elements['companion-tone'].value,'frisky');
console.log('Appearance: explicit English/Arabic commands, no incidental switches, safe presets, pose/framing and persistence passed.');

for(const text of ['Come here','Come closer to me','Clara, come closer','Can you come closer?','تعالي لعندي','قربي مني','كلارا، تعالي'])assert.equal(parseRequest(text).motion,'approach',text);
const before=ui.value();for(let i=0;i<8;i++){ui.advance();assert.deepEqual(ui.value(),before);}
console.log('Appearance initialization and ordinary replies retain the exact selected look.');
const stored=new Map([['clara-scene','beach'],['clara-outfit','summer'],['clara-pose','seated'],['clara-framing','medium']]);
const restored=init({getElementById:id=>elements[id]},{localStorage:{getItem:k=>stored.get(k),setItem:(k,v)=>stored.set(k,v)}});
assert.deepEqual(restored.value(),{scene:'beach',outfit:'summer',pose:'seated',framing:'medium'});
assert.equal(elements['clara-outfit'].disabled,undefined);
