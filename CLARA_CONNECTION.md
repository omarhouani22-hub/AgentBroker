# Clara connection monitoring

The owner workspace (`/owner`) and Clara Settings (`/clara/`) include a private
Command Center connection panel. Refresh reads configuration and the last observed
Clara generation without calling any model. The existing bearer/session controls
protect both connection APIs, including the existing cookie write header check.

Selected routing is distinct from observed routing: `CLARA_LOCAL_ONLY=true` uses
the same-host model; otherwise the saved experimental trained preference can use
local inference with the existing free fallback; ordinary conversation uses the
fixed `https://openrouter.ai/api/v1/chat/completions`, `openrouter/free` route.
Provider-reported `model` metadata is displayed only when supplied and safe;
missing metadata is `unknown`. A requested router identifier is not a model name.
Local factual text rules are identified separately from inference.

The diagnostic sends a fixed greeting through Clara's existing generation adapter,
without loading private history, profile, documents, memory or tools. It reserves
one slot from the same configurable remote conversation allowance before generation,
uses the existing dialogue lock and bounded free retry/repair behavior, and never
calls the paid shared/team adapter. It returns validation outcome and elapsed
server time, not response contents. No provider switches, credentials, plan
changes, external logging, new services or paid fallback are added.

The application budget defaults to 50 remote attempts per UTC day. Owners can set
`CLARA_REMOTE_DAILY_LIMIT` on the server to an integer from 1 to 500; missing or
invalid values use 50. This does not increase OpenRouter's own quota. Messages,
requested new topics and connection tests share this budget. Failed attempts
still count, and internal model retries can consume multiple upstream requests.
Local-only inference bypasses this remote budget. Lowering the configured limit
does not invalidate a saved counter from a higher limit. Local exhaustion returns
`clara_daily_limit`; provider rate limits retain `provider_rate_limited`.

Only the latest completed generation's route, sanitized model identifier, UTC time,
latency and enumerated error category are kept in process memory. Observations
reset on restart and cover model generations through Clara's adapter, not local
read-only tool commands, presentation actions or all application activity. The
existing SQLite quota/storage durability remains dependent on host storage.

Storage negotiation, purchases and rental actions are not established by a
connection check. Clara's currently connected local tools are narrow read-only
status and saved-knowledge/file search operations.

Validation:

    python -m unittest tests.test_clara_connection tests.test_clara_response_quality tests.test_agentbroker_companion tests.test_clara_chat tests.test_clara_tasks tests.test_clara_privacy tests.test_clara_documents test_arabic_dialogue test_moltbook_dialogue test_response_recovery test_browser_session tests.test_companion_languages test_moltbook test_provider test_app tests.test_local_chat_recovery -v
    node tests/clara_connection.test.cjs
    node tests/clara_voice.test.cjs
    node tests/clara_camera.test.cjs
    node tests/clara_appearance.test.cjs
    node tests/clara_natural_voice.test.cjs
