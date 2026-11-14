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
