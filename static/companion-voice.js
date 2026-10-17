/* Browser speech, plus optional explicitly configured neural speech. No always-on microphone. */
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
    const natural = win.ClaraNaturalVoice ? win.ClaraNaturalVoice.init(doc,win,() => halt()) : null;
    let recognition = null, speaking = false, thinking = false, session = 0, preferred = '', greeted = false;
    // Keep native utterances alive until completion (important on Safari/iOS).
    let currentUtterance = null, primeUtterance = null, unlocked = false, lastContent = '', watchdog = null;
    const greeting = 'I am Clara, your AI assistant. What do you wanna talk about?';
    function clearWatchdog() { if (watchdog !== null && win.clearTimeout) win.clearTimeout(watchdog); watchdog = null; }
    function unlock() {
      if (!synth || !win.SpeechSynthesisUtterance) return;
      if (synth.resume) synth.resume();
      if (!unlocked) {
        unlocked = true; primeUtterance = new win.SpeechSynthesisUtterance(' ');
        primeUtterance.volume = 0; primeUtterance.onend = () => { primeUtterance = null; };
        primeUtterance.onerror = () => { primeUtterance = null; };
        try { synth.speak(primeUtterance); } catch (_) { unlocked = false; primeUtterance = null; }
      }
    }
    function save(key, value) { try { win.localStorage.setItem(key, value); } catch (_) {} }
    function read(key) { try { return win.localStorage.getItem(key); } catch (_) { return null; } }
    language.value = read('agentbroker-mic-language') === 'ar-JO' ? 'ar-JO' : 'en-US';
    preferred = read('agentbroker-voice') || '';
    function state(value) {
      avatar.dataset.state = value;
      avatarStatus.textContent = ({idle:'Ready to chat',listening:'Listening…',thinking:'Preparing a reply…',speaking:'Speaking…'})[value];
      stop.hidden = value === 'idle' && !mode.checked;
      const call = get('companion-call'); if (call) { call.textContent = mode.checked ? '✕ End call' : '☎ Start voice call'; call.dataset.active = String(mode.checked); }
    }
    function updateVoices() {
      const voices = synth ? synth.getVoices() : [];
      voiceSelect.replaceChildren();
      const auto = doc.createElement('option'); auto.value = ''; auto.textContent = 'Female voice when available'; voiceSelect.append(auto);
      for (const voice of voices.filter(v => /^(ar|en)(-|$)/i.test(v.lang))) {
        const option = doc.createElement('option'); option.value = voice.voiceURI; option.textContent = voice.name + ' · ' + voice.lang; voiceSelect.append(option);
      }
      voiceSelect.value = [...voiceSelect.options].some(o => o.value === preferred) ? preferred : '';
      voiceHelp.textContent = 'Voices depend on your device and follow the reply language. Download English and Arabic voices in your device settings if needed.';
    }
    voiceSelect.onchange = () => { preferred = voiceSelect.value; save('agentbroker-voice', preferred); };
    function halt() {
      mode.checked = false; session++; speaking = false; if (natural) natural.stop(); clearWatchdog(); currentUtterance = null;
      if (recognition) recognition.abort();
      if (synth) synth.cancel();
      state(thinking ? 'thinking' : 'idle');
    }
    function listen() {
      if (!SpeechInput || thinking || doc.hidden) return;
      if (recognition) { recognition.stop(); return; }
      session++; const active = session;
      if (natural) natural.stop();
      if (synth) synth.cancel(); speaking = false;
      const input = new SpeechInput(); recognition = input;
      const original = field.value.trim(); let heard = '', failed = false;
      // Auto reply language cannot identify untranscribed audio. Choose input explicitly.
      input.lang = language.value;
      input.continuous = false; input.interimResults = true; input.maxAlternatives = 1;
      field.readOnly = true; language.disabled = true;
      input.onstart = () => { if (active === session) { state('listening'); mic.textContent = 'Finish listening'; status.textContent = 'Listening…'; } };
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
        const errors = {'not-allowed':'Allow microphone access in browser settings.', 'service-not-allowed':'Speech recognition unavailable; use keyboard dictation.', 'audio-capture':'Check your microphone.', 'no-speech':'No speech heard; tap the microphone to retry.', 'network':'Speech service connection failed; use keyboard dictation.'};
        status.textContent = errors[event.error] || 'Check the mic language or use keyboard dictation.';
      };
      input.onend = () => {
        if (recognition === input) recognition = null;
        field.readOnly = thinking; language.disabled = false; transcript.textContent = '';
        mic.textContent = '🎤 Speak';
        if (active !== session) return;
        state('idle');
        if (!failed && heard.trim()) {
          status.textContent = mode.checked ? 'Sending…' : 'Review the transcript, then Send.';
          if (mode.checked) get('companion-form').requestSubmit();
        } else if (!failed) {
          mode.checked = false;
          status.textContent = 'No clear transcript; try again.';
        }
      };
      try { state('listening'); input.start(); }
      catch (_) { recognition = null; field.readOnly = false; language.disabled = false; halt(); status.textContent = 'Microphone unavailable; use keyboard dictation.'; }
    }
    function speak(content, keepInputLanguage = false) {
      if (!synth || !win.SpeechSynthesisUtterance) {
        mode.checked = false; status.textContent = 'Speech playback unavailable. Open Clara in Safari or Chrome.'; state('idle'); return;
      }
      content = String(content || '').trim(); if (!content) return;
      lastContent = content; unlocked = true; clearWatchdog();
      session++; const active = session;
      if (natural) natural.stop();
      if (recognition) recognition.abort();
      synth.cancel(); if (synth.resume) synth.resume();
      const lang = isArabic(content) ? 'ar-JO' : 'en-US';
      if (mode.checked && !keepInputLanguage) { language.value = lang; save('agentbroker-mic-language', language.value); }
      // Short chunks avoid long-utterance stalls in mobile speech engines.
      const words = content.split(/\s+/), chunks = []; let chunk = '';
      for (const word of words) { if (chunk && (chunk+' '+word).length > 180) { chunks.push(chunk); chunk=''; } chunk += (chunk?' ':'')+word; }
      if (chunk) chunks.push(chunk);
      function audioFailed() {
        if (active !== session) return;
        clearWatchdog(); session++; speaking = false; mode.checked = false; currentUtterance = null; synth.cancel(); state('idle');
        status.textContent = 'Audio could not start. Tap Clara or Listen to play the reply. Check your device volume and selected voice.';
      }
      function play(index) {
        if (active !== session || doc.hidden) return;
        const utterance = new win.SpeechSynthesisUtterance(chunks[index]); currentUtterance = utterance;
        utterance.lang = lang;
        const selected = chooseVoice(synth.getVoices(), lang, preferred);
        if (selected) utterance.voice = selected;
        utterance.rate = 1; utterance.volume = 1;
        utterance.onstart = () => {
          if (active !== session) return;
          clearWatchdog(); speaking = true; state('speaking'); status.textContent = '';
          const help = get('audio-help'); if (help) help.textContent = 'Voice enabled. Replies are read aloud while this page is open.';
        };
        utterance.onend = () => {
          if (active !== session) return;
          clearWatchdog(); currentUtterance = null;
          if (index+1 < chunks.length) { play(index+1); return; }
          speaking = false; state('idle');
          if (mode.checked && !doc.hidden) listen();
        };
        utterance.onerror = audioFailed;
        if (win.setTimeout) watchdog = win.setTimeout(audioFailed, 5000);
        try { synth.speak(utterance); } catch (_) { audioFailed(); }
      }
      if (natural && natural.selected()) {
        state('thinking'); natural.play(content,{
          onstart(){if(active===session){speaking=true;state('speaking');status.textContent='';}},
          onend(){if(active===session){speaking=false;state('idle');if(mode.checked&&!doc.hidden)listen();}},
          onblocked(){if(active===session){speaking=false;mode.checked=false;state('idle');status.textContent='Tap Play below Clara to hear the natural voice.';}},
          onerror(){if(active===session)play(0);}
        });
      } else play(0);
    }
    // This is a deliberate user gesture, so it also works as Safari's audio unlock.
    avatar.onclick = () => { if (thinking) return; speak(lastContent || greeting, true); };
    mic.onclick = () => { unlock(); listen(); };
    stop.onclick = () => { halt(); status.textContent = 'Voice conversation stopped.'; };
    mode.onchange = () => {
      if (!mode.checked) { halt(); return; }
      if (!synth) { halt(); status.textContent = 'Speech playback unavailable. Open Clara in Safari or Chrome.'; return; }
      if (!greeted) { greeted = true; speak(greeting, true); }
      else listen();
    };
    const callButton = get('companion-call');
    if (callButton) callButton.onclick = () => {
      if (!SpeechInput) { status.textContent = 'Hands-free input is unavailable in this browser. Use keyboard dictation and Enable voice.'; return; }
      mode.checked = !mode.checked; mode.onchange();
    };
    language.onchange = () => { save('agentbroker-mic-language', language.value); state('idle'); };
    doc.addEventListener('visibilitychange', () => { if (doc.hidden) halt(); });
    if (!SpeechInput) { mic.disabled = true; mode.disabled = true; status.textContent = 'Speech input unavailable here. Use keyboard dictation; spoken replies are still available.'; }
    if (synth && synth.addEventListener) synth.addEventListener('voiceschanged', updateVoices);
    updateVoices(); state('idle');
    return {speak, halt, unlock, refreshNatural:() => natural ? natural.refresh() : Promise.resolve(), remember:content => {lastContent=content;}, active:() => mode.checked, thinking(value) { thinking = value; if (value) { if(natural)natural.stop(); clearWatchdog(); currentUtterance = null; session++; if (recognition) recognition.abort(); if (synth) synth.cancel(); speaking = false; state('thinking'); } else if (!speaking) state('idle'); }, failed(message) { halt(); status.textContent = message; }};
  }
  const api = {chooseVoice, init};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AgentBrokerVoice = api;
})(typeof window !== 'undefined' ? window : globalThis);
