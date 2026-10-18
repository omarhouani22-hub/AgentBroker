"""Private CPU speech service. Fixed local model, bounded worker, no network calls."""
import importlib.util
import io
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parent
VOICE = 'en_US-kristin-medium'
MODEL = ROOT / ('.speech-runtime/' + VOICE + '.onnx')
MAX_CHARS = 800


def configured():
    return (importlib.util.find_spec('piper') is not None and MODEL.is_file()
            and Path(str(MODEL) + '.json').is_file())


def validate(text):
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= MAX_CHARS:
        raise ValueError('Local voice accepts 1–800 characters per reply.')
    if re.search(r'[\u0600-\u06ff]', text):
        raise ValueError('The internal voice currently supports English only.')


def generate(text):
    validate(text)
    if not configured():
        raise RuntimeError('Local voice is not installed')
    # Protect the web process on a shared free host; serialize with dialogue lock.
    try:
        maximum = int(Path('/sys/fs/cgroup/memory.max').read_text().strip())
        current = int(Path('/sys/fs/cgroup/memory.current').read_text().strip())
        stats = dict(line.split() for line in Path('/sys/fs/cgroup/memory.stat').read_text().splitlines())
        anonymous = current - int(stats.get('file', 0))
        if maximum - anonymous < 240 * 1024 * 1024:
            raise RuntimeError('Insufficient memory for internal speech')
    except (OSError, ValueError):
        pass
    with tempfile.TemporaryDirectory(prefix='clara-speech-') as directory:
        target = Path(directory) / 'reply.wav'
        # Text is stdin, never shell syntax, command arguments, logs or public files.
        env = {key: value for key, value in os.environ.items()
               if key in ('PATH', 'LANG', 'LC_ALL', 'LD_LIBRARY_PATH', 'SYSTEMROOT')}
        subprocess.run([sys.executable, str(Path(__file__).resolve()), str(target)],
                       input=text.encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, env=env, check=True, timeout=35)
        if not target.is_file() or not 44 < target.stat().st_size <= 4_000_000:
            raise ValueError('Invalid local speech response')
        data = target.read_bytes()
        with wave.open(io.BytesIO(data)) as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getnframes() == 0:
                raise ValueError('Invalid local waveform')
        return data


def worker(target):
    # Imported only in an ephemeral worker; release model RAM after each utterance.
    import json
    import onnxruntime as ort
    from piper import PiperVoice
    from piper.config import PiperConfig, SynthesisConfig
    from piper.voice import ESPEAK_DATA_DIR
    text = sys.stdin.buffer.read(5000).decode()
    validate(text)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    voice = PiperVoice(config=PiperConfig.from_dict(json.loads(Path(str(MODEL) + '.json').read_text())),
                       session=ort.InferenceSession(str(MODEL), sess_options=options,
                                                   providers=['CPUExecutionProvider']),
                       espeak_data_dir=ESPEAK_DATA_DIR, download_dir=MODEL.parent)
    # Short chunks prevent one long utterance from allocating a large activation tensor.
    chunks = re.findall(r'.{1,170}(?:\s+|$)', text)
    if ''.join(chunks).strip() != text.strip():
        chunks = [text[i:i+160] for i in range(0, len(text), 160)]
    with wave.open(str(target), 'wb') as output:
        for index, chunk in enumerate(chunks):
            voice.synthesize_wav(chunk.strip(), output,
                                 syn_config=SynthesisConfig(length_scale=0.95),
                                 set_wav_format=index == 0)


if __name__ == '__main__':
    worker(sys.argv[1])
