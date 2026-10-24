import hashlib
import tempfile
import unittest
from cryptography.fernet import Fernet
from agentvault import AgentVault


class VaultTests(unittest.TestCase):
    def test_roundtrip_and_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            key = Fernet.generate_key()
            v = AgentVault(d, key, {"a": hashlib.sha256(b"secret").hexdigest()})
            self.assertEqual(v.save("a", "secret", b"memory"), 1)
            self.assertEqual(v.restore("a", "secret"), b"memory")
            self.assertEqual(v.save("a", "secret", b"new"), 2)
            self.assertEqual(v.restore("a", "secret"), b"new")
            with self.assertRaises(PermissionError):
                v.restore("a", "wrong")
            with self.assertRaises(PermissionError):
                v.save("b", "secret", b"bad")
            self.assertNotIn(b"new", (v.directory / (hashlib.sha256(b"a").hexdigest() + ".checkpoint")).read_bytes())

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as d:
            v = AgentVault(d, Fernet.generate_key(), {"a": hashlib.sha256(b"s").hexdigest()})
            with self.assertRaises(ValueError):
                v.save("a", "s", b"x" * (1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
