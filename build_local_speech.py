"""Install the reviewed voice at build time; inference never downloads anything."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
VOICE = 'en_US-ljspeech-medium'
REVISION = 'bae641dcb5a608cff81ccaf7ff018baaca1a33e1'
BASE = f'https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/en/en_US/ljspeech/medium/'
FILES = {
    VOICE + '.onnx': ('6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22', 64_000_000),
    VOICE + '.onnx.json': ('141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860', 20_000),
    'MODEL_CARD': ('fbee1529c89d36b3fe76d7e9f3f832dce17f44900a52d76a9bda735654766b4d', 20_000),
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


if __name__ == '__main__':
    build()
