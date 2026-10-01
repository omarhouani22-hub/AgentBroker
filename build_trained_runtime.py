"""Build the official pinned CPU runtime and verify the public experimental artifact."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

root=Path(__file__).resolve().parent
manifest=json.loads((root/'trained_model_manifest.json').read_text())
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
