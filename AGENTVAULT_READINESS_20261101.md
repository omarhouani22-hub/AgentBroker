# AgentVault readiness investigation — 1 November 2026

**Decision: HOLD. Production sales stay disabled.** This is an evidence review and a narrow local restore-reporting fix, not a launch authorization. No production backup endpoint, maintenance, reconciliation, migration, restore, payment mutation, deploy or hosting change was invoked. Read-only service/Actions metadata and public health/plans GETs were inspected. No secret values were read or printed.

## Checkpoint and scope

Reviewed PR #66 at `3f80a2ff460fd40f0aca87c1836e69ba8c54405a`, still open/unmerged, and its already completed evidence. The service uses `agentvault_service:app`, not the earlier file-based `agentvault_api:app`. New work is on a separate branch based on #66; the existing dirty local closed-trial/checkpoint refactor is excluded.

Current Render metadata: `agentvault-service`, free plan, branch `feat/agentvault-service-launch-20261024`, auto-deploy enabled, PR previews disabled. Live deploy `dep-dbfnuo942hec73ep8g80` reports commit `34e0bcf6600d4a091be372355cfd38a887ddb79e`; the later PR-head commits document evidence. A push/merge to the watched service branch can therefore deploy independently of merging #66 to main. Do not update that branch or change build/environment/health-check settings without approval.

## Evidence matrix

