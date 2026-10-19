# Maintenance cycle: 2026-09-28

## Baseline and scope

- Inspected actual source at `main` commit `c7c71f40061762d00463d08de343c1c3f872fbd5`. GitHub Deployments showed the same commit as the latest successful Render deployment (2026-09-27).
- Read-only production checks: `/health` HTTP 200, `ok: true`, version `1.6.0-hermes-pilot`; `/` HTTP 200. The health response reports `hermes_runtime_installed: false`. These checks do not establish provider balances, working credentials, live research completeness, or autonomous learning.
- Source authentication is bearer-token based. No authenticated production session or server backup was obtained. Live persistence and provider execution remain unverified. No paid model calls were made.
- No Notion integration was found in the inspected source tree. Continued use of the former Command Center could not be established: this execution environment returned HTTP 403. This is not evidence of an outage or abandonment. Its files were not changed.

## Proven defect and bounded fix

`team_provider._call` accepted any nonempty text, even when the provider reported `finish_reason: length`. The default dual-model route also uses this transport in single-provider mode. A mocked `/runs` request with an incomplete model answer returned HTTP 200 before the change.

The fix requires a well-formed response, a `stop` finish reason, nonempty text, and at most 200,000 bytes. Incomplete, filtered, tool-only, malformed, and oversized responses fail before being treated as successful answers. Validation errors do not trigger transport retries. Existing transient transport retries and completed-draft fallback are retained. No prompts, credentials, billing settings, schema, or data are changed.

## Measurement and verification

Command: `python3 -m unittest test_team_response test_app test_offer -v`

- Before: the synthetic truncated-answer integration test failed because `/runs` returned HTTP 200 instead of the expected error.
- After: `/runs` returns HTTP 502 with failed status; authenticated `/knowledge` stays empty in the isolated temporary database.
- An incomplete dual-model review makes exactly two transport calls, returns the already complete draft, and does not save a lesson.
- Complete responses remain unchanged. Invalid responses are not retried.
- All 15 tests passed. Providers and search were mocked; no private data or paid requests were used. These results establish handling of provider termination metadata, not factual accuracy or semantic completeness of every answer.

## Publication, backup, and rollback

The tested change is prepared on a separate branch, not merged or deployed. Connector branch creation was denied (HTTP 403); the authorized GitHub browser session was used for the review branch. Render currently requires sign-in. No production backup was taken, so deployment is held.

Before merging, establish authenticated access and securely back up the complete SQLite database (including knowledge, documents, and team lessons), or verify that no at-risk data exists. Do not commit private backups to this public repository. Confirm actual production storage durability; the checked-in Render configuration specifies the free plan and does not define a persistent disk.

After backup: recheck `main`, merge only the bounded change, verify Render deployment commit and `/health`, then verify authenticated read access and retained data. A live paid research call is optional and must stay within the cycle's two-call maximum. If rollback is necessary, revert this change and redeploy the previous commit; restore the secured database backup only if data loss occurred. No schema migration is required.

## Ranked follow-up backlog

1. Release this tested response-integrity fix after the backup/access gate is satisfied.
2. Verify durable private storage and complete backup/restore coverage before further unattended deployments.
3. Validate and deduplicate saved team reviews; do not label generated reviews as verified knowledge without source checks. Treat retrieved lessons as untrusted data.
4. Make private-document answers follow the request language; the inspected path currently requests English explicitly.
5. Measure provider latency and cost by stage before changing retry or multi-model budgets.

Legacy Hermes/watch automations remain disabled. Application and memory improvements are not model-weight training or evidence of continuous learning.
