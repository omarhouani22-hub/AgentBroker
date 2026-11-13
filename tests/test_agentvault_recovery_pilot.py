"""Isolated regression tests for AgentVault checkpoint recovery.

These tests use temporary storage and generated keys only; no production data,
external services, credentials, or network calls.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from agentvault import AgentVault


class AgentVaultRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = Fernet.generate_key()
        self.token = "local-test-token"
        self.vault = AgentVault(
            self.temp.name,
            self.key,
            {"agent-a": hashlib.sha256(self.token.encode()).hexdigest()},
        )

    def test_round_trip_and_version_increment(self):
        self.assertEqual(self.vault.save("agent-a", self.token, b"first"), 1)
        self.assertEqual(self.vault.restore("agent-a", self.token), b"first")
        self.assertEqual(self.vault.save("agent-a", self.token, b"second"), 2)
        self.assertEqual(self.vault.restore("agent-a", self.token), b"second")

    def test_missing_checkpoint_returns_none(self):
        self.assertIsNone(self.vault.restore("agent-a", self.token))

    def test_wrong_agent_token_cannot_restore(self):
        self.vault.save("agent-a", self.token, b"private")
        with self.assertRaises(PermissionError):
            self.vault.restore("agent-a", "wrong-token")

    def test_tampered_checkpoint_is_rejected(self):
        self.vault.save("agent-a", self.token, b"original")
        name = hashlib.sha256(b"agent-a").hexdigest() + ".checkpoint"
        checkpoint = Path(self.temp.name) / name
        encrypted = bytearray(checkpoint.read_bytes())
        encrypted[-1] ^= 1
        checkpoint.write_bytes(encrypted)
        with self.assertRaises(ValueError):
            self.vault.restore("agent-a", self.token)

    def test_wrong_encryption_key_is_rejected(self):
        self.vault.save("agent-a", self.token, b"private")
        other = AgentVault(
            self.temp.name,
            Fernet.generate_key(),
            {"agent-a": hashlib.sha256(self.token.encode()).hexdigest()},
        )
        with self.assertRaises(ValueError):
            other.restore("agent-a", self.token)


if __name__ == "__main__":
    unittest.main()
