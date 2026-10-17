"""English speech recognition in a short-lived local worker, without API calls."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / '.internal-runtime/vosk-model-small-en-us-0.15'
MAX_BYTES = 960_044


def configured():
    return importlib.util.find_spec('vosk') is not None and (MODEL / 'am/final.mdl').is_file()


def validate(data):
    if not 44 < len(data) <= MAX_BYTES: raise ValueError('Provide up to 30 seconds of audio')
    try:
        with wave.open(io.BytesIO(data)) as audio:
            if (audio.getnchannels() != 1 or audio.getsampwidth() != 2
                    or audio.getframerate() != 16000 or audio.getcomptype() != 'NONE'
                    or not 1 <= audio.getnframes() <= 480000):
                raise ValueError('Use mono 16 kHz PCM WAV audio')
            frames = audio.readframes(480001)
            if len(frames) != audio.getnframes() * 2: raise ValueError('Truncated waveform')
    except (wave.Error, EOFError) as error:
        raise ValueError('Invalid waveform') from error
    return frames


def transcribe(data):
    validate(data)
    if not configured(): raise RuntimeError('Internal recognition is not installed')
    from local_chat import memory_headroom
    memory_headroom(320)
    result = subprocess.run([sys.executable, str(Path(__file__).resolve())], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','LD_LIBRARY_PATH')},
                            timeout=30, check=True)
    text = json.loads(result.stdout)['text']
    if not isinstance(text, str) or len(text) > 2000: raise ValueError('Invalid transcript')
    return text


def install_routes(app):
    from flask import jsonify, request
    @app.post('/companion/transcribe')
    def recognize():
        if request.mimetype != 'audio/wav': return jsonify(error='Use WAV audio'), 415
        data = request.stream.read(MAX_BYTES + 1)
        try: validate(data)
        except ValueError as error: return jsonify(error=str(error)), 400
        import moltbook as m
        if not m.DIALOGUE_LOCK.acquire(False): return jsonify(error='Clara is busy'), 409
        try:
            return jsonify(text=transcribe(data), provider='Vosk', internal=True)
        except Exception:
            return jsonify(error='Internal recognition unavailable; no external service was called.'), 503
        finally: m.DIALOGUE_LOCK.release()


if __name__ == '__main__':
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    frames = validate(sys.stdin.buffer.read(MAX_BYTES + 1))
    recognizer = KaldiRecognizer(Model(str(MODEL)), 16000)
    words = []
    for offset in range(0, len(frames), 8000):
        if recognizer.AcceptWaveform(frames[offset:offset+8000]):
            words.append(json.loads(recognizer.Result()).get('text', ''))
    words.append(json.loads(recognizer.FinalResult()).get('text', ''))
    print(json.dumps({'text': ' '.join(words).strip()}))
