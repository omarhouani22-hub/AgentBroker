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


## HTTP beta API (not deployed)

The API source is `agentvault_api.py` and its tests are in `test_agentvault_api.py`.
Install dependencies in an isolated Python environment with
`pip install -r agentvault_requirements.txt`.
Configure `AGENTVAULT_KEY` (a persisted Fernet key),
`AGENTVAULT_TOKEN_HASHES` (JSON object mapping each agent ID to the SHA-256
hex digest of a random secret token), and `AGENTVAULT_DIR` (an encrypted,
backed-up **persistent** volume). Never commit credentials.

Start only behind HTTPS with `gunicorn agentvault_api:app`.
Send `PUT /v1/checkpoint` with binary payload, `X-Agent-Id`, and
`Authorization: Bearer <token>`; retrieve using `GET /v1/checkpoint`
with the same headers. Maximum request size: 1 MiB.
`GET /healthz` is informational and does not validate persistent storage.
No customer traffic should be accepted before storage durability, key recovery,
concurrency, quotas, monitoring and recovery drills are proven.

Run locally:
```sh
python -m unittest test_agentvault.py test_agentvault_api.py test_agentvault_paypal.py
```

**2026-10-24 verification note:** the API dependencies were not available in
the execution environment used for development, and package installation was
blocked by DNS/network access. Do not mistake committed tests for passed tests.
No PayPal live credentials or durable storage have been configured.
