# Clara Growth Manager

Implemented as a separate feature on main `3f13dcc83ab671830eff91307d18659d91272556`. No deployment, sales activation, credential provisioning, real outreach, financial operation or paid model request is part of this change. Earlier owner-memory, avatar/audio and closed-trial work remain in their own branches/worktrees. This PR does not merge PR #66 or the local closed-trial prototype.

## Owner workflow

Open **Command Center · Growth Manager** from `/owner` or Clara's settings, at `/command-center/growth`. All CRM data, drafts, approval controls, reports and audit data require the existing owner bearer credential or authenticated browser session. Cookie writes retain the existing `X-AgentBroker-Request: 1` and SameSite controls. Visitors cannot see leads or owner notes.

1. Review the conservative product policy, then explicitly approve its immutable version. Public answers remain unavailable until this approval.
2. Select permitted public sources and enable discovery. The server's read-only worker, once configured, performs due cycles without further prompts: it finds evidence, classifies use cases, prepares educational drafts, generates the UTC daily report and proposes concrete next actions. No cycle can approve or publish.
3. Review each public use case before marking it reviewed. Follow-ups, consent status, conversations and feedback entered manually are **owner-reported**; they do not establish verified conversations, trial activation or revenue.
4. Inspect a draft, its immutable digest, target and public evidence. Editing retires the old approval and creates a new pending version. A separate approval is required for a standalone Moltbook post derived from a lead-specific educational draft.
5. Approval does not publish. A separate explicit confirmation is required for the exact approved bytes and destination. Approval expires after 24 hours; return the item to review to refresh it. Policy revocation blocks publishing even when an individual draft was approved. Source changes invalidate earlier review and pending/approved drafts.

Clara's existing private local-tool dispatcher recognizes `/growth`, `/growth next`, `/growth report` and `grow AgentVault`. It returns the current evidence-based next action and dashboard link without a model call or external action. Unrelated chat does not receive the Growth Manager dataset.

## Discovery, content and public answers

Moltbook discovery directly calls the existing API wrapper with GET `/agents/me`, `/search` and `/posts/{id}`. It deliberately avoids the older `research()` feedback workflow. At most three distinct full-post API results are considered per cycle; search hits whose full-post read fails are not leads. Clara's own account is excluded. Public GitHub issue search is unauthenticated, fixed to `api.github.com`, public issues and the checkpoint/restore use case, with at most three results. No arbitrary URL fetcher, private repository access or customer-account discovery is added.

Only bounded public excerpts are retained. URLs are validated, text is rendered with `textContent`, and email addresses, credential-shaped values and opaque tokens are scrubbed. External text is evidence only: no instructions are executed or activated. Signals reuse the existing market-intelligence patterns and require an agent/LLM context. These are fit hypotheses based on attributed public use cases, never fabricated customers or inferred willingness to pay.

The pipeline includes an owner-triggered synthetic demonstration using the existing repository `AgentVault` class, a throwaway directory, a fresh throwaway encryption key and a fixed synthetic payload tailored to the signal category. It saves encrypted data, reconstructs the local application, restores exact bytes, verifies SHA-256 and rejects a wrong token. The directory and key are discarded. Its evidence is labeled **isolated local prototype**, never deployed durability, real customer results or a trial activation. A separate pending marketing draft can cite this precise scoped result; it still requires policy/draft approval. No downloaded code, environment vault directory, production credential, customer upload or external service is used.

Drafts are deterministic educational material tailored to the observed state-loss, restore or privacy signal. A proposed SHA-256 save/reconstruct/restore demonstration is labeled unperformed. No service SLA, unlimited storage, zero-knowledge encryption, testimonial, deployed recovery success or actual customer is invented. Content preparation and approved product answers make **zero model calls**.

