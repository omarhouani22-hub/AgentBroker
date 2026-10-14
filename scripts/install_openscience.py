"""Install a pinned upstream Linux runtime; never log in or run a model at build time."""
import hashlib
import io
import os
import platform
import tarfile
from pathlib import Path
from urllib.request import urlopen

VERSION = '2.0.151'
SHA256 = '2f7aed5c40c988296775fa1283a494de1710aba9137a6ce2ab182673e6b8f869'
URL = ('https://github.com/synthetic-sciences/openscience/releases/download/'
       f'v{VERSION}/openscience-linux-x64-baseline.tar.gz')


def main():
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise RuntimeError('Pinned OpenScience package requires Linux x64')
    destination = Path(__file__).resolve().parent.parent / '.openscience-runtime'
    destination.mkdir(mode=0o700, exist_ok=True)
    with urlopen(URL, timeout=120) as response:
        archive = response.read(100 * 1024 * 1024)
    if hashlib.sha256(archive).hexdigest() != SHA256:
        raise RuntimeError('OpenScience release checksum mismatch')
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as package:
        member = package.getmember('openscience')
        if not member.isfile():
            raise RuntimeError('OpenScience binary is not a regular file')
        binary = package.extractfile(member)
        if binary is None:
            raise RuntimeError('OpenScience release binary missing')
        target = destination / 'openscience'
        target.write_bytes(binary.read())
        os.chmod(target, 0o700)
    print(f'OpenScience {VERSION} runtime installed; model usage remains disabled by default.')


if __name__ == '__main__':
    main()
