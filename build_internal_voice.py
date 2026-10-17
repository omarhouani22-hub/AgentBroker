"""Fetch fixed, checksum-pinned local dialogue and speech-recognition models."""
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = [
    ('https://huggingface.co/bartowski/SmolLM2-360M-Instruct-GGUF/resolve/7be6f65f1db715fe5dc5a4634c0d459b4eed42ec/SmolLM2-360M-Instruct-Q4_K_M.gguf',
     '2fa3f013dcdd7b99f9b237717fa0b12d75bbb89984cc1274be1471a465bac9c2', 271_000_000, 'chat.gguf'),
    ('https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip',
     '30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498', 42_000_000, 'vosk.zip')]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while b := stream.read(1048576): h.update(b)
    return h.hexdigest()


def build():
    directory = ROOT / '.internal-runtime'
    directory.mkdir(exist_ok=True)
    for url, digest, limit, name in FILES:
        target = directory / name
        if not target.is_file() or sha(target) != digest:
            temporary = directory / (name + '.part')
            try:
                with urlopen(url, timeout=60) as remote, temporary.open('wb') as out:
                    total = 0
                    while b := remote.read(1048576):
                        total += len(b)
                        if total > limit: raise ValueError('Model download exceeds reviewed size')
                        out.write(b)
                if sha(temporary) != digest: raise ValueError('Model checksum mismatch')
                temporary.replace(target)
            finally: temporary.unlink(missing_ok=True)
    # Extract only regular files within the fixed model directory. A verified
    # archive remains cached; installation is replaced atomically after validation.
    model = directory / 'vosk-model-small-en-us-0.15'
    marker = directory / 'vosk.sha256'
    expected = FILES[1][1]
    if not model.is_dir() or not marker.is_file() or marker.read_text() != expected:
        with tempfile.TemporaryDirectory(dir=directory) as tmp:
            with zipfile.ZipFile(directory / 'vosk.zip') as archive:
                size = 0
                for info in archive.infolist():
                    path = Path(info.filename)
                    if (path.is_absolute() or '..' in path.parts or not path.parts
                            or path.parts[0] != model.name or (info.external_attr >> 16) & 0o170000 == 0o120000):
                        raise ValueError('Invalid recognition archive')
                    size += info.file_size
                    if size > 150_000_000: raise ValueError('Oversized recognition archive')
                archive.extractall(tmp)
            if model.exists(): shutil.rmtree(model)
            shutil.move(str(Path(tmp) / model.name), model)
            marker.write_text(expected)
    print('Pinned internal chat and recognition models verified.')


if __name__ == '__main__': build()
