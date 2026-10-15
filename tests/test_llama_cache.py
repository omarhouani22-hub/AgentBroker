"""Unit checks for the opt-in cache configuration (no network or model download)."""
import ast
import hashlib
import io
import tarfile
import subprocess
import pathlib
import tempfile
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "build_trained_runtime.py"
tree = ast.parse(SOURCE.read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "restore_verified_cache")
module = ast.Module(body=[fn], type_ignores=[])

class CacheTests(unittest.TestCase):
    def run_restore(self, url, digest):
        import subprocess
        import tarfile
        from urllib.parse import urlparse
        from urllib.request import Request, urlopen
        scope = dict(cache_url=url, cache_sha=digest, urlparse=urlparse,
                     tempfile=tempfile, Path=pathlib.Path, urlopen=urlopen,
                     Request=Request, tarfile=tarfile, subprocess=subprocess,
                     sha256=lambda _: "")
        exec(compile(module, str(SOURCE), "exec"), scope)
        with tempfile.TemporaryDirectory() as tmp:
            binary = pathlib.Path(tmp) / "bin" / "llama-server"
            marker = pathlib.Path(tmp) / "revision"
            with patch.dict(scope, {"urlopen": lambda *a, **kw: (_ for _ in ()).throw(AssertionError("network called"))}):
                return scope["restore_verified_cache"](binary, marker, "test-revision")

    def test_verified_archive_restores_binary(self):
        payload=b"#!/bin/sh\necho llama-version\n"
        with tempfile.TemporaryDirectory() as tmp:
            archive=pathlib.Path(tmp)/"cache.tar.gz"
            with tarfile.open(archive,"w:gz") as tar:
                info=tarfile.TarInfo("llama-server")
                info.size=len(payload)
                tar.addfile(info,io.BytesIO(payload))
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            from urllib.parse import urlparse
            from urllib.request import Request
            scope=dict(cache_url="https://example.org/llama.tar.gz",cache_sha=digest,
                       urlparse=urlparse,tempfile=tempfile,Path=pathlib.Path,
                       Request=Request,tarfile=tarfile,subprocess=subprocess,
                       sha256=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
                       urlopen=lambda *a,**kw: archive.open("rb"))
            exec(compile(module,str(SOURCE),"exec"),scope)
            binary=pathlib.Path(tmp)/"bin"/"llama-server"
            marker=pathlib.Path(tmp)/"revision"
            self.assertTrue(scope["restore_verified_cache"](binary,marker,"test-revision"))
            self.assertEqual(binary.read_bytes(),payload)
            self.assertEqual(marker.read_text(),"test-revision")

    def test_corrupt_archive_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=pathlib.Path(tmp)/"bad.tar.gz"
            archive.write_bytes(b"not an archive")
            from urllib.parse import urlparse
            from urllib.request import Request
            scope=dict(cache_url="https://example.org/bad.tar.gz",
                       cache_sha=hashlib.sha256(archive.read_bytes()).hexdigest(),
                       urlparse=urlparse,tempfile=tempfile,Path=pathlib.Path,
                       Request=Request,tarfile=tarfile,subprocess=subprocess,
                       sha256=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
                       urlopen=lambda *a,**kw: archive.open("rb"))
            exec(compile(module,str(SOURCE),"exec"),scope)
            binary=pathlib.Path(tmp)/"bin"/"llama-server"
            marker=pathlib.Path(tmp)/"revision"
            self.assertFalse(scope["restore_verified_cache"](binary,marker,"test-revision"))
            self.assertFalse(marker.exists())

    def test_disabled(self):
        self.assertFalse(self.run_restore("", ""))

    def test_rejects_http(self):
        self.assertFalse(self.run_restore("http://example.org/cache.tar.gz", "a"*64))

    def test_rejects_invalid_digest(self):
        self.assertFalse(self.run_restore("https://example.org/cache.tar.gz", "not-a-digest"))

if __name__ == "__main__":
    unittest.main()
