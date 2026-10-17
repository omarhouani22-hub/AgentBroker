const assert=require('node:assert/strict');
global.window={};require('../static/companion-camera.js');
async function run(){
 const elements={};let requested=0,stopped=0;
 const make=()=>({hidden:true,disabled:false,textContent:'',value:'',videoWidth:1280,videoHeight:720,removeAttribute(k){delete this[k];},focus(){},async play(){}});
 const doc={hidden:false,getElementById(id){return elements[id] ||= make();},createElement(){return {getContext(){return {drawImage(){}};},toDataURL(){return 'data:image/jpeg;base64,test-frame';}};},addEventListener(){}};
 const stream={getTracks:()=>[{stop(){stopped++;}}]};
 const win={navigator:{mediaDevices:{async getUserMedia(constraints){requested++;assert.equal(constraints.audio,false);return stream;}}}};
 const camera=window.AgentBrokerCamera.init(doc,win);
 assert.equal(requested,0);assert.equal(camera.frame(),null);
 await elements['companion-camera'].onclick();assert.equal(requested,1);
 assert.equal(elements['camera-preview'].srcObject,stream);assert.equal(camera.frame(),null);
 elements['camera-attach'].onclick();assert.equal(camera.frame(),'data:image/jpeg;base64,test-frame');
 assert.equal(stopped,1);assert.equal(elements['camera-snapshot'].hidden,false);
 assert.equal(elements['camera-preview'].srcObject,null);
 camera.clear();assert.equal(camera.frame(),null);assert.equal(elements['camera-snapshot'].src,undefined);
 console.log('Clara camera: opt-in video only, local preview, single still, stopped tracks and removal passed.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
