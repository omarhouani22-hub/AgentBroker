# AgentVault — evidence and decision register

Last reviewed: 2026-11-14. This is a review-only record, not a release approval.

## Strategic decisions
- Initial customers to investigate: independent AI-agent developers and early AI startups.
- Positioning hypothesis: persistent memory and recovery for AI agents. Do not promise uninterrupted execution or general-purpose memory without proof.
- Validate customer need before selling. No verified customers, revenue, or willingness to pay recorded here.
- No production deployments, merges, live payments, customer uploads, outreach, advertising, or paid resources without separate explicit approval.
- Do not put customer data, credentials, or government workplace information in this repository.

## Verified repository observations
- Repository: omarhouani22-hub/AgentBroker.
- Reviewed branch: feat/agentvault-service-launch-20261024.
- The following files were read from that branch: agentvault_backup.py, agentvault_offsite_drill.py, test_agentvault_backup.py, test_agentvault_offsite_drill.py, agentvault_service.py.
- On 2026-11-14, agentvault_backup.py, agentvault_offsite_drill.py and test_agentvault_backup.py were not found on main. The service-launch branch was previously compared to main and found diverged; it must not be treated as already merged or deployed.
- The offsite drill checks the outer ZIP SHA-256, inner archive SHA-256, checkpoint decryption/digests, SQLite integrity, foreign-key integrity, and table row equality. The test suite contains synthetic-data cases; reading the tests is NOT evidence they passed.
- The drill rejects ZIP inputs over 20 MiB and ZIP members over 16 MiB. This is a code-enforced capacity limit, not a validated production capacity policy.
- The drill rejects a snapshot embedding the application encryption key and expects the key separately. It restores into temporary isolated SQLite, not production PostgreSQL.
- The offsite drill's optional synthetic probe is separate from archived data. Passing a synthetic probe must never be represented as proof of recovering a real customer's private checkpoint.
- The service requires external PostgreSQL outside test mode and gates sales on both SALES_ENABLED and RECOVERY_VERIFIED, plus payment configuration.

## Unverified release gates
1. Real consistent production backup captured and stored privately off-service, with separately controlled key and verified checksum.
2. Isolated restoration of that exact real backup, with integrity and row-count comparisons and verified private checkpoint retrieval.
3. Durable production storage and recovery after service lifecycle events.
4. Green CI on the exact intended release commit; security and authorization checks.
5. Verified owner import/recall and browser/session behavior.
6. Explicit approval before any production change or commercial launch.

## Next safe action
- Run isolated synthetic boundary tests for ZIP >20 MiB, members >16 MiB, malformed ZIP and zip-bomb expansion; measure expected legitimate backup size and set an explicit bounded capacity policy.
- Then verify the actual offsite backup and restore only through a private authorized route. Never place archive bytes, keys, tokens or personal data in CI logs, issues or chat.
- Keep all experiments on a branch not watched by Render auto-deploy. This documentation branch is not an authorization to merge or deploy.

## Evidence discipline
Use status labels: VERIFIED SOURCE, TEST PASSED (with run URL), PRODUCTION VERIFIED (with private evidence reference), BLOCKED, or HYPOTHESIS. A source-code inspection alone is VERIFIED SOURCE, never TEST PASSED. Record dates, commit SHA, and limitations before changing any gate status.


