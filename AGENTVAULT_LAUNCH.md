# AgentVault launch candidate — 24 October 2026

This implementation is **not yet a live commercial service**. Sales default off.
The LocalSite Foundry Wix homepage has not been replaced; browser authentication
is required because the existing site uses Wix's editor. Do not confuse the
separate Render preview/API with the paid custom domain.

## Implemented

- Product homepage, Starter offer ($5 USD / 30 prepaid days), console, API guide,
  launch-candidate service terms and privacy text.
- Vault creation with one-time secrets; only secret hashes are persisted.
- Authenticated server-side encryption, tenant-bound ciphertext, version history,
  SHA-256 integrity, 1 MiB requests, five versions, 10 MiB quota.
- External PostgreSQL for production; SQLite accepted only in tests. Atomic
  transactions and per-vault row locks serialize storage and entitlement changes.
- Dedicated private `agentvault` schema and restricted table permissions/RLS.
- PayPal create/capture, server-controlled amount, merchant validation, idempotent
  entitlement grant and read-only reconciliation of ambiguous captures.
- Expiry/write blocking, seven-day read/export grace, explicit checkpoint deletion,
  persistent rate limits, audit events, maintenance and synthetic recovery command.
- Sales gated by explicit configuration, verified recovery, live PayPal and merchant ID.

## Required deployment settings (server-side secrets only)

Use `agentvault_service:app`, not the earlier `agentvault_api:app` prototype.
Build: `pip install -r agentvault_requirements.txt`
Start: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 45 agentvault_service:app`
HTTP health check: `/healthz` (503 until database/key/schema ready).

- `AGENTVAULT_DATABASE_URL`: dedicated external PostgreSQL credential. Use a least
  privilege runtime user with SELECT/INSERT/UPDATE/DELETE rights on the five tables.
  Schema migration may use a separate owner credential. Do not expose a Supabase
  service key or the database password to the frontend.
- `AGENTVAULT_KEY`: a generated Fernet key; persist an independently protected
  recovery copy. Never regenerate it on deploy.
- `AGENTVAULT_PUBLIC_ORIGIN`: exact canonical HTTPS origin serving console + API.
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_MERCHANT_ID`.
- `PAYPAL_ENVIRONMENT`: sandbox for staging; live only after merchant approval.
- `AGENTVAULT_SALES_ENABLED=false`, `AGENTVAULT_RECOVERY_VERIFIED=false` initially.

## Before enabling sales

1. Approve any infrastructure expense before provisioning it. There was no active
   external database during this run. The available Supabase project was inactive.
2. Configure the database and persistent encryption key. Run
   `python agentvault_service.py --migrate` once using the schema owner.
3. Run the full suite against an isolated **real PostgreSQL** database, including
   concurrent writes. The current 20-test result uses SQLite and mocked PayPal;
   it does not establish production/PostgreSQL or real payment correctness.
4. Run `python agentvault_ops.py recovery-drill`, restart the deployed service and
   independently restore/download a synthetic checkpoint. Separately restore a
   database backup plus the protected key into an isolated environment and compare
   plaintext digest. Record recovery time and data-loss window.
5. Establish an automatic external database backup, protect the encryption key,
   and schedule daily `python agentvault_ops.py maintenance`. Configure health and
   failed-payment monitoring. Test a failed transaction and payment reconciliation.
6. Run PayPal sandbox checkout with a real sandbox merchant/buyer and validate the
   merchant, amount, duplicate return, cancellation, refund and reversal workflow.
   Do not make a live payment without the user's explicit amount authorization.
7. Verify merchant settlement eligibility for the user's PayPal account. Enable
   live keys securely and complete the final authorized live verification.
8. Finalize provider names, regions and backup retention in the privacy page;
   confirm seller identity, support and refund terms. The included pages are
   launch-candidate drafts, not a claim of legal review.
9. Replace the editor-built Wix homepage with the prepared content, link the
   console/API origin, remove the $499 website-design offer, verify mobile layout,
   links, checkout and restore. Preserve the old site until the replacement works.
10. Only after all checks pass set recovery_verified=true and sales_enabled=true.

## Operational limits

This is compact agent checkpoint storage, not general storage rental. Starter
has no SLA, cross-region redundancy or zero-knowledge encryption. Customer secrets
cannot currently be rotated/recovered by self-service; securely retain the vault
access file. The operator must handle refund/reversal notifications and access
reconciliation before commercial launch. No automatic rebilling occurs.

Pending orders whose creation failed ambiguously remain reserved for operator
reconciliation. Never blindly re-charge. A capture that returned ambiguously can
be checked again via the console, which uses PayPal GET to reconcile.

## Verification performed

`python -m unittest test_agentvault_service test_agentvault test_agentvault_api test_agentvault_paypal -q`
20 tests pass. Includes unpaid write rejection, tenant isolation, encryption,
application reconstruction, retained versions, quota rollback, tamper detection,
expiry/grace, deletion, rate limits, amount/merchant rejection, payment timeout
reconciliation, no duplicate activation and route delivery. PayPal calls mocked.
JavaScript syntax checked with `node --check agentvault_site/console.js`.
