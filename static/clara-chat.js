/* Focused installable client: private chat, voice and optional still-camera questions. */
'use strict';
const el=id=>document.getElementById(id);
const voice=AgentBrokerVoice.init(document,window);
const camera=AgentBrokerCamera.init(document,window);
let busy=false, attachedDocument=null, uploadingDocument=false;
async function api(path,body) {
  const response=await fetch(path,{method:body===undefined?'GET':'POST',cache:'no-store',headers:{'Content-Type':'application/json','X-AgentBroker-Request':'1'},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) {if(response.status===401){el('private-ui').hidden=true;el('login-form').hidden=false;voice.halt();camera.close();}throw new Error(data.error||'تعذر الاتصال / Request failed');}
  return data;
}
function render(data) {
  const container=el('companion-messages');container.replaceChildren();
  for(const message of data.messages||[]) {
    const card=document.createElement('article');card.className='message '+message.role;card.dir='auto';
    const label=document.createElement('strong');label.textContent=message.role==='user'?(/[\u0621-\u064a]/.test(message.content)?'أنت':'You'):'Clara';
    const text=document.createElement('p');text.textContent=message.content;card.append(label,text);
    if(message.role==='assistant'){const listen=document.createElement('button');listen.type='button';listen.textContent='🔊 اسمع / Listen';listen.onclick=()=>voice.speak(message.content);card.append(listen);}
    container.append(card);
  }
  container.scrollTop=container.scrollHeight;
  el('companion-status').textContent=data.status==='free_model_unavailable'?'النموذج غير متاح حالياً. / Model unavailable.':'';
}
async function advisor() {try{const data=await api('/companion/advisor/status');el('advisor-status').textContent='المراجع المحفوظة: '+data.documents.length+' · معلوماتك الخاصة: '+data.profile_entries+' · رسائل محفوظة: '+data.archived_messages+' · دوام التخزين ونفاذ النصوص غير متحققين.';}catch(_) {}}
async function loginStatus() {
  const data=await api('/session/status');
  el('private-ui').hidden=!data.authenticated;el('login-form').hidden=data.authenticated;el('logout').hidden=!data.authenticated;
  if(data.authenticated){render(await api('/companion/messages'));advisor();}
}
el('login-form').onsubmit=async event=>{event.preventDefault();try{await api('/session/login',{secret:el('login-secret').value});el('login-status').textContent='';await loginStatus();}catch(error){el('login-status').textContent=error.message;}finally{el('login-secret').value='';}};
el('logout').onclick=async()=>{voice.halt();camera.close();camera.clear();await api('/session/logout',{});await loginStatus();};
el('companion-form').onsubmit=async event=>{
  event.preventDefault();const field=el('companion-input');if(busy||uploadingDocument||!field.value.trim())return;
  if(camera.frame()&&voice.active()&&!event.submitter){voice.failed('اضغط إرسال يدوياً لإرسال اللقطة. / Tap Send manually to share the image.');return;}
  if(attachedDocument && camera.frame()){voice.failed('أرسل الوثيقة والصورة بطلبين منفصلين. / Send the document and image separately.');return;}
  busy=true;el('companion-send').disabled=true;field.readOnly=true;voice.thinking(true);el('companion-status').textContent='';
  try {
    const data=attachedDocument
      ? await api('/companion/files/'+attachedDocument.id+'/work',{instruction:field.value,action:el('document-action').value})
      : await api('/companion/messages',{content:field.value,reply_language:'auto',tone:el('companion-tone').value,camera_image:camera.frame()});
    field.value='';camera.clear();render(data);voice.thinking(false);
    if(data.download){
      const link=document.createElement('a');link.href=data.download;link.className='download-link';link.textContent='تنزيل النسخة المعدّلة / Download edited copy';
      el('companion-messages').append(link);
      const review=document.createElement('details'),title=document.createElement('summary');title.textContent='التغييرات / Changes';review.append(title);
      for(const edit of data.edits||[]){const text=document.createElement('p');text.dir='auto';text.textContent=edit.old+' → '+edit.new;review.append(text);}el('companion-messages').append(review);
      el('companion-status').textContent='الأصل محفوظ؛ راجع المحتوى والتنسيق قبل الاعتماد. / Original preserved; review content and layout.';
    }
    const last=(data.messages||[]).at(-1);
    if(last&&last.role==='assistant'&&(voice.active()||el('companion-autospeak').checked))voice.speak(last.content);
  }catch(error){voice.thinking(false);voice.failed(error.message);el('companion-status').textContent=error.message;}
  finally{busy=false;el('companion-send').disabled=false;field.readOnly=false;}
};
el('profile-import').onclick=async function(){const file=el('profile-file').files[0];if(!file)return;if(file.size>100000){el('advisor-status').textContent='الملف كبير جداً.';return;}this.disabled=true;try{const data=JSON.parse(await file.text());await api('/companion/profile',{confirm_private_import:true,entries:data.entries});el('profile-file').value='';await advisor();}catch(error){el('advisor-status').textContent=error.message;}finally{this.disabled=false;}};
loginStatus().catch(error=>{el('login-status').textContent=error.message;});

el('history-export').onclick=async function(){this.disabled=true;try{let after=0,rows=[],more=true;while(more){const page=await api('/companion/history/export?after='+after);rows.push(...page.messages);more=page.has_more;after=page.next_after;if(!after)break;}const blob=new Blob([JSON.stringify({version:1,messages:rows},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='Clara-private-chat.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){el('advisor-status').textContent=error.message;}finally{this.disabled=false;}};

el('companion-attach').onclick=()=>el('document-file').click();
el('document-file').onchange=async()=>{
 const file=el('document-file').files[0];if(!file||uploadingDocument)return;uploadingDocument=true;el('companion-attach').disabled=true;
 el('document-panel').hidden=false;el('document-status').textContent='جاري قراءة الوثيقة… / Reading…';
 attachedDocument=null;el('companion-send').disabled=true;
 try{
  if(file.size>1800000)throw new Error('الحد 1.8 MB؛ أرسل جزءاً من الملف. / Upload a section under 1.8 MB.');
  const form=new FormData();form.append('file',file);
  const response=await fetch('/companion/files',{method:'POST',headers:{'X-AgentBroker-Request':'1'},body:form});
  const data=await response.json();if(!response.ok)throw new Error(data.error||'Upload failed');
  attachedDocument=data;el('document-status').textContent=data.name+' · '+data.characters+' حرف';el('document-preview').textContent=data.preview;
  el('document-action').querySelector('option[value="edit"]').disabled=data.kind==='pdf';el('document-action').value=data.kind==='pdf'?'review':'edit';
  el('companion-input').focus();
 }catch(error){el('document-status').textContent=error.message;}
 finally{uploadingDocument=false;el('companion-attach').disabled=false;el('companion-send').disabled=busy;el('document-file').value='';}
};
el('document-remove').onclick=()=>{attachedDocument=null;el('document-preview').textContent='';el('document-panel').hidden=true;};
