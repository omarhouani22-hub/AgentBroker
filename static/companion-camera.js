/* Preview stays on-device. Only an explicitly attached frame leaves the browser. */
(function(root) {
  'use strict';
  function init(doc,win) {
    const get=id=>doc.getElementById(id);
    const button=get('companion-camera'), panel=get('camera-panel'), video=get('camera-preview');
    const stop=get('camera-stop'), attach=get('camera-attach'), discard=get('camera-discard');
    const preview=get('camera-snapshot'), status=get('camera-status');
    let stream=null, frame=null, generation=0;
    function clear() { frame=null; preview.removeAttribute('src'); preview.hidden=true; discard.hidden=true; }
    function close() {
      generation++;
      if(stream) stream.getTracks().forEach(t=>t.stop());
      stream=null;video.srcObject=null;video.hidden=true;stop.hidden=true;attach.hidden=true;
      button.disabled=false; button.textContent='📷 كاميرا / Camera';
    }
    button.onclick=async()=>{
      if(stream) { close(); return; }
      const current=++generation;
      if(!win.navigator.mediaDevices || !win.navigator.mediaDevices.getUserMedia) { status.textContent='الكاميرا غير متاحة هنا؛ افتح الموقع في متصفح يدعمها. / Camera unavailable.';panel.hidden=false;return; }
      button.disabled=true;panel.hidden=false;
      try {
        const camera=await win.navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:768},height:{ideal:768}},audio:false});
        if(current!==generation || doc.hidden) { camera.getTracks().forEach(t=>t.stop());return; }
        stream=camera;video.srcObject=stream;video.hidden=false;stop.hidden=false;attach.hidden=false;
        await video.play();button.textContent='📷 الكاميرا مفعلة / Camera on';
        status.textContent='معاينة على جهازك فقط. «إرفاق لقطة» ثم «إرسال» يرسل صورة واحدة إلى نموذج OpenRouter المجاني. الصورة لا تُحفظ في سجل AgentBroker. / Local preview only; attach and send shares one image with the free model via OpenRouter, without saving image bytes in chat history.';
      } catch(_) { close();status.textContent='تعذر تشغيل الكاميرا؛ راجع إذن الكاميرا في المتصفح. / Check camera permission.'; }
      finally { button.disabled=false; }
    };
    attach.onclick=()=>{
      if(!stream || !video.videoWidth) {status.textContent='انتظر ظهور المعاينة. / Wait for the preview.';return;}
      const canvas=doc.createElement('canvas');
      const scale=Math.min(1,768/video.videoWidth,768/video.videoHeight);
      canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
      canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
      frame=canvas.toDataURL('image/jpeg',0.7);preview.src=frame;preview.hidden=false;discard.hidden=false;
      close();status.textContent='لقطة جاهزة للمراجعة. اكتب سؤالك ثم أرسل، أو احذفها. / Review this still image, then type your question and send, or remove it.';
      get('companion-input').focus();
    };
    stop.onclick=close;discard.onclick=clear;
    doc.addEventListener('visibilitychange',()=>{if(doc.hidden)close();});
    return {frame:()=>frame,clear,close};
  }
  root.AgentBrokerCamera={init};
})(window);
