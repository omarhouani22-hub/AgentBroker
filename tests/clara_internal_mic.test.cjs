const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let processor,stopped=0,closed=0,posts=[];
class Context{
 constructor(){this.sampleRate=16000;this.destination={};}
 resume(){return Promise.resolve();}close(){closed++;return Promise.resolve();}
 createMediaStreamSource(){return {connect(){},disconnect(){}};}
 createScriptProcessor(){processor={connect(){},disconnect(){},onaudioprocess:null};return processor;}
 createGain(){return {gain:{value:1},connect(){},disconnect(){}};}
}
const window={document:{documentElement:{dataset:{localOnly:'true'}}},navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){stopped++;}}]})}},AudioContext:Context,AbortController,
 setTimeout(){return 1;},clearTimeout(){},fetch:async(path,options)=>{posts.push({path,options});return {ok:true,json:async()=>path.endsWith('/status')?{enabled:true,recognition_available:true}:{text:'hello clara'}};}};
vm.runInNewContext(fs.readFileSync('static/clara-internal-mic.js','utf8'),{window,Blob});
(async()=>{
 const api=window.ClaraInternalMic;assert.equal(api.enabled,true);await api.refresh();assert.equal(api.available,true);
 const input=new api.Recognition();let text='',ended=0;input.onresult=e=>{text=e.results[0][0].transcript;assert.equal(e.results[0].isFinal,true);};input.onend=()=>ended++;
 await input.start();processor.onaudioprocess({inputBuffer:{getChannelData:()=>new Float32Array(4096).fill(.1)}});
 await input.stop();assert.equal(text,'hello clara');assert.equal(ended,1);assert.equal(stopped,1);assert.equal(closed,1);
 const post=posts.find(x=>x.path==='/companion/transcribe');assert.equal(post.options.headers['X-AgentBroker-Request'],'1');
 const wav=new DataView(await post.options.body.arrayBuffer());assert.equal(wav.getUint32(24,true),16000);assert.equal(wav.getUint16(22,true),1);assert.equal(wav.getUint32(40,true),8192);
 assert(posts.every(x=>x.path.startsWith('/companion/')));
 const active=new api.Recognition();await active.start();active.abort();assert.equal(stopped,2);assert.equal(active.active,false);
 console.log('Internal microphone: same-origin PCM capture, final transcript, track release and cancellation passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
