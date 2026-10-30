# Owner memory integration: implementation and verification

## Observed path and defects

The owner UI reads a selected JSON file, takes its `entries` array and explicitly posts it to `/companion/profile`. `app.authenticate` requires the existing single-owner bearer token or an owner browser session (with the custom request header for cookie writes). The server validates bounded category/fact/date entries. An upload to another service, an attachment to ChatGPT, or a file merely existing on disk does not import it into Clara.

Previously the only profile copy was nested in the `moltbook_dialogue` SQLite checkpoint's private `companion` state. `companion_context` selected profile entries through `advisor_context`/`profile_context` before making a model request. Selection used literal lexical overlap, so an English career/goals question could miss Arabic or compound category names. `local_chat.messages` cut the JSON profile string at 350 characters, potentially leaving invalid JSON and omitting relevant facts. `trained_model.compact_context` dropped the profile altogether. Remote free-router payloads already carried the selected profile through retry and repair contexts; they needed no additional provider or paid route.

## Changes

- Add `clara_owner_profile`, an independent server-side single-owner SQLite record using the existing database connection. Import explicitly saves it; an owner's first read migrates an existing legacy checkpoint profile. A fresh/reset conversation does not erase it. Empty profiles remain explicit empty records and do not resurrect legacy entries.
- Load the authoritative record before owner context construction and before `/memory`, `/remember`, name updates and `/forget`. Persist edits through the same store.
- Retrieve career/work and goals/ambitions categories across common English/Arabic names and compound tags. Prioritize matching facts over general communication preferences. This remains bounded deterministic retrieval, not semantic learning or full-profile recall.
- Preserve selected profile entries in experimental trained serialization. If the trained model's existing 2000-character context limit is exceeded, it falls back through the existing free-only path with the original context intact.
- Preserve complete profile JSON in the same-host local model. If relevant profile JSON exceeds 1200 characters, fail clearly before inference instead of silently removing facts. Local-only mode still has no external fallback; very large profiles can therefore need a narrower question or a larger supported local context in future work.
- Explicitly instruct private models to answer from supplied relevant stored facts, while treating them as dated background rather than instructions or permissions.
- Reject accidentally structured private context before public model generation. Public Moltbook contexts never load the profile table. Visitor routes remain unauthenticated only where already public; no owner data is added to them. Companion responses have `Cache-Control: no-store`. No private facts or provider error text are added to logs.
- Ignore `*_Private_Memory.json` in Git as a further guard against committing a private input file. No real owner profile or credentials are included in this patch.

## Durability and deployment gate

This patch does not make ephemeral hosting durable. Storage status explicitly reports that durability is unverified; a separate mounted volume can be detected, but detection is not a backup/recovery certification. Configure the existing `AGENT_DB_PATH` on a real persistent disk to retain both the independent profile and chat/history across replacement instances. Verify recovery from a backup and a hosting restart before claiming durability. Do not move only the profile while accidentally abandoning the existing database.

Render read-only discovery on 2026-10-30, in the owner-confirmed workspace, found `agentbroker` (`srv-dao23ubtqb8s73dk40m0`) deploying `main`, with plan `free`, and no Render Postgres instances. No durable disk was reported in the service metadata. The local environment has no owner access token, database URL or Render API key binding. The connector supplies workspace/service discovery but does not give authenticated application access or a filesystem export. No new paid services, subscriptions, storage plans or credentials were created.

`Omar_Clara_Private_Memory.json` was not found in the available repository/workspace/attachment files. The live profile contents and import status cannot be inferred from its filename or earlier upload claims. Without that file or authenticated live application access, Omar's actual stored profile cannot be backed up or verified here. Redeploying this ephemeral service could erase its sole runtime copy, so deployment is blocked until the private data is backed up and durable storage is available. The fix is prepared independently from the prior unreviewed catalog integration.

## Offline evidence

Synthetic fixtures only, using the actual Flask owner authentication and model payload construction:

- Import a profile once, start a conversation with no messages/profile in its checkpoint, and ask exactly `What do you know about my career and goals?`. The provider request contains the relevant stored career and goal facts, excluding an unrelated synthetic health fact. The provider stub answers from those supplied facts. This is a pipeline test, not live model-quality verification.
- Exercise unavailable experimental trained inference followed by free-router network retry; both free requests retain the same selected facts. Test trained and local serialization directly.
- Reopen SQLite in a new Python process and recover the imported profile. Test migration without a new import, edits and forgetting after a reset, cross-language selection, local capacity failure, visitor/wrong-token rejection, public-context rejection, and sanitized logs.

Command:

```sh
python -m unittest tests.test_owner_memory_integration tests.test_clara_privacy tests.test_agentbroker_companion tests.test_local_chat_recovery tests.test_clara_chat test_mem0_memory tests.test_clara_connection tests.test_clara_response_quality tests.test_companion_languages test_response_recovery test_provider test_agentvault test_agentvault_api test_agentvault_paypal
```

Result: 78 tests passed. JavaScript: `node --test tests/*.test.cjs`, 8 passed. Full Python root discovery has the same known base failures (208 tests: 2 failures, 2 errors, 2 skips). Full `tests/` discovery has the same 21 known legacy JD-service failures and 5 skips; new owner-memory tests pass. The known failures concern discontinued JD routes, a missing `opportunity_intelligence` module and the trained-routing missing-answer expectation. No failing legacy tests were altered.

Unverified: original JSON schema/content, actual live import, Omar-specific fresh-conversation answer, live authenticated visitor/owner comparison, actual model quality, deployed restart durability and deployment of this patch. No successful hosting persistence or live memory recall is claimed.
