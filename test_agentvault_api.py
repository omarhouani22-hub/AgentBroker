import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from agentvault_api import app


class APITests(unittest.TestCase):
    def test_save_restore_auth_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            env = {"AGENTVAULT_KEY": Fernet.generate_key().decode(),
                   "AGENTVAULT_DIR": d,
                   "AGENTVAULT_TOKEN_HASHES": json.dumps({"a": hashlib.sha256(b"secret").hexdigest()})}
            with patch.dict(os.environ, env):
                client = app.test_client()
                headers = {"X-Agent-Id": "a", "Authorization": "Bearer secret"}
                self.assertEqual(client.put("/v1/checkpoint", data=b"state", headers=headers).status_code, 200)
                self.assertEqual(client.get("/v1/checkpoint", headers=headers).data, b"state")
                self.assertEqual(client.get("/v1/checkpoint", headers={"X-Agent-Id": "a", "Authorization": "Bearer wrong"}).status_code, 401)
                self.assertEqual(client.get("/v1/checkpoint", headers=headers).data, b"state")

    def test_no_credentials_returns_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(app.test_client().get("/v1/checkpoint",
                headers={"X-Agent-Id": "a", "Authorization": "Bearer x"}).status_code, 503)


if __name__ == "__main__":
    unittest.main()
