"""Private CPU speech service. Fixed local model, bounded worker, no network calls."""
import importlib.util
import io
import json
import os
import platform
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parent
VOICE = 'en_US-kristin-medium'
MODEL = ROOT / ('.speech-runtime/' + VOICE + '.onnx')
OPTIMIZED = MODEL.with_suffix('.optimized.onnx')
OPTIMIZED_META = MODEL.with_suffix('.optimized.json')
MAX_CHARS = 800


def _cache_fingerprint(ort):
    from build_local_speech import FILES, REVISION
    return {'voice': VOICE, 'source_sha256': FILES[VOICE + '.onnx'][0],
            'revision': REVISION, 'runtime': ort.__version__,
            'machine': platform.machine(), 'provider': 'CPUExecutionProvider',
            'optimization': 'extended'}


def cached_model(ort):
    try:
        if OPTIMIZED_META.stat().st_size > 4096: return None
        meta = json.loads(OPTIMIZED_META.read_text())
        if (meta['fingerprint'] == _cache_fingerprint(ort)
                and 0 < OPTIMIZED.stat().st_size == meta['bytes'] <= 100_000_000):
            return OPTIMIZED
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def session_options(ort):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    return options


def load_session(ort):
    options = session_options(ort)
    cached = cached_model(ort)
    if cached:
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    try:
        return ort.InferenceSession(str(cached or MODEL), sess_options=options,
                                   providers=['CPUExecutionProvider'])
    except Exception:
        if not cached: raise
        return ort.InferenceSession(str(MODEL), sess_options=session_options(ort),
                                    providers=['CPUExecutionProvider'])


def prepare_optimized_model():
    """Build-time only: retain CPU graph rewrites, without hardware layout ops."""
    import onnxruntime as ort
    from build_local_speech import digest
    cached = cached_model(ort)
    if cached and digest(cached) == json.loads(OPTIMIZED_META.read_text())['sha256']:
        return
    options = session_options(ort)
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
    temporary = MODEL.with_suffix('.optimized.part.onnx')
    options.optimized_model_filepath = str(temporary)
    try:
        session = ort.InferenceSession(str(MODEL), sess_options=options,
                                       providers=['CPUExecutionProvider'])
        del session
        if not 0 < temporary.stat().st_size <= 100_000_000:
            raise ValueError('Invalid optimized voice model')
        temporary.replace(OPTIMIZED)
        OPTIMIZED_META.write_text(json.dumps({'fingerprint': _cache_fingerprint(ort),
            'bytes': OPTIMIZED.stat().st_size, 'sha256': digest(OPTIMIZED)}))
    finally:
        temporary.unlink(missing_ok=True)


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
    session = load_session(ort)
    voice = PiperVoice(config=PiperConfig.from_dict(json.loads(Path(str(MODEL) + '.json').read_text())),
                       session=session,
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