`POST /agentvault/advice` accepts only a documented topic: `product`, `demonstration`, `trial`, `limits`, `payments`, `support`. It returns only the current owner-approved policy statement, with its policy version and `generated_by=approved_documentation_lookup`. It does not accept free-text secrets, vault IDs or customer memory, execute tools, create tickets, modify entitlements or send a reply to anyone. This is a bounded documentation responder, not an unrestricted LLM or a connected third-party support inbox.

## External actions and approval safety

Publishing defaults disabled. Only owner-approved Moltbook comments and posts to the existing `general` destination have adapters. GitHub is read-only. There is no DM, email, bulk-messaging or social-account automation. The initial beta permits at most three external publishing attempts per 24 hours and at most one per target and public source account. These limits include failed/uncertain attempts.

For any publishing to be available in a later authorized deployment, the operator must explicitly set both `CLARA_GROWTH_PUBLISH_ENABLED=true` and `CLARA_GROWTH_DURABLE_STORAGE_CONFIRMED=true`, with an absolute persistent `AGENT_DB_PATH`. The durability flag is an operator attestation after recovery testing, not an automatic storage certification. This PR sets neither flag and provisions no storage. Do not attest durability for a free ephemeral filesystem.

A SQLite transaction validates current policy approval, exact draft digest, destination, expiration and beta limits, then persists a reservation **before** I/O. No model or worker can perform that approval. Timeout, process interruption or an ambiguous response cannot be retried automatically. A post is marked verified only when the provider returns a valid ID and echoes the approved content without a verification gate; otherwise it stays submitted-unverified or uncertain. Those states require operator investigation. A new draft targeting the same destination is also blocked for the day after an attempt. No automatic challenge solving or extra paid call is used.

`growth_actions` records every outbound read/write attempt before it occurs and its sanitized outcome afterward. Request paths, target IDs and public draft digests are retained; authorization headers, keys, customer checkpoint data and arbitrary provider error bodies are not. A reservation left by a crash is an unknown outcome, not a confirmed post.

## Verified business metrics

The dashboard separates:

- public use-case candidates and explicitly owner-reviewed public leads;
- actual public replies from that lead's account to a verified approved publication, or a signature-authenticated conversation event;
- staging trial activation, only after an authenticated committed-event receipt;
- actual USD net revenue, only from authenticated **live merchant-settlement** and reversal receipts. Sandbox orders/captures are rejected and list prices are never multiplied by lead counts;
- trial-to-paid conversion: distinct verified activated leads with a verified settlement divided by distinct verified activated leads. It is a historical cohort measure, not a claim of currently paying customers.

Absent trial/revenue connections show `null` / **Not connected**, not invented zero revenue or a conversion rate. Growth Manager never creates/captures payments, issues refunds, discounts, extends access, changes sales flags or grants trial access. A reversal receipt records an external fact; it does not issue a refund.

`POST /growth/receipts/trial` and `/growth/receipts/revenue` authenticate HMAC-SHA256 over the exact raw body using separate optional server-only keys, `CLARA_GROWTH_TRIAL_RECEIPT_KEY` and `CLARA_GROWTH_REVENUE_RECEIPT_KEY`. No issuer keys were created/configured here. These narrowly scoped ingress routes do not require or expose the full owner credential. All other Growth Manager routes remain owner-authenticated.

The exact receipt schema is `{id, lead_id, kind, occurred_at, amount_minor, currency, environment, evidence_kind}`. Event IDs are issuer IDs, not credentials or customer secrets. Types, known lead, source scope, timestamp, amount and currency are validated. Replays are idempotent; conflicting reuse of an ID is rejected. Trial kinds are `trial_activated` (evidence `committed_trial_activation`) and `conversation_verified` (`authenticated_conversation`), environment `staging`, amount `0`, currency empty. Revenue kinds are `revenue_settled` and `revenue_reversed`, environment `live`, evidence `merchant_settlement`, positive integer USD cents. An issuer must establish the underlying business fact before signing; a signature authenticates an issuer, not an independently audited bank statement.