| Condition | Status | Evidence and exact limit |
| --- | --- | --- |
| Sales closed | **VERIFIED** | Public `/v1/plans` returned `sales_enabled=false` on this review. No checkout/capture request was made. |
| Database-backed service reachable | **VERIFIED**, limited | A follow-up `/healthz` GET returned `status=ok`, `durable_database=true`, `recovery_verified=false`. The first GET timed out after 25 seconds; follow-up was justified to distinguish that observation from persistent failure. No lasting outage or latency SLA is established. |
| Render-hosted Postgres | **VERIFIED absent** | Read-only instance listing returned none. This does not rule out the external database. |
| Production SQL backend | **VERIFIED**, limited | Service source rejects SQLite outside TESTING, uses psycopg with TLS and a dedicated schema. The successful health query establishes application access to PostgreSQL; its durable_database flag is simply Store.pg, not an independent durability/DR certification. |
| External provider, persistence and disaster recovery | **NOT VERIFIED currently** | Historical notes identify an existing Supabase free project and application reconstruction tests. Live DSN/provider configuration, current provider retention/backup guarantees and infrastructure failover were not independently inspected; no production credential was exported. |
| Prior Sandbox checkout/capture/refund | **VERIFIED historical evidence retained** | Existing launch/scheduler notes record the completed Sandbox work. Not repeated. This is not Live settlement evidence. |
| Actual PostgreSQL integration tests | **VERIFIED historical CI** | Run [40358884872](https://github.com/omarhouani22-hub/AgentBroker/actions/runs/40358884872) completed successfully at 34e0bcf: unit job and three real loopback PostgreSQL concurrency/logical-recovery tests. No new PostgreSQL instance or real Sandbox transaction was needed for this narrow change. |
| Scheduled offsite backup transfer | **VERIFIED** | [41173913117](https://github.com/omarhouani22-hub/AgentBroker/actions/runs/41173913117), 31 October: download/digest, GitHub artifact upload and subsequent maintenance steps succeeded. Artifact **13032362417**, 1905-byte ZIP, is reported unexpired until **14 November 2026**. Only artifact metadata was read here; no production archive was downloaded. |
| Prior archive restore | **VERIFIED, narrowly scoped** | Render completion log at 2026-10-26T16:25:53Z: archive authenticated, five tables row-identical, FK/integrity checks passed, disposable DB removed; counts vaults=1, checkpoints=0, orders=0, limits=11, audit=2. A separately inserted synthetic probe passed API recovery. This is real logical recovery of that particular archive, not proof an archived customer checkpoint was recovered. |
| Latest production snapshot restore | **NOT VERIFIED** | No isolated restore of the 31 October artifact is established. Its current row counts/content and independently held original key were not accessed. Prior empty-archive/synthetic checks must not be promoted to current production-data recovery. |
| Physical Postgres restore / measured RPO and RTO | **NOT VERIFIED** | SQLite logical restore does not exercise a production Postgres replacement, infrastructure credentials or disaster failover. The recorded sub-second local drill duration is not end-to-end RTO. |
| Independent key recovery/custody today | **NOT VERIFIED currently** | Historical notes record owner key custody/decryption. Current owner-held key accessibility for the latest archive was not demonstrated here. Never copy the key to chat, GitHub or this shared workspace. |
| Ongoing operations | **VERIFIED**, limited | Existing main workflow schedules daily backup at 00:17 UTC and hourly bounded review at minute 37; 14-day GitHub artifact retention, 16 MiB transfer ceiling and maintenance after upload. Latest reviewed run 41253413682 completed review successfully and skipped backup; success alone is not proof a daily backup ran. Schedule delays are observable and are not an SLA. Alert delivery, independent retention beyond the GitHub account and quota/cost headroom remain unverified. |
| Configured Render health-check path | **FAILED configuration check** | Service metadata reports an empty healthCheckPath although the runbook specifies /healthz. The endpoint works on follow-up; automatic health supervision is not established. No setting was changed because that could redeploy. |
| Restore helper verification reporting | **FAILED before fix; regression fixed locally** | restore_local formerly reported checkpoint_integrity_verified=true solely because an embedded application key was present, including zero checkpoints. The new regression failed against the old code. The helper now requires at least one actually verified archived checkpoint and reports its count. |
| Live settlement and final commercial terms | **NOT VERIFIED** | Historical merchant-screen checks are not actual Live settlement. Seller/support/refund/privacy details, provider/region/retention disclosures and an explicitly authorized final Live payment remain launch gates. No Live financial action is authorized or performed. |
| PR/release authorization | **NOT VERIFIED / HOLD** | #66 remains unmerged; all approval, production-data protection and release gates remain open. |

### Source distinction for the October 26 evidence

The supplied checkpoint correctly warns that actual production-data recovery is not generally established. Repository notes contain additional narrow evidence: scheduled archive 12628766704 from run 40271160876 was restored in a disposable environment using the existing key without accessing the production database. The completion record explicitly says `archived_checkpoints_verified=0` and `separate_synthetic_probe_verified=true`. This review re-read that record and existing CI metadata; it did not rerun the drill or copy the archive/key. The historical archive remains distinguishable from the newer 31 October archive and from protected customer-content recovery.

## Configuration names — no values

| Name | Location/use |
| --- | --- |
| `AGENTVAULT_DATABASE_URL` | Render service environment → app DATABASE_URL. Required external PostgreSQL URI in production. The exact value/provider/credential is not exposed. |
| `AGENTVAULT_KEY` | Render/owner-held Fernet encryption key. Encrypts tenant-bound checkpoint content and the scheduled archive envelope; must survive deployments and have an independently protected recovery copy. Never rotate/regenerate casually. |
| `AGENTVAULT_OPERATIONS_TOKEN` | Narrow operations credential in the service and GitHub Actions secret. Backup/review/maintenance access; no DB, PayPal or encryption credentials are sent to Actions. The scheduler job uses local alias `OPERATIONS_TOKEN`. |
| `AGENTVAULT_OPERATIONS_ENABLED` | GitHub repository **variable**, not an application environment setting. Gates the already installed operations workflow. |
| `AGENTVAULT_PUBLIC_ORIGIN` | Exact canonical HTTPS console/API origin. |
| `AGENTVAULT_SALES_ENABLED` | Explicit sales gate; remains false. |
| `AGENTVAULT_RECOVERY_VERIFIED` | Operator sales prerequisite; currently false. An attestation flag, not an automated backup verification result. |
| `PAYPAL_ENVIRONMENT` | Sandbox/live API selection, independent of sales/recovery gates. |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_MERCHANT_ID` | Server-side payment credentials/expected merchant identity. Names only; values were not inspected. |
| `AGENTVAULT_TEST_POSTGRES_URL` | Disposable, loopback-only CI test database; never a production fallback. |
| `AGENTVAULT_DIR`, `AGENTVAULT_TOKEN_HASHES` | Earlier file-based prototype settings in agentvault_api.py; **not** durable-storage configuration for the deployed service entry point. |

No S3/R2/B2 destination variable is used by the current scheduled backup: GitHub Actions artifacts are the implemented offsite destination. The app's database schema is selected in code/app config, not by a documented schema environment variable. No service configuration was changed or secret value queried. Local production database/key/operations credentials are not configured in this environment.

## Backup and recovery mechanics inspected

The operations endpoint authenticates a distinct token, writes its bounded rate bucket, then takes a REPEATABLE READ READ ONLY PostgreSQL transaction across all five tables. It seals a data-only logical snapshot with the existing application key, excludes that key from the payload, and supplies a transfer checksum. Consequently, even a backup request has a production rate-limit write/export effect; it was not invoked during this review.

The scheduler validates the response/digest, uploads the encrypted archive with 14-day retention, and only then invokes data-pruning maintenance. Dispatching this existing workflow is therefore production-affecting and requires approval; it must not be used merely to repeat a readiness test. A backup HTTP 200 establishes neither durable offsite retention nor restore success by itself.

restore_local exclusively creates a new local SQLite file, refuses overwrite and does not restore to PostgreSQL. Embedded-key manual snapshots can verify checkpoint plaintext during open_snapshot; scheduled data-only snapshots require the owner key and the separate offsite drill to verify their ciphertext. The two archive types and empty/nonempty checkpoint counts must remain distinct.

## Safe change and tests

Only restore-result reporting and its documentation/tests changed. No schemas, connection logic, payment flow, sales flags, schedule, provider configuration or live runtime behavior were altered. The extra `archived_checkpoints_verified` field counts actual plaintext integrity checks by this helper; data-only archives and empty archives report zero. The existing offsite drill can separately verify a data-only archive using its supplied original key.

New regressions failed before the fix (false positive plus missing count) and passed afterward. **8 targeted tests passed** with:

```sh
python -m unittest -v test_agentvault_backup test_agentvault_offsite_drill
```

Repeating these local fixture tests was justified by the changed shared restore helper and its offsite caller. The already completed real Sandbox/payment drills, prior real PostgreSQL CI integration tests, production restore drill, and scheduled backup were not repeated. Python compilation and git diff --check passed. Repository-wide legacy Clara/JD failures were not retested or represented as green; this investigation concerns the isolated AgentVault change.

## Single next action

**Approve an owner-private isolated restore of the latest existing offsite production snapshot, artifact 13032362417 from 31 October, using the independently held original key.** Check the archive/digest, all restored table rows, and tenant/byte/digest integrity of every archived checkpoint; explicitly report zero if none exist. Do not insert a synthetic probe and present it as recovered production content. Keep plaintext/key inside the private isolated runtime and retain only aggregate evidence. Record the snapshot date and end-to-end recovery timing.

Use the already exported artifact; do not dispatch the maintenance-coupled workflow, create a new production record or change hosting as part of this action. It still requires an approved private execution/key-access arrangement; no key should be pasted into chat or copied into this workspace. Successful recovery would close that evidence gap, not automatically authorize real payments or clear the remaining storage, health supervision, Live settlement, commercial and deployment gates.
