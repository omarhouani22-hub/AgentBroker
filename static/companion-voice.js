/* Browser speech is optional. No paid audio service or always-on microphone. */
(function (root) {
  'use strict';
  const isArabic = text => /[\u0621-\u064a]/.test(text);
  const femaleNames = /samantha|karen|moira|tessa|victoria|ava|allison|sara|salma|hoda|zeina|laila|layla|fatima|aisha|zira|jenny|aria|yasmin|mariam|female|أنثى/i;
  function chooseVoice(voices, language, preferred) {
    const matching = voices.filter(v => v.lang.toLowerCase().startsWith(language.slice(0, 2).toLowerCase()));
    return matching.find(v => v.voiceURI === preferred) || matching.find(v => femaleNames.test(v.name)) || matching[0];
  }
  function init(doc, win) {
    const get = id => doc.getElementById(id);
    const mic = get('companion-mic'), stop = get('companion-stop'), field = get('companion-input');
    const mode = get('companion-voice-mode'), language = get('companion-mic-language');
    const status = get('companion-voice-status'), transcript = get('companion-transcript');
    const avatar = get('companion-avatar'), avatarStatus = get('avatar-status');
    const voiceSelect = get('companion-voice'), voiceHelp = get('companion-voice-help');
    const SpeechInput = win.SpeechRecognition || win.webkitSpeechRecognition;
    const synth = win.speechSynthesis;
    let recognition = null, speaking = false, thinking = false, session = 0, preferred = '', greeted = false;
    function save(key, value) { try { win.localStorage.setItem(key, value); } catch (_) {} }
    function read(key) { try { return win.localStorage.getItem(key); } catch (_) { return null; } }
    language.value = read('agentbroker-mic-language') === 'en-US' ? 'en-US' : 'ar-JO';
    preferred = read('agentbroker-voice') || '';
    function state(value) {
      avatar.dataset.state = value;
      const en = language.value === 'en-US';
      avatarStatus.textContent = ({idle:en?'Ready to chat':'جاهزة للحوار',listening:en?'Listening…':'بسمعك…',thinking:en?'Preparing a reply…':'بجهّز الرد…',speaking:en?'Speaking…':'بحكي معك…'})[value];
      stop.hidden = value === 'idle' && !mode.checked;
    }
    function updateVoices() {
      const voices = synth ? synth.getVoices() : [];
      voiceSelect.replaceChildren();
      const auto = doc.createElement('option'); auto.value = ''; auto.textContent = 'صوت نسائي إن توفر / Female voice when available'; voiceSelect.append(auto);
      for (const voice of voices.filter(v => /^(ar|en)(-|$)/i.test(v.lang))) {
        const option = doc.createElement('option'); option.value = voice.voiceURI; option.textContent = voice.name + ' · ' + voice.lang; voiceSelect.append(option);
      }
      voiceSelect.value = [...voiceSelect.options].some(o => o.value === preferred) ? preferred : '';
      voiceHelp.textContent = 'الأصوات حسب جهازك؛ الاختيار تلقائي حسب لغة الرد. / Voices depend on your device and follow the reply language.';
    }
    voiceSelect.onchange = () => { preferred = voiceSelect.value; save('agentbroker-voice', preferred); };
    function halt() {
      mode.checked = false; session++; speaking = false;
      if (recognition) recognition.abort();
      if (synth) synth.cancel();
      state(thinking ? 'thinking' : 'idle');
    }
    function listen() {
      if (!SpeechInput || thinking || doc.hidden) return;
      if (recognition) { recognition.stop(); return; }
      session++; const active = session;
      if (synth) synth.cancel(); speaking = false;
      const input = new SpeechInput(); recognition = input;
      const original = field.value.trim(); let heard = '', failed = false;
      // Auto reply language cannot identify untranscribed audio. Choose input explicitly.
      input.lang = language.value;
      input.continuous = false; input.interimResults = true; input.maxAlternatives = 1;
      field.readOnly = true; language.disabled = true;
      input.onstart = () => { if (active === session) { state('listening'); mic.textContent = 'إنهاء الاستماع / Finish'; status.textContent = 'بسمعك… / Listening…'; } };
      input.onresult = event => {
        if (active !== session) return;
        heard = ''; let interim = '';
        // results includes earlier finals: rebuild rather than append duplicates.
        for (const result of Array.from(event.results)) {
          if (result.isFinal) heard += result[0].transcript + ' ';
          else interim += result[0].transcript + ' ';
        }
        field.value = [original, heard.trim()].filter(Boolean).join(' ').slice(0, 2000);
        transcript.textContent = interim.trim();
        field.dir = isArabic(field.value || interim) ? 'rtl' : 'ltr';
      };
      input.onerror = event => {
        if (active !== session) return;
        failed = true; mode.checked = false;
        const errors = {'not-allowed':'اسمح بالمايك من إعدادات المتصفح. / Allow microphone access in browser settings.', 'service-not-allowed':'التعرف الصوتي غير متاح هنا؛ استخدم إملاء لوحة المفاتيح. / Use keyboard dictation.', 'audio-capture':'المايك غير متاح؛ تحقق من توصيله. / Check your microphone.', 'no-speech':'ما سمعت كلام؛ اضغط المايك وجرب مجدداً. / No speech heard; tap the microphone to retry.', 'network':'تعذر الاتصال بخدمة الصوت؛ استخدم إملاء لوحة المفاتيح. / Speech service connection failed.'};
        status.textContent = errors[event.error] || 'تعذر سماع الكلام؛ راجع لغة المايك أو استخدم إملاء لوحة المفاتيح. / Check the mic language or use keyboard dictation.';
      };
      input.onend = () => {
        if (recognition === input) recognition = null;
        field.readOnly = thinking; language.disabled = false; transcript.textContent = '';
        mic.textContent = '🎤 احكي / Speak';
        if (active !== session) return;
        state('idle');
        if (!failed && heard.trim()) {
          status.textContent = mode.checked ? 'جاري إرسال كلامك… / Sending…' : 'راجع الكلام ثم اضغط إرسال. / Review the transcript, then Send.';
          if (mode.checked) get('companion-form').requestSubmit();
        } else if (!failed) {
          mode.checked = false;
          status.textContent = 'ما وصل نص واضح؛ جرّب مجدداً. / No clear transcript; try again.';
        }
      };
      try { state('listening'); input.start(); }
      catch (_) { recognition = null; field.readOnly = false; language.disabled = false; halt(); status.textContent = 'تعذر تشغيل المايك؛ استخدم إملاء لوحة المفاتيح. / Use keyboard dictation.'; }
    }
    function speak(content, keepInputLanguage = false) {
      if (!synth || !win.SpeechSynthesisUtterance) {
        mode.checked = false; status.textContent = 'الصوت غير مدعوم هنا. / Speech playback unavailable.'; state('idle'); return;
      }
      session++; const active = session;
      if (recognition) recognition.abort();
      synth.cancel();
      const utterance = new win.SpeechSynthesisUtterance(content);
      utterance.lang = isArabic(content) ? 'ar-JO' : 'en-US';
      const selected = chooseVoice(synth.getVoices(), utterance.lang, preferred);
      if (selected) utterance.voice = selected;
      if (mode.checked && !keepInputLanguage) { language.value = isArabic(content) ? 'ar-JO' : 'en-US'; save('agentbroker-mic-language', language.value); }
      utterance.rate = 1;
      utterance.onstart = () => { if (active === session) { speaking = true; state('speaking'); status.textContent = ''; } };
      utterance.onend = () => {
        if (active !== session) return;
        speaking = false; state('idle');
        if (mode.checked && !doc.hidden) listen();
      };
      utterance.onerror = () => {
        if (active !== session) return;
        speaking = false; mode.checked = false; state('idle');
        status.textContent = 'تعذر تشغيل الصوت؛ اضغط اسمع لإعادة المحاولة. / Audio failed; tap Listen to retry.';
      };
      synth.speak(utterance);
    }
    mic.onclick = listen;
    stop.onclick = () => { halt(); status.textContent = 'توقفت المحادثة الصوتية. / Voice conversation stopped.'; };
    mode.onchange = () => {
      if (!mode.checked) { halt(); return; }
      if (!synth) { halt(); status.textContent = 'الصوت غير مدعوم هنا. / Speech playback unavailable.'; return; }
      if (!greeted) { greeted = true; speak('I am Clara, your AI assistant. What do you wanna talk about?', true); }
      else listen();
    };
    language.onchange = () => { save('agentbroker-mic-language', language.value); state('idle'); };
    doc.addEventListener('visibilitychange', () => { if (doc.hidden) halt(); });
    if (!SpeechInput) { mic.disabled = true; mode.disabled = true; status.textContent = 'استخدم مايك لوحة المفاتيح؛ التعرف الصوتي غير مدعوم بهذا المتصفح. / Use keyboard dictation in this browser.'; }
    if (synth && synth.addEventListener) synth.addEventListener('voiceschanged', updateVoices);
    updateVoices(); state('idle');
    return {speak, halt, active:() => mode.checked, thinking(value) { thinking = value; if (value) { session++; if (recognition) recognition.abort(); if (synth) synth.cancel(); speaking = false; state('thinking'); } else if (!speaking) state('idle'); }, failed(message) { halt(); status.textContent = message; }};
  }
  const api = {chooseVoice, init};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AgentBrokerVoice = api;
})(typeof window !== 'undefined' ? window : globalThis);
