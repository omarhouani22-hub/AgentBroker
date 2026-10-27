"""One bounded, public-fixture check of the actual installed voice loop."""
import io
import json
import wave

_state = {'state': 'not_started', 'scope': 'fixed_public_voice_smoke_not_general_quality'}


def status(): return dict(_state, execution_policy='release_ci_only')


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
    # A prior mistaken hearing reply must not trap the next turn on that topic.
    out = local_chat.generate({'conversation':[
        {'role':'user','content':'Can you hear me?'},
        {'role':'assistant','content':"I'm not sure if I can hear you."},
        {'role':'user','content':'What is 17 plus 25?'}]})
    if '42' not in out['content']: raise ValueError('Conversation topic recovery failed')
    # Test the failure reported by the owner using the actual local model.
    out = local_chat.generate({'conversation':[{'role':'user','content':'How can I control my subconscious mind?'}]})
    answer = out['content'].lower()
    if len(answer) < 70 or not any(word in answer for word in ('habit', 'thought', 'practice', 'mindful', 'behavior', 'behaviour', 'focus')) or 'i, me and my' in answer or 'my own subconscious' in answer:
        raise ValueError('User-perspective answer quality check failed')
    # Run an actual generated answer through TTS as the last step.
    if len(local_speech.generate(out['content'])) < 1000: raise ValueError('Output speech smoke failed')
    return {'state': 'passed', 'cases': [name for name, _, _ in cases],
            'recognition': 'passed', 'speech': 'passed', 'topic_recovery': 'passed', 'external_api_calls': 0}


def start():
    """Compatibility no-op: execute evaluate() explicitly in the release job."""
    return None


if __name__ == '__main__': print(json.dumps(evaluate()))
