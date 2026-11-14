# AgentVault — private recovery custody and isolated restore runbook (draft)

Status: **DRAFT / NOT PRODUCTION VERIFIED**. Prepared 2026-11-14. No authorization to handle production keys, customer data, or deploy.

## Keys and ownership
- `AGENTVAULT_KEY`: encrypts/decrypts checkpoint payloads. Must be retained privately by the authorized owner; a backup archive alone does not recover tenant plaintext.
- `AGENTVAULT_BACKUP_RECOVERY_KEY`: separately generated Fernet key for sealing *new* backup archives. Must differ from `AGENTVAULT_KEY`.
- `AGENTVAULT_OPERATIONS_TOKEN`: API authentication token, **not** a recovery/decryption key.
- Older archives made before the separation were sealed with the historical `AGENTVAULT_KEY`. Preserve that original key for legacy recovery; never assume the new backup key opens old archives.
- Never commit, email, paste in chat, include in CLI arguments, log, or store keys alongside the backup. Use an owner-controlled secret manager or offline encrypted vault with tested access and recovery, separately from the archive. Keep authorized access limited and documented. Avoid recording secret values in this runbook.

## Preconditions before a real drill
1. Obtain explicit authorization for exact backup source, destination, people, and acceptable operational risk. No production mutation.
2. Privately confirm key custody and whether archive is legacy or new; identify the correct archive key and original checkpoint key.
3. Obtain the *exact* archived bytes through an authorized private path. Record SHA-256, capture time, database consistency method, row counts, and encrypted storage location in a private evidence log. Do not publish these values if sensitive.
4. Use an isolated disposable environment with no network, no production credentials, no production database endpoint, no payments, and a temporary filesystem with adequate capacity. Ensure no secrets or customer payloads leak into logs.
5. Ensure input ZIP limits are suitable; the drill currently rejects ZIPs over 20 MiB and members over 16 MiB. A too-large legitimate archive is a **blocked drill**, not evidence of successful restore.

## Offline verification (example; placeholders only)
Supply `AGENTVAULT_BACKUP_RECOVERY_KEY` and `AGENTVAULT_KEY` privately through approved secret injection. For a legacy archive, supply the historical application key as the archive key **and** checkpoint key. Do not type keys directly into shell command arguments.

```sh
python agentvault_offsite_drill.py \
  --zip /private/path/agentvault-backup.zip \
  --sha256 EXPECTED_OUTER_ZIP_SHA256 \
  --key-from-environment \
  --checkpoint-key-from-environment
```

Do not run this command against live material without separate authorization and private safeguards. The script is a local disposable SQLite restore, **not** a PostgreSQL disaster recovery or durability test.

## Acceptance evidence
- Outer ZIP SHA-256 and internal encrypted archive checksum match independent records.
- Archive decrypts with designated archive key; wrong archive key fails.
- Every archived checkpoint decrypts with original checkpoint key and its tenant prefix/digest matches.
- All restored table rows equal snapshot rows; SQLite integrity and foreign keys pass; unauthorized tenant tokens are rejected.
- Temporary database is removed, secrets are absent from logs, and no network or production services were accessed.
- Separate operational test is still required for production PostgreSQL restore, durable storage, actual owner import/recall, and service lifecycle recovery.

## Stop conditions
Stop and do not mark `RECOVERY_VERIFIED` if: keys missing, mismatched, or untrusted; archive checksum fails; archive is oversized; row counts differ; any checkpoint cannot be decrypted; test environment is not isolated; production credentials are present; or the evidence is only synthetic.

## Current evidence
- PR #95 (draft): https://github.com/omarhouani22-hub/AgentBroker/pull/95
- GitHub Actions run #87: https://github.com/omarhouani22-hub/AgentBroker/actions/runs/43601724103 — 51 unit tests and 3 PostgreSQL tests passed, including separate-key CLI synthetic test.
- **Not yet verified:** actual production backup capture, separate owner custody, real isolated restore, PostgreSQL disaster recovery, production durability. No commercial release approved.