## Progress update — 2026-11-14 (latest)
- TEST PASSED: PR #94, GitHub Actions run #79, https://github.com/omarhouani22-hub/AgentBroker/actions/runs/43601166241 — 47 unit tests and 3 PostgreSQL tests passed. Five ZIP boundary tests verified in logs.
- TEST PASSED: PR #95, GitHub Actions run #85, https://github.com/omarhouani22-hub/AgentBroker/actions/runs/43601619397 — 50 unit tests and 3 PostgreSQL tests passed, including the legacy-archive compatibility test.
- VERIFIED SOURCE: on draft PR #95 branch `fix/agentvault-offsite-key-separation-20261114`, the backup endpoint was changed to require `AGENTVAULT_BACKUP_RECOVERY_KEY` distinct from `AGENTVAULT_KEY`, failing closed when absent or equal. These changes were tested by run #85.
- VERIFIED SOURCE, NOT YET TEST PASSED: latest commit `cca65bfddd589e2dc26cf876ab2615f4aab61582` modifies offsite-drill CLI to accept both archive and checkpoint keys independently and adds a synthetic CLI test verifying recovery without network or secret output. No CI result was confirmed for this commit at the time of this record.
- Important cryptographic distinction: opening the backup archive with its recovery key does not decrypt tenant checkpoints without the separately retained original application key. The live recovery-key custody/escrow mechanism remains unverified.
- BLOCKED: no actual production backup was accessed, transferred, or restored. No durable off-service archive and key custody verified. Do not mark RECOVERY_VERIFIED true.
- NO CHANGE: draft PRs #94/#95 remain unmerged; no Render deployment, payment activation, customer uploads, or paid resources authorized.
- NEXT: confirm CI on latest commit; independently review backup/tenant key handling and legacy archive compatibility; require explicit operational approval and private key-safe process before real offsite backup/isolated restore.

- TEST PASSED (2026-11-14): latest PR #95 commit `cca65bfddd589e2dc26cf876ab2615f4aab61582`, GitHub Actions run #87, https://github.com/omarhouani22-hub/AgentBroker/actions/runs/43601724103 — 51 unit tests and 3 PostgreSQL tests passed; log explicitly confirms separate-key CLI synthetic test passed.
- DOCUMENTED (not production verified): `docs/AGENTVAULT_PRIVATE_RECOVERY_RUNBOOK.md` provides owner key custody, legacy archive handling, isolated restore procedure, acceptance evidence, and stop conditions. No production secrets or archives accessed.

## Owner custody confirmation — 2026-11-14
- OWNER REPORTED: owner downloaded and saved a copy of the encrypted AgentVault backup artifact from GitHub Actions run `41279756795`, artifact `13073085820` (created 2026-11-01, retention expiration 2026-11-15). This is a self-report, not independently verified durable offsite storage.
- OWNER REPORTED: original encryption key is retained separately from the encrypted archive. No key value was requested, shared, or stored in this repository.
- VERIFIED ARTIFACT METADATA: GitHub reported the backup artifact as unexpired at discovery; it was downloaded through the GitHub connector. Do not interpret download as decrypted or restored data.
- BLOCKED: no real isolated restore or checkpoint retrieval has been performed. Next step: select a local Windows/Mac or appropriately isolated machine and run a key-private restore with the owner; never transmit keys in chat.

## Reconciliation — 2026-11-16 (non-production documentation only)
- The 2026-11-14 lines saying the latest PR #95 commit lacked a confirmed CI result were superseded by the later TEST PASSED entry for run #87. Do not treat those statements as current blockers.
- Owner reports holding the encrypted ZIP and the original key separately; this does not establish that the archive is complete, that durable offsite storage is proven, or that its contents can be restored.
- Owner has only an iPhone for now and explicitly deferred the real private restore until a Windows/Mac is available. Do not request keys in chat or initiate a paid restore service.
- VERIFIED SOURCE: Clara's `moltbook.py` in branch `feat/agentvault-moltbook-publish-button` contains `GET /moltbook/status` and `POST /moltbook/posts`; `MOLTBOOK_API_KEY` is read at runtime. Source inspection is not proof that this branch is deployed.
- OWNER-PROVIDED SCREENSHOT: live Moltbook status showed `connected=true`, `claimed=true`, username `agent_broker`, and prior introduction published. This proves the account connection at screenshot time, not publication of a new AgentVault post.
- BLOCKED: no authenticated, authorized outbound invocation of Clara's post endpoint is available through the currently connected tools; **AgentVault marketing post not verified as published**. Do not imply otherwise or retry blindly.
- Operational priority: validate the exact real backup privately when an appropriate isolated computer is available; independently, keep market-validation preparation distinct from customer outreach and publication. No change to production, billing, or release flags.
