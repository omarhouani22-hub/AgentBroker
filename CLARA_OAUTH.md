# Clara OAuth preparation — not activated

This branch prepares Clara for a same-container `openai-oauth@2.0.0` proxy.
It does not install/start the proxy, change Render settings, or authenticate.
The current free OpenRouter connection remains the default and fallback.

## Inspected deployment (28 October 2026)

The existing `agentbroker` Render service runs Python in Oregon on Free,
deploying `main`, with one Gunicorn worker and two threads. Build command:
`bash build_agentbroker.sh`. Start command:
`gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 2 --timeout 120 app:app`.
The latest deployment reported live at commit
`6059dbd7ef7745d9d7ca79b086437799af94016a`. A live deployment status is not an
inference test or a guarantee of provider availability.

## Feasibility and blockers

- The proxy requires Node >=20. It could run as a supervised sibling process
  in the same service, binding only `127.0.0.1:10531`. Do not bind it to
  `0.0.0.0`, expose its port, add a public reverse-proxy route, or make a separate
  unauthenticated web service. Upstream does not require an API key on this port.
- The current Python build does not install the proxy or supervise Node. Runtime
  compatibility and memory use alongside existing local models are unverified.
- Version 2.0.0 CLI login uses `http://localhost:1455/auth/callback`. Opening that
  flow on an iPhone points at the phone, not Render. The hosted browser method
  requires its Chrome/Firefox extension; Safari is explicitly unsupported.
  There is no verified iPhone-only sign-in path for this version. Do not expose
  Render's callback publicly or change the redirect URL on a guess.
- Render Free has no persistent disk or shell/SSH access and loses writable
  filesystem state on restart, redeployment, and idle spin-down. A writable
  `auth.json` alone will not retain login. A static Render secret file can
  bootstrap a copy but cannot reliably retain rotating refresh credentials.
- Durable operation needs a private store for the latest refreshed session,
  with encryption, restricted access, atomic updates and refresh serialization.
  No such store was verified or provisioned. Free Render Postgres expires after
  30 days; Free Key Value loses data on restart. Neither is a durable solution.

Sources: [versioned package](https://github.com/EvanZhouDev/openai-oauth/blob/v2.0.0/packages/openai-oauth/package.json),
[upstream documentation](https://github.com/EvanZhouDev/openai-oauth#readme),
[Render Free limits](https://render.com/docs/free).

## Secure sign-in available on your own computer

On a trusted desktop/laptop with Node >=20, run in a terminal (not CI, Render
build logs, or a recorded/shared terminal):

```sh
npx --yes openai-oauth@2.0.0 login
```

Complete sign-in directly on OpenAI's authentication page in that computer's
browser. The localhost callback stays on the same computer. This authenticates
that local machine only; it does not connect Render. Credentials are written to
your local Codex auth file and must remain private. Do not paste passwords,
callback URLs/codes, tokens, or `auth.json` into chat, issues, commits or logs.
Do not upload credentials to this public repository. Any future transfer must
use a private authenticated secret-storage channel after durable storage exists.

## Implemented boundary

- Disabled unless `CLARA_OAUTH_ENABLED=true` and a safe explicit
  `CLARA_OAUTH_MODEL` is configured server-side. Select a model actually returned
  by the authenticated local `/v1/models`; examples in upstream docs are not
  evidence your account can use them.
- Only the authenticated message handler sets `_owner_request`; public-agent
  work and unsolicited companion openings do not use the ChatGPT session.
- Preserves existing local-model precedence if the local runtime is enabled.
- Sends the current Clara messages to a hard-coded loopback endpoint, without
  OpenRouter credentials, environment HTTP proxies, redirects, or routing fields.
- One proxy transport attempt with an 8-second socket timeout, bounded response
  size and the existing reply deadline. This is a socket timeout, not a strict
  end-to-end latency guarantee. No OAuth credentials or error bodies are logged.
- Existing Clara JSON, language, privacy and legal-output checks apply. Failed
  proxy transport or validation falls back to the existing `openrouter/free`
  path, including its existing limits and bounded retry policy. No paid fallback.
- A successful OAuth reply records `openai_oauth/<returned-model>` in Clara's
  existing message model field. That value is provider-reported, not inferred
  from the assistant's text. Fallback retains the existing `free_router` label.
- `.gitignore` excludes typical OAuth credential files and runtime directories.
  This is a guardrail, not a secret scanner or protection against force-add.

## Activation and verification still required

Before activation: restore execution-environment network access; verify the exact
npm artifact and dependencies; install a locked Node runtime/package; add process
supervision without changing the public binding; provide private durable refreshed
session storage; complete owner sign-in; and confirm Render billing/spend limits
permit a deployment without overage charges. Back up private Clara data before
redeploying because the existing SQLite archive is also on potentially ephemeral
storage. Do not create paid services or upgrade the plan.

Then test from the authenticated Clara UI with a harmless message and record
the assistant message's model and wall-clock request duration. Test proxy-down
fallback and restart/redeploy recovery. Verify the proxy cannot be reached
publicly. Until those tests pass, the integration is unverified.

Local check: `python -m unittest test_clara_oauth -v`. These are offline boundary
tests with mocked transport and production routing isolated through AST; they
do not exercise the whole Flask application, a real proxy, browser login or
OpenAI inference. No live-model latency is available from these tests.
