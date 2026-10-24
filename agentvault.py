"""AgentVault prototype: encrypted, authenticated agent checkpoints.

No public routes, billing, or external model calls. Local prototype only.
SQLite stores metadata; encrypted checkpoint bytes live in a private directory.
"""
import hashlib
import hmac
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken


class AgentVault:
    def __init__(self, directory, master_key, token_hashes):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.cipher = Fernet(master_key)
        self.token_hashes = dict(token_hashes)
        self.database = self.directory / "vault.sqlite3"
        with sqlite3.connect(self.database) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
                agent_id TEXT PRIMARY KEY, version INTEGER NOT NULL,
                updated_at INTEGER NOT NULL, byte_count INTEGER NOT NULL
            )""")

    def _authorize(self, agent_id, token):
        if not isinstance(agent_id, str) or not agent_id or len(agent_id) > 128:
            raise PermissionError("Invalid agent")
        expected = self.token_hashes.get(agent_id)
        actual = hashlib.sha256(token.encode()).hexdigest() if isinstance(token, str) else ""
        if not expected or not hmac.compare_digest(expected, actual):
            raise PermissionError("Unauthorized")

    def save(self, agent_id, token, payload):
        self._authorize(agent_id, token)
        if not isinstance(payload, bytes) or not payload or len(payload) > 1024 * 1024:
            raise ValueError("Checkpoint must be 1 byte to 1 MiB")
        name = hashlib.sha256(agent_id.encode()).hexdigest() + ".checkpoint"
        encrypted = self.cipher.encrypt(payload)
        with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as tmp:
            tmp.write(encrypted)
            temporary = Path(tmp.name)
        os.chmod(temporary, 0o600)
        temporary.replace(self.directory / name)
        with sqlite3.connect(self.database) as db:
            db.execute("""INSERT INTO checkpoints VALUES (?,1,?,?)
                ON CONFLICT(agent_id) DO UPDATE SET
                version=version+1, updated_at=excluded.updated_at,
                byte_count=excluded.byte_count""",
                (agent_id, int(time.time()), len(payload)))
            return db.execute("SELECT version FROM checkpoints WHERE agent_id=?", (agent_id,)).fetchone()[0]

    def restore(self, agent_id, token):
        self._authorize(agent_id, token)
        name = hashlib.sha256(agent_id.encode()).hexdigest() + ".checkpoint"
        try:
            return self.cipher.decrypt((self.directory / name).read_bytes())
        except FileNotFoundError:
            return None
        except InvalidToken as exc:
            raise ValueError("Checkpoint corrupted or wrong key") from exc
