# AgentVault operator runbook — 25 October 2026

Sales remain closed until the launch gates in AGENTVAULT_LAUNCH.md are satisfied.

## Payment review

Run `python agentvault_reconcile.py` only in the existing service environment, using its existing credentials. This performs PayPal GET lookups for already paid orders; it does not create, capture, refund or transfer money. Review `verification_failures` immediately: errors never count as verified payment status. A confirmed non-completed capture is put on `payment_hold`. Writing, new orders and capture are blocked for that vault; read/export remains subject to existing retention. Never clear a hold automatically or create a replacement charge. Investigate the provider transaction and contact the customer without requesting vault secrets. Partial refunds require an operator decision about remaining service; the command conservatively holds writes.

This command is NOT yet scheduled. Before sales, establish a documented regular run plus action after every refund/dispute notification, and test a real Sandbox refund/reversal. Mocked status tests alone do not establish provider event delivery.

## Encryption key custody

The owner must retain the original AGENTVAULT_KEY from the AgentVault service's Render environment in an independent password manager or equivalent protected secret store. Never regenerate the key, paste it in chat, commit it, place it in customer downloads, or store an encrypted envelope together with its recovery key. Copying it to this shared workspace was previously blocked and must not be retried by an indirect path. Owner confirmation of custody is necessary but is not proof of recovery: independently restore a database snapshot plus that original key and verify synthetic plaintext bytes/digest before marking recovery verified.

## Backups and maintenance

`agentvault_backup.py` can validate authenticated encrypted logical snapshots and restore only into a new local SQLite destination without overwrite. PostgreSQL CI uses synthetic keys and contents and proves a PostgreSQL logical snapshot can be restored and decrypted; it does not prove recovery of the original production key. Automated offsite backup is not configured. Establish a protected destination, separate key custody, retention and recovery checks before sales. `python agentvault_ops.py maintenance` removes expired checkpoint content after the documented grace period and prunes audit/limit records; schedule it only after backup protection is in place.

## Launch decision

Require real Sandbox purchase, actual PostgreSQL concurrency, original-key backup recovery, scheduled operational reviews/backups/maintenance, refund/reversal evidence, Live merchant eligibility and accurate support/privacy/terms. Keep SALES_ENABLED=false and RECOVERY_VERIFIED=false until these are evidenced. No Live capture is authorized by the earlier unapproved Live diagnostic order.
