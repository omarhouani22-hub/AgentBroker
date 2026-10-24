# Model providers

AgentBroker 1.5 separates model calls from its knowledge, document retrieval policy,
and learning history. Research, private-document answers, and autonomous learning
all use the same server-configured adapter. Changing a provider does not train a
model or establish that answers improved.

## Existing DeepSeek connection

No configuration change is needed. The default is `LLM_PROVIDER=deepseek` using
`DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` (legacy default: `deepseek-chat`).
The endpoint stays fixed at `https://api.deepseek.com/chat/completions`.

## Another compatible provider

Set these variables in Render's Environment settings, then deploy:

| Variable | Value |
| --- | --- |
| `LLM_PROVIDER` | `openai-compatible` |
| `LLM_BASE_URL` | Provider's HTTPS API base URL, including `/v1` if required, without `/chat/completions` |
| `LLM_MODEL` | Exact model identifier supplied by the provider |
| `LLM_API_KEY` | That provider's API key, stored only as a server secret |
| `LLM_TOKEN_PARAMETER` | `max_tokens` (default), or `max_completion_tokens` if required |

Only non-streaming Chat Completions with system/user messages, a text
`choices[0].message.content`, and `finish_reason=stop` are supported. This is not
an adapter for every vendor's native API. Models must also reliably return the
bounded JSON used by the learning planner. Unsupported, empty, or truncated
responses fail without replacing the accepted retrieval policy.

There is one request per model call, capped at 1,800 output tokens and a 60-second
response timeout. Redirects and automatic fallback to another provider are disabled.
A custom endpoint never receives the legacy DeepSeek key. No provider configuration
or credentials are accepted from visitors, documents, model output, or checkpoints.

## Self-hosted model

A compatible server such as Ollama can use `LLM_BASE_URL=http://127.0.0.1:11434/v1`
when it actually runs on the same machine as AgentBroker. A local model must already
be installed and have sufficient hardware. On Render, localhost means the Render
instance, not your laptop. Remote servers require HTTPS and a nonempty API key;
protect a remote Ollama server with an authenticated gateway. No model or hosting
plan is purchased or provisioned by this change.

## Verify and roll back

1. Before a deployment, ensure the knowledge backup and learning checkpoint exist.
2. After deploying, run a short research question and a private-document citation
   check through Command Center. Check the learning journal and next scheduled run.
3. Compare candidate answers on representative held-out questions before deciding
   a model is better. Existing synthetic retrieval checks do not evaluate models.
4. To roll back, set `LLM_PROVIDER=deepseek` with the existing DeepSeek key/model.

Provider changes do not change the database schema, accepted policy, document
storage, or encrypted checkpoint format. Render's ephemeral database can still reset
on deployment: Command Center restores its saved learning state, and GitHub's daily
clock restores encrypted checkpoints. Restore shared knowledge from the existing
Command Center backup after a reset. Keep `AGENT_ACCESS_TOKEN` unchanged because it
also protects existing encrypted checkpoints.

The daily clock checks `autonomous_clock_v1` capability instead of a particular
release number, so later compatible releases continue the existing schedule.

References: [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
and [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility).

## OmniRoute: free-only opt-in (AgentBroker / Clara / Hermes)

OmniRoute exposes OpenAI-compatible `/v1/chat/completions`. Host it separately behind authenticated HTTPS and configure the existing Render service **only after the gateway is running**. No gateway, credentials, or model usage is provisioned by this change.

| Variable | Value |
| --- | --- |
| `LLM_PROVIDER` | `omniroute` |
| `LLM_BASE_URL` | `https://YOUR-PRIVATE-OMNIROUTE-HOST/v1` |
| `LLM_MODEL` | An explicit confirmed-free OpenCode route, `oc/<model-id>` (never `auto`, `auto/cheap`, or paid routes) |
| `LLM_API_KEY` | Private gateway token |
| `DUAL_MODEL_MODE` | `false` (also enforced for OmniRoute in `model_call`) |

The `oc/` restriction prevents automatic selection of other provider families; **it does not independently verify pricing or quota changes**. Check the selected route's terms and gateway policy before enabling. An exhausted free route must fail, not fall back to a paid route. `auto/cheap` optimizes price, not zero cost.

AgentBroker and Clara paths using the shared `model_call` and Hermes student sessions using `model_config` inherit the new provider. Separate DeepSeek teacher calls, `team_provider` direct calls, and any external speech/image services do **not** inherit this setting: keep those features disabled until individually audited. In particular, do not enable Hermes team experiments while `DEEPSEEK_API_KEY` is present without explicit spending authorization.

This change does not modify Render secrets, deploy a gateway, run models, or activate learning. Rollback: restore the previous `LLM_PROVIDER` and related settings. Test with an authenticated gateway and a verified free model before production use.
