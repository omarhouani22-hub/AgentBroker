# OpenScience research bridge

This optional bridge uses the documented OpenScience CLI JSON event contract:
https://www.openscience.sh/docs/automation
https://github.com/synthetic-sciences/openscience

It supports a private literature review or original book manuscript. It does not yet publish books, post announcements, save unreviewed manuscripts into knowledge memory, or schedule automatic runs. Existing Moltbook routes remain available separately. Model completion is not evidence of scientific accuracy or publication readiness.

## Deployment requirements

The Render build installs upstream OpenScience 2.0.151 (Linux x64 baseline), verifies its pinned SHA-256, and extracts only the executable. Build and connection checks never dispatch a model or purchase credits. Keep the bridge disabled until an operator has tested the runtime and configured its research permissions. The CLI denies new permission requests; denied requests return a failure rather than silently broadening access. A separate temporary cwd/config/data directory and a restricted environment avoid inheriting AgentBroker credentials; this is not an OS sandbox.

Environment settings:

- `OPENSCIENCE_ENABLED=1` enables requests.
- `OPENSCIENCE_EXECUTABLE` defaults to the pinned `.openscience-runtime/openscience` binary.
- `OPENSCIENCE_WORKSPACE_API_KEY` is the Synthetic Sciences workspace key (`osk_` or legacy `thk_`). This is different from a model-provider key.
- `OPENSCIENCE_ALLOW_MODEL_USAGE=1` is required before any research request can dispatch a model. Leave it unset until the owner approves model costs.
- `OPENSCIENCE_MODEL` explicitly selects `provider/model`.
- `OPENSCIENCE_PROVIDER_KEY_ENV` optionally selects one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`.
- `OPENSCIENCE_PROVIDER_API_KEY` is the dedicated provider credential, supplied through secrets. Other app credentials are not inherited.

No new spending is enabled by default. Configuring a hosted provider and executing a request can incur model costs; CLI permission denial is not a billing cap. For local model/provider configuration or retained research permissions, use a separately managed runtime and the official SDK instead of this ephemeral CLI adapter.

## API

All routes use AgentBroker's existing authentication:

- `GET /openscience/status`: authenticated runtime, connection and spending-gate flags.
- Public `/health` includes redacted connection flags. It launches a background check, cached for five minutes, using only GET `/api/cli/balance` and GET `/api/v1/auth/status` on `https://app.syntheticsciences.ai`. It verifies the workspace scope, never returns a key, user or organization identifier, or balance amount, and never sends a model request. `connected=true` proves account metadata access; it does not prove successful research.
- Each authorized research run performs the official headless workspace-key login inside its temporary runtime directory, with all output suppressed, before dispatching the selected model. Credentials are discarded with that directory.
- `POST /openscience/runs`: `{"request_id":"unique-request-001","topic":"AI for HR","language":"English","mode":"book"}`. `mode` can also be `review`; language can be `Arabic`.
- `GET /openscience/runs/<request_id>`: private saved status/output.

Reserve and retain the request ID before calling. Reusing it returns the saved completed output or a conflict while running/failed, never another model request. A changed input with the same ID conflicts. Process timeout kills its process group. After a crash or timeout, inspect OpenScience's state before deciding whether to use a new ID; there is no automatic retry. Checkpoints use the existing SQLite database; ephemeral Render storage can lose them on redeployment. Do not enable recurring jobs without durable persistence.

## Remaining production pipeline

1. Verify workspace-key connection, select an available model, approve its costs, and test a research-capable run including literature access.
2. Add reviewed manuscript/source metadata to private knowledge storage.
3. Connect the actual book site's authenticated upload/publishing API; do not guess its endpoint.
4. Produce and verify the PDF/book artifact, bibliography and licenses before publishing.
5. Confirm the book's public page and download before calling the existing Moltbook post/verification flow.
6. Persist book identifiers and announcement identifiers, reconcile uncertain writes, and prevent duplicate publications across restarts.

Validation uses mocked provider/process events. A successful test does not prove installed runtime, live research, publishing or Moltbook delivery.

Runtime verification: upstream binary reported 2.0.151; CLI help confirms the adapter flags. Connection, auth, zero-balance, idempotency and spending-gate tests use mocked responses. Live account flags must be checked after deployment.
