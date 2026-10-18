"""Install the reviewed voice at build time; inference never downloads anything."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
VOICE = 'en_US-kristin-medium'
REVISION = 'bae641dcb5a608cff81ccaf7ff018baaca1a33e1'
BASE = f'https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/en/en_US/kristin/medium/'
FILES = {
    VOICE + '.onnx': ('5849957f929cbf720c258f8458692d6103fff2f0e3d3b19c8259474bb06a18d4', 64_000_000),
    VOICE + '.onnx.json': ('5681426d4aead22195de70531eeeeddb46493cfaffc5764b2ea3db73428b651c', 20_000),
    'MODEL_CARD': ('8c181b1d5f7d8152b914faab941fcbe6b8f0495e63e5189d6f27b8c68c8393fc', 20_000),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def build():
    directory = ROOT / '.speech-runtime'
    directory.mkdir(exist_ok=True)
    for name, (expected, limit) in FILES.items():
        destination = directory / name
        if destination.is_file() and digest(destination) == expected:
            continue
        temporary = destination.with_suffix(destination.suffix + '.part')
        try:
            with urlopen(BASE + name, timeout=60) as remote, temporary.open('wb') as out:
                total = 0
                while chunk := remote.read(1024 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise ValueError('Voice download exceeds reviewed size')
                    out.write(chunk)
            if digest(temporary) != expected:
                raise ValueError('Voice checksum mismatch')
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    print('Pinned English female voice verified; no inference API used.')
    from local_speech import prepare_optimized_model
    prepare_optimized_model()
    print('Local CPU voice graph prepared for faster worker startup.')


if __name__ == '__main__':
    build()
