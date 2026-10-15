"""Build the official pinned CPU runtime and verify the public experimental artifact."""
import hashlib
import json
import os
import platform
import tarfile
import tempfile
from urllib.parse import urlparse
from urllib.request import Request
from pathlib import Path

root=Path(__file__).resolve().parent
manifest=json.loads((root/'trained_model_manifest.json').read_text())
cache_defaults=manifest.get('llama_cache', {})

# Reviewed release defaults are checksum pinned. An explicit empty URL disables
# the cache; operator overrides still require a matching digest and revision.
cache_url=os.environ.get('AGENTBROKER_LLAMA_CACHE_URL',cache_defaults.get('url',''))
cache_sha=os.environ.get('AGENTBROKER_LLAMA_CACHE_SHA256',cache_defaults.get('sha256',''))
cache_revision=os.environ.get('AGENTBROKER_LLAMA_CACHE_REVISION',cache_defaults.get('revision',''))
def restore_verified_cache(binary, marker, revision):
    if not cache_url or not cache_sha or not cache_revision:
        print('llama cache disabled; compiling pinned source')
        return False
    if cache_revision != revision or platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        print('Cache revision or platform mismatch; compiling pinned source')
        return False
    parsed=urlparse(cache_url)
    if parsed.scheme!='https' or parsed.hostname not in ('github.com','objects.githubusercontent.com','release-assets.githubusercontent.com') or len(cache_sha)!=64 or any(c not in '0123456789abcdef' for c in cache_sha.lower()):
        print('Invalid cache configuration; compiling pinned source')
        return False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/'cache.tar.gz'
            with urlopen(Request(cache_url,headers={'User-Agent':'AgentBroker-build'}),timeout=45) as response,archive.open('wb') as out:
                total=0
                while chunk:=response.read(1024*1024):
                    total+=len(chunk)
                    if total>250_000_000:
                        raise ValueError('cache download exceeds size limit')
                    out.write(chunk)
            if sha256(archive)!=cache_sha.lower():
                raise ValueError('cache SHA-256 mismatch')
            with tarfile.open(archive,'r:gz') as tar:
                members=tar.getmembers()
                if len(members)!=1 or members[0].name!='llama-server' or not members[0].isfile() or members[0].size>250_000_000:
                    raise ValueError('unexpected cache contents')
                with tar.extractfile(members[0]) as src:
                    binary.parent.mkdir(parents=True,exist_ok=True)
                    temporary=binary.with_suffix('.tmp')
                    with temporary.open('wb') as dst:
                        import shutil
                        shutil.copyfileobj(src,dst)
                    temporary.chmod(0o755)
                    temporary.replace(binary)
            result=subprocess.run([str(binary),'--version'],capture_output=True,text=True,timeout=20)
            if result.returncode!=0:
                raise ValueError('cached binary failed smoke test')
            marker.write_text(revision)
            print('Verified llama cache hit for revision '+revision)
            return True
    except Exception as exc:
        binary.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        print('Cache unavailable or invalid; compiling pinned source: '+str(exc))
        return False
import subprocess
import sys
from urllib.request import urlopen

runtime=root/'.trained-runtime'
runtime.mkdir(exist_ok=True)
model=runtime/'agentbroker-q3.gguf'
def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):
            digest.update(chunk)
    return digest.hexdigest()

if not model.exists() or sha256(model)!=manifest['sha256']:
    temporary=runtime/'download.gguf.part'
    with urlopen(manifest['url'],timeout=60) as response,temporary.open('wb') as out:
        while chunk:=response.read(1024*1024):
            out.write(chunk)
    if sha256(temporary)!=manifest['sha256']:
        raise RuntimeError('Trained model checksum mismatch')
    temporary.replace(model)
revision=manifest['llama_revision']
source=runtime/'source'
binary=runtime/'bin/llama-server'
marker=runtime/'revision'
if not binary.exists() or not marker.exists() or marker.read_text()!=revision:
    if restore_verified_cache(binary, marker, revision):
        print('Experimental trained CPU runtime and checksum verified.')
        sys.exit(0)
    subprocess.run([sys.executable,'-m','pip','install','cmake==4.2.3'],check=True)
    if not (source/'.git').exists():
        subprocess.run(['git','init',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'remote','add','origin','https://github.com/ggml-org/llama.cpp'],check=True)
    subprocess.run(['git','-C',str(source),'fetch','--depth','1','origin',revision],check=True)
    subprocess.run(['git','-C',str(source),'checkout','--detach',revision],check=True)
    import cmake
    cmake_bin=str(Path(cmake.CMAKE_BIN_DIR)/'cmake')
    build=runtime/'build'
    subprocess.run([cmake_bin,'-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
                    '-DBUILD_SHARED_LIBS=OFF','-DGGML_NATIVE=OFF','-DLLAMA_OPENSSL=OFF',
                    '-DLLAMA_BUILD_TESTS=OFF','-DLLAMA_BUILD_EXAMPLES=OFF'],check=True)
    subprocess.run([cmake_bin,'--build',str(build),'--target','llama-server','-j','2'],check=True)
    import shutil
    binary.parent.mkdir(exist_ok=True)
    shutil.copy2(build/'bin/llama-server',binary)
    marker.write_text(revision)
print('Experimental trained CPU runtime and checksum verified.')
