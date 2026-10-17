"""Actual fixed public utterance; no private conversation or paid providers."""
import io
import json
import resource
import sys
import time
import wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import local_speech

started = time.monotonic()
audio = local_speech.generate('I am Clara, your AI assistant. What do you wanna talk about?')
elapsed = time.monotonic() - started
with wave.open(io.BytesIO(audio)) as waveform:
    duration = waveform.getnframes() / waveform.getframerate()
    assert 1 < duration < 20
assert elapsed < 30
print(json.dumps({'provider': 'Piper', 'api_calls': 0, 'seconds': round(elapsed, 2),
                  'audio_seconds': round(duration, 2),
                  'worker_peak_mib': round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024, 1)}))
