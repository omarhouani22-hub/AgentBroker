/* Bundled native adapter. No microphone or speech starts until a user action. */
(function (root) {
  'use strict';
  if (!root.webkit?.messageHandlers?.clara) return;
  let serial = 0, current = null, voices = [];
  const utterances = new Map(), listeners = new Set();
  const send = (action, data = {}) => root.webkit.messageHandlers.clara.postMessage({action, ...data});
  class Utterance {
    constructor(text) { this.text = String(text); this.lang = 'en-US'; this.rate = 1; this.volume = 1; this.voice = null; }
  }
  class Recognition {
    constructor() { this.lang = 'en-US'; this.interimResults = true; this.running = false; }
    start() {
      if (this.running || current) throw new Error('Recognition already active');
      this.id = ++serial; this.running = true; current = this;
      send('recognize', {id:this.id, language:this.lang});
    }
    stop() { if (this.running) send('finishRecognition', {id:this.id}); }
    abort() {
      if (!this.running) return;
      send('abortRecognition', {id:this.id}); this.running = false;
      if (current === this) current = null;
      this.onend?.();
    }
  }
  const speechSynthesis = {
    getVoices: () => voices.slice(),
    addEventListener(name, callback) { if (name === 'voiceschanged') listeners.add(callback); },
    resume() { send('resumeSpeech'); },
    cancel() { utterances.clear(); send('cancelSpeech'); },
    speak(utterance) {
      const id = ++serial; utterances.set(id, utterance);
      send('speak', {id, text:utterance.text, language:utterance.lang, voice:utterance.voice?.voiceURI || '', rate:utterance.rate, volume:utterance.volume});
    }
  };
  function receive(event) {
    if (event.type === 'voices') {
      voices = event.voices; listeners.forEach(callback => callback()); return;
    }
    if (event.type.startsWith('speech')) {
      const utterance = utterances.get(event.id); if (!utterance) return;
      if (event.type === 'speechStart') utterance.onstart?.();
      else { utterances.delete(event.id); (event.type === 'speechEnd' ? utterance.onend : utterance.onerror)?.({error:event.error}); }
      return;
    }
    const input = current; if (!input || input.id !== event.id) return;
    if (event.type === 'recognitionStart') input.onstart?.();
    if (event.type === 'recognitionResult') {
      const result = [{transcript:event.text, confidence:1}]; result.isFinal = event.final;
      input.onresult?.({resultIndex:0, results:[result]});
    }
    if (event.type === 'recognitionError') input.onerror?.({error:event.error});
    if (event.type === 'recognitionEnd') { current = null; input.running = false; input.onend?.(); }
  }
  root.ClaraNativeSpeech = {Recognition, Utterance, speechSynthesis, _receive:receive,
    _suspend() { root.document.dispatchEvent(new root.Event('clara-native-pause')); current?.abort(); speechSynthesis.cancel(); }
  };
  send('voices');
})(window);