**Issuer-side adapters are not connected.** The trial integration and AgentVault service on PR #66 are separate from main; this patch does not create a production database reader or infer settlement from their paid/captured order fields. No inbox, CRM, trial or merchant integration is claimed live. Wiring a least-privilege event issuer and verifying real receipts is remaining integration work; until then these metrics remain unconnected.

## Autonomy and storage

`CLARA_GROWTH_WORKER_ENABLED=true` enables a lightweight in-process daemon using existing server resources. It checks every minute and scans permitted sources at most hourly. The database lease serializes concurrent workers and survives process reconstruction. Settings default off with no permitted sources. One owner opt-in plus server worker configuration is required; subsequent discovery, drafting, reports and recommendations are proactive, with no per-lead manual command. No GitHub schedule, external messaging, subscription or new service is activated by this PR.

The worker is best effort only while the host runs. Free-host sleep, restarts and source quotas mean no always-on monitoring or punctual daily delivery is promised. The daily report includes new use cases and action outcomes for the UTC day, lifetime metrics as of generation time, pending reviews and next actions. It is private on the dashboard; no report is posted, emailed or uploaded externally.

All eight new `growth_*` tables use the existing owner database. SQLite file persistence across a fresh process is tested; deployed host durability is unverified. These tables are **not silently added to any pre-existing encrypted checkpoint or approved offsite export**. Private backup/recovery coverage must be reviewed before enabling publishing. Public-source records are bounded excerpts; private owner notes must omit contacts and secrets. No owner's uploaded profile, private conversation memory or checkpoint contents are read into this feature.

## Verification

The feature suite covers authentication/CSRF, public policy isolation, source failure, actual full-post evidence, own-account exclusion, inert/scrubbed external text, autonomous read-only cycles, immutable approvals, evidence-change invalidation, exact-byte publishing, concurrency/reservations, crash/timeout safety, receipt isolation/idempotency, live-vs-sandbox revenue, public conversation evidence, process reconstruction and private Clara tool routing. Every source, customer and settlement in tests is explicitly synthetic; providers are mocked.

Commands and observed results are recorded in the PR. Full root and `tests/` discovery retain legacy failures reproduced on the untouched main checkout; those tests were not weakened. No real prospect discovery, publication, financial transaction, customer activation, hosted worker execution or deployment was performed. Browser visual review is separate from the DOM/API tests and is reported only if actually run.

### Checks actually run for this PR

- `python -m unittest tests.test_growth_manager`: **26 passed**, including a real encrypted synthetic local prototype demonstration; no live service involved.
- `python -m unittest tests.test_growth_manager tests.test_agentbroker_companion tests.test_clara_privacy tests.test_english_interface test_provider test_memory test_agentvault test_agentvault_api test_agentvault_paypal test_agentvault_market_intel`: **72 run, 1 skipped, no failures**.
- `node --test tests/*.test.cjs`: **9 files passed**, including dashboard rendering, inert untrusted source text, unsaved-edit approval rejection and read-only polling.
- Python compilation, JavaScript syntax and `git diff --check` passed.
- Full root discovery: **208 run, 2 failures, 2 errors, 2 skips**, reproduced on untouched main. These are legacy retired JD offers, the missing `opportunity_intelligence` module and trained-routing's missing-answer expectation.
- Full `tests/` discovery: **167 run, 21 failures, 5 skips**; the same 21 legacy discontinued JD-service failures reproduce on untouched main. No baseline failures were masked or changed.
- Chromium visual review was attempted but blocked by the executor's socket sandbox; no browser visual or live integration success is claimed. The private API and DOM behavior checks above did run.

The `actual_*` metrics are based only on received verified-issuer events, not a complete audit of all business activity. Issuer completeness, live public APIs, hosted scheduling, deployed storage recovery, real settlement receipts and external publishing remain unverified/unconnected. No merge or deployment was performed.
