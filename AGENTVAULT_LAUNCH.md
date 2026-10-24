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

1. Supabase project eebmqxxxxzdddrpmbmvj was restored on its existing free plan.
   The five agentvault tables were created in an isolated private schema, RLS enabled,
   with no direct anon/authenticated access. Runtime access remains blocked: automatic
   approval review rejected creation of a login role with CRUD policies because the
   exact credential recipient and permission scope require user approval. No such
   login role or policy was created. Approve any infrastructure expense separately.
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

## Current hosted state

Launch candidate: https://agentvault-service.onrender.com/
Console: https://agentvault-service.onrender.com/console
The earlier https://agentvault-preview.onrender.com/ now links to this console and docs.
Render service: srv-dbedrd0473hc73d098gg, free plan, sales disabled.
Source branch: feat/agentvault-service-launch-20261024; draft PR #66.
Wix editor authentication failed; a fresh verification page still requires login.
PayPal live merchant connection has not been made.
Database schema and access restrictions were verified using Supabase SQL.
Security advisors report expected no-policy information for the new closed tables;
pre-existing public.pp_* SECURITY DEFINER warnings belong to the older PeoplePilot app
(reference: https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable).
They were not modified as part of AgentVault.

Runtime permission requested: one server-only login for the AgentVault Render service,
USAGE on the private agentvault schema and SELECT/INSERT/UPDATE/DELETE on av_vaults,
av_checkpoints, av_orders, av_limits and av_audit only. No superuser, role creation,
database creation or bypass-RLS privileges; no access to PeoplePilot tables.
Do not retry the rejected grant until the user expressly approves that scope.


## Follow-up verification — 24 October 2026

The user approved the precise AgentVault runtime database permission scope.
The agentvault_runtime login was created with no superuser, CREATEDB, CREATEROLE,
BYPASSRLS or inherited roles. It has USAGE on agentvault and CRUD on its five
tables only. SQL verified no access to public PeoplePilot tables and no CREATE
privilege on the private schema. Runtime-only RLS policies permit those operations.
The previous approval block for this grant is resolved; do not repeat the request.

The application key and database credentials were stored in the AgentVault Render
service's environment, not in Git or customer-facing pages. The direct IPv6-only
Supabase connection was replaced by the Singapore Supavisor session pooler for
Render IPv4 compatibility. The live /healthz endpoint now returns status=ok and
durable_database=true. Sales and recovery_verified remain false pending the full
backup recovery/payment launch gates.

An operator-only synthetic vault was inserted for a real hosted drill. The live
API successfully saved encrypted state to PostgreSQL, returned byte-identical data
and the correct SHA-256 digest, and rejected a wrong secret with HTTP 401. Render
was independently redeployed (dep-dbee517b9u1s739dkpjg); the original checkpoint
was then recovered with identical bytes/digest. The authenticated deletion endpoint
removed the test checkpoints, and a database count confirmed zero remaining test
checkpoint rows. This proves restart persistence, not provider backup restoration.

PayPal developer dashboard sign-in succeeded using secure credentials and SMS
verification. Existing Live apps: Hire AI agent and MyApp_Payhip_Limited. Neither
was changed or reused. A new Live app creation form is prepared with name AgentVault
but was not submitted: it grants new payment API access and presents the Developer
Agreement (noted as US accounts only). Obtain action-time user confirmation before
creating the app and sharing its server-side credentials with AgentVault on Render.
No real charge, payout, payment settlement verification or sandbox checkout occurred.

Wix browser session was logged in as omarhouani22@gmail.com, which returned HTTP
403 for the required LocalSite Foundry site 3cbc13ce-b099-4bb1-b81f-5b9fff88ba6e.
The original connected site context belongs to the localsitefoundry account. The
browser was logged out of the personal account. Automatic review rejected returning
to the protected site before establishing the owner-account access prerequisite.
No workaround was attempted. The old custom-domain homepage remains unchanged.


## Verified follow-up — 25 October 2026 (Amman)

LocalSite Foundry's public ChatGPT Site was replaced by AgentVault version 8 at
https://localsite-foundry.omarhouani22.chatgpt.site/ . This is separate from the
previously discussed Wix custom domain; no claim is made that Wix was changed.

The owner explicitly selected Omar's Render workspace and approved a redeploy,
a synthetic recovery drill and one unapproved Live PayPal order for $5, with
no approval/capture. Deploy dep-dbeintrncjis73ecmfug ran the checked-in
`agentvault_ops.py recovery-drill` and `payment-check` commands. Both passed:
committed encrypted synthetic data survived application reconstruction, and
PayPal Live returned an unapproved order and a merchant identity. No payment
was captured. PAYPAL_MERCHANT_ID was then added to the existing Render service.
The temporary diagnostic build command was restored to dependency installation
only, so subsequent deploys do not create more diagnostic PayPal orders.

All 25 isolated tests passed locally, JavaScript syntax passed, and GitHub Actions
run 40137082715 passed. CI now includes the service and operator-payment tests
and runs on the service-launch branch. Provider responses are mocked in unit tests;
the server-side preflight is separate evidence of actual Live connectivity.

SALES_ENABLED and RECOVERY_VERIFIED remain false. The completed reconstruction
and earlier hosted restart checks do not establish recovery from an independent
database backup. A protected independent backup/key recovery drill and a completed
buyer checkout/capture/settlement check remain unverified. Do not mark those as
passed based on the unapproved order or enable sales merely to remove the gate.


## Independent data snapshot — 25 October 2026

A consistent single-statement export of the five AgentVault tables was saved to
owner-private external file storage, read back and restored into a new isolated
SQLite database. All rows matched exactly: one expired operator vault, two audit
rows, four limit rows, zero orders and zero checkpoints. This was a manual data
snapshot, not an automatic scheduled backup, a PostgreSQL physical restore, or a
successful recovery of production-encrypted checkpoint contents.

`agentvault_backup.py` adds authenticated encrypted portable backups and exclusive
local-only restoration. Tests cover restored bytes through the application API,
wrong recovery keys, archive tampering, tenant substitution, refusal to overwrite
an existing target, and honest data-only recovery status. All 28 isolated tests pass.
No snapshot or production encryption key is committed to Git.

Automatic approval review blocked copying the production encryption key into a
shared-directory envelope together with its recovery key. The incomplete envelope
and unused generated key were removed, the clipboard was cleared, and the attempt
was not retried. Production key escrow/recovery remains incomplete. The user must
approve a separate protected key custody arrangement before that gate can pass.

PayPal Developer public documentation was accessible, but automatic review blocked
navigation to PayPal account sign-in because financial-account login authority was
not established for this specific action. Do not retry account sign-in or use an
alternate route without explicit user approval. No Sandbox buyer payment or real
capture was performed. Sales and recovery verification flags remain false.
