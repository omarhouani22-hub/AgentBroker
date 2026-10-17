"""One bounded, public-fixture check of the actual installed voice loop."""
import io
import json
import threading
import wave
import time

_started = False
_lock = threading.Lock()
_state = {'state': 'not_started', 'scope': 'fixed_public_voice_smoke_not_general_quality'}


def status(): return dict(_state)


def evaluate():
    import local_chat
    import local_speech
    import local_recognition
    # Current deployment and CI are Python 3.12/3.11. No ffmpeg or cloud service.
    import audioop
    data = local_speech.generate('The weather is nice today. We can walk in the park.')
    with wave.open(io.BytesIO(data)) as audio:
        rate = audio.getframerate()
        frames = audio.readframes(audio.getnframes())
    down, _ = audioop.ratecv(frames, 2, 1, rate, 16000, None)
    wav = io.BytesIO()
    with wave.open(wav, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(down)
    transcript = local_recognition.transcribe(wav.getvalue())
    expected = {'weather', 'nice', 'today', 'walk', 'park'}
    if len(expected.intersection(transcript.lower().split())) < 4:
        raise ValueError('Recognition smoke failed')
    cases = [('identity', 'What is your name?', 'clara'),
             ('arithmetic', 'What is 17 plus 25?', '42'),
             ('recall', 'My favourite colour is blue. What colour did I just mention?', 'blue')]
    for _, question, expected in cases:
        out = local_chat.generate({'conversation':[{'role':'user','content':question}]})
        if expected not in out['content'].lower(): raise ValueError('Conversation smoke failed')
    # Run an actual generated answer through TTS as the last step.
    if len(local_speech.generate(out['content'])) < 1000: raise ValueError('Output speech smoke failed')
    return {'state': 'passed', 'cases': [name for name, _, _ in cases],
            'recognition': 'passed', 'speech': 'passed', 'external_api_calls': 0}


def start():
    global _started
    import local_chat
    if not local_chat.enabled(): return
    with _lock:
        if _started: return
        _started = True
    def run():
        import moltbook
        if not moltbook.DIALOGUE_LOCK.acquire(False):
            _state['state'] = 'busy'; return
        _state['state'] = 'running'
        started = time.monotonic()
        try: _state.update(evaluate(), seconds=round(time.monotonic()-started, 2))
        except Exception as error: _state.update(state='failed', failure=type(error).__name__)
        finally: moltbook.DIALOGUE_LOCK.release()
    threading.Thread(target=run, daemon=True, name='internal-voice-fixed-smoke').start()


if __name__ == '__main__': print(json.dumps(evaluate()))
