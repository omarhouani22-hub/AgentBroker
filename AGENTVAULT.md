# AgentVault — experimental agent memory backup

**Status: local prototype, not a production storage service.** No public API, payment system, customer onboarding, Moltbook campaign, or guarantees of durability. No model API calls or spending.

The Python `AgentVault` class encrypts up to 1 MiB per checkpoint with Fernet, authenticates each agent using a pre-provisioned SHA-256 token hash, and records checkpoint version/size/timestamp in SQLite. Encrypted bytes are stored outside SQLite in a private directory.

Run local tests: `python -m unittest test_agentvault.py` (requires existing `cryptography` dependency).

Example:
```python
import hashlib
from cryptography.fernet import Fernet
from agentvault import AgentVault
vault = AgentVault("/private/agentvault", Fernet.generate_key(), {"demo": hashlib.sha256(b"random-demo-token").hexdigest()})
vault.save("demo", "random-demo-token", b"checkpoint")
assert vault.restore("demo", "random-demo-token") == b"checkpoint"
```

**Important:** The example key is ephemeral: persist it securely or previous data becomes unrecoverable. Never put production tokens or encryption keys in Git. Local disk on free hosting may be ephemeral; do not claim backup durability without external persistent storage and tested disaster recovery. Prototype has no quotas, concurrency controls, billing, public endpoints, retention, audit trail, or cross-region redundancy. Do not accept customer data before addressing these issues.

**Validation gates before Moltbook promotion:** confirm actual demand from operators/agents; test independent restart recovery on durable storage; verify encryption, token isolation, deletion, and abuse protection; establish storage cost, terms and pricing; obtain approval before any external posting or paid deployment.
