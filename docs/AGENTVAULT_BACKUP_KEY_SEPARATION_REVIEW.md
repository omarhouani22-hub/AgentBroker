# AgentVault backup encryption key separation — security review

Reviewed 2026-11-14. Source: `agentvault_operations_api.py` on `feat/agentvault-service-launch-20261024`.

## Verified source observation

The `POST /internal/operations/backup` endpoint invokes:

```python
archive = seal_snapshot(encode_snapshot(rows), app.config['ENCRYPTION_KEY'].encode())
```

The same application `ENCRYPTION_KEY` is used to encrypt/decrypt tenant checkpoints in `agentvault_service.py`.

The archive does not embed the plaintext application key, which is good, but the archive and tenant ciphertext share a cryptographic secret. The endpoint's comment about the owner holding the original key independently describes custody, not cryptographic key separation.

## Risk and status

- VERIFIED SOURCE: backup and tenant data use the same Fernet key.
- HYPOTHESIS: an independently controlled backup recovery key could reduce the blast radius of a compromised app key, depending on key custody and archive content.
- BLOCKED: no production backup/recovery validation or proof of independent backup key custody.
- Do not change production settings or enable sales on the basis of this review.

## Safe remediation proposal — not implemented

1. Introduce a dedicated `AGENTVAULT_BACKUP_RECOVERY_KEY`, distinct from `AGENTVAULT_KEY`, sourced from a private secret store. Never log either.
2. Encrypt the logical snapshot using the backup recovery key. Tenant checkpoint ciphertext still requires the original application key for full recovery. Define a secure, separately controlled way to escrow the application key, or explicitly declare that the archive alone cannot recover plaintext checkpoints.
3. Add synthetic tests proving: backup key != app key; archive cannot be opened with app key; backup key alone does not silently claim plaintext checkpoint recovery; operator-provided separately escrowed app key allows isolated verified checkpoint retrieval; wrong key, corrupt ciphertext, and tenant substitution fail closed.
4. Confirm that the new backup format and rotation policy preserve restoration of older archives before considering deployment.
5. Perform a private off-service backup and isolated restore of real data only after explicit operational approval and a safe, non-logging handling path.

## Related constraints

- Existing offsite drill enforces 20 MiB ZIP and 16 MiB member caps; these limits need a documented capacity policy.
- No live key material, backup bytes, user data, or service tokens belong in GitHub, chat, or CI artifacts.
- No deployment, merge, payment activation, new paid resource, or customer upload authorized by this document.
