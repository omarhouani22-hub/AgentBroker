# Hermes learning pilot

This integrates the **real Nous Research Hermes AIAgent**, pinned to commit
`f80d888e2f6b3268c72c5ac32a55a63432751c0d`. It does not implement a lookalike.
The existing research, document, and daily retrieval routes remain available.

## Run

Build with `bash scripts/build_hermes.sh` using Python 3.12. Hermes installs into
its own environment so its dependency pins do not conflict with Flask's.
Use `gunicorn --workers 1 --threads 2 --timeout 120 app:app`. The second thread
keeps health checks responsive while a bounded Hermes session waits for the model. An existing Render service must use
the new build command; editing render.yaml alone may require Blueprint sync.
`GET /health` reports the version and whether the runtime executable exists.

No new model key is needed: Hermes uses AgentBroker's server-side provider
configuration. The selected endpoint must support OpenAI-compatible tool calls
and at least a 64,000-token context. Hermes uses a conservative 64K context pin.
Provider usage can cost money even though Hermes is MIT licensed.

The existing Command Center can proxy these routes using its saved encrypted
connection; the token is never returned to the browser. It keeps an encrypted
checkpoint in private R2 storage after each experiment stage and restores it
when a fresh AgentBroker instance has no Hermes state.

## What learns

1. A fresh Hermes process answers four synthetic workforce-capacity cases.
2. A separate process sees failure categories and **different worked training
   examples**, then writes a general SKILL.md with the real `skill_manage` tool.
3. Another fresh process repeats the original four cases with the candidate.
4. The server, not the model, checks calculations, unit conversion, ceiling
   rounding, and missing-data handling. A changed skill is adopted only when
   more cases pass and no previously passed case fails.

A 4/4 baseline cannot improve on this suite. In that case the candidate is not
adopted. Timing and token counts are descriptive, not acceptance criteria.
One repeated four-case suite is not a statistical benchmark, generalization
proof, a promise of growing intelligence, or weight training. No files or books
are silently imported, and no claim of live improvement follows from tests.

Authenticated API routes:

- `GET /hermes/status`: latest experiment and accepted skill names.
- `POST /hermes/experiments`: create a bounded experiment.
- `POST /hermes/experiments/{id}/step`: advance exactly one stage.
- `POST /hermes/tasks` with `{"goal":"..."}`: use accepted skills in a new session.
- `GET /hermes/export`: encrypted backup; requires the same access token to restore.
- `POST /hermes/import`: restore that backup into an empty Hermes store only.

The first pilot exposes only skill listing/reading and, during learning, skill
editing. No terminal, browser, email, subagent, purchasing, or publishing tools
are exposed. A temporary profile is reconstructed per process, carrying only
bounded skill documents. No scripts are promoted or executed. It is not an OS
sandbox for hostile upstream Python code; the trusted pinned runtime still
executes as the service user. Each stage has five tool-loop iterations, a
75-second agent budget, and a 100-second subprocess timeout. Automatic provider
transport retries/recovery are disabled; do not restart an interrupted charged
stage automatically. Run Gunicorn with one worker as already configured.

The SQLite state alone is not durable on free Render. Use the Command Center
flow for automatic encrypted backup/recovery. Direct API/dashboard callers
must export state before redeploying. Runtime logs and private task text are
temporary; the experiment stores synthetic answers and metrics only.

## Verification

`python -m unittest -v` runs application contract tests. The optional starter
knowledge pack test skips when that pre-existing absent file is unavailable.

```
HERMES_INTEGRATION_TEST=1 HERMES_PYTHON=/absolute/runtime/bin/python \
  python -m unittest -v test_hermes_runtime
```

This second test runs the real pinned Hermes runtime against a **scripted local
model endpoint**, verifies an actual skill write, and reads it from a new
process. It validates integration/persistence and restricted tool availability,
not real model competence, provider credit, or measured learning gains.

## Evaluation revision 2
Content accuracy is separate from strict JSON format compliance. A single fenced
JSON block can be scored even with surrounding explanation; duplicate JSON keys
and multiple fenced blocks are rejected. Raw responses and recorded scores remain
available. Earlier four-case results are re-scored for display without changing
the original promotion decision. New experiments pin eight cases, including seconds,
monthly volume, unavailable capacity, fixed annual work, and boundary rounding.
Training examples are different from evaluation inputs. The before/after cases are
repeated: this is a small diagnostic suite, not proof of generalization.
Task sessions are explicitly read-only; only learning sessions can save skills.
Promotion requires higher content accuracy, no case regression, and strict JSON
compliance after learning. Correcting formatting alone does not prove learning.
