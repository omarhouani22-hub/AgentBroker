# Free-form Moltbook dialogue

AgentBroker can start discussions, comment on others' posts, continue replies,
and reuse tentative lessons from attributed community discussions.

## Configuration

Set OPENROUTER_API_KEY as a secret on the existing Render service.
If LLM_BASE_URL is exactly https://openrouter.ai/api/v1, its existing LLM_API_KEY
can be used instead. Never commit a key or paste it into a public post.
Keep the existing MOLTBOOK_API_KEY and owner claim.

The dialogue engine is pinned to openrouter/free. It does not use the main
model provider, DeepSeek, dual_model_call, paid fallback models, or paid search.
No purchase or subscription is needed for the free-model route. Provider
availability, free quotas, GitHub Actions and free hosting limits still apply.
On quota errors the cycle waits rather than switching to a paid model.

## Behavior

The existing authenticated GitHub heartbeat runs every three hours. It restores
and preserves moltbook-checkpoint.txt as an encrypted artifact alongside the
existing learning checkpoints. Each cycle may publish one generated comment or
post, or skip if no useful contribution is identified. New discussion posts
have a 24-hour minimum interval. The free model receives public thread excerpts,
previous public actions and tentative lessons; no private owner files or
credentials are supplied. A free model may decode a verification challenge;
the arithmetic is then computed locally.

Replies are prioritized, with periodic space for original discussions.
Learning means storing attributed hypotheses and test suggestions and using
them in later conversations. It does not train model weights, prove an
improvement, or automatically modify production code.

Writes are reserved durably before transmission. Ambiguous outcomes and failed
verification pause automatic writes for operator review, avoiding duplicate
posts. Keep the encrypted checkpoint when redeploying an ephemeral instance.

## Verification

GET /health includes moltbook_free_dialogue_v1.
Authenticated GET /moltbook/dialogue/status reports configuration, recent
actions and lesson count. Trigger the existing agent-learning.yml workflow
manually after deployment and check the preserved encrypted artifact.
Actual publication is confirmed only by status=published and the remote
post/comment ID, then checking visibility on Moltbook.

## Automatic measured memory improvement

Once per UTC day, after public lessons exist, the free model proposes a bounded
retrieval policy. Allowed changes are query relevance weighting, duplicate
removal and per-source limits. Only aggregate gaps from a fixed synthetic
holdout are supplied to the proposer. A candidate is adopted only if mean
retrieval coverage improves and no holdout case regresses. Invalid proposals,
quota errors and failures retain the accepted policy. Attempts are reserved
before generation and are not repeated automatically that day.

The accepted policy actually chooses the tentative lessons supplied to later
Moltbook conversations. An experiment history and prior policy are retained in
the encrypted checkpoint. The holdout result measures only synthetic retrieval
coverage; it does not establish real conversational improvement, factual truth,
general intelligence, or model-weight training. A repeatedly used holdout can
be overfit. Production code and tool permissions cannot be changed by lessons.

## Owner conversation

The private dashboard has a conversation panel. AgentBroker can initiate one
new friendly topic per UTC day and reply to the owner. The scheduled heartbeat
creates topics without needing a browser to stay open; they appear on the next
visit. A signed-in page also checks for a new daily topic. Polling only reads
messages. Owner conversation is stored separately inside the encrypted
checkpoint and never included in public Moltbook prompts or posts.

The companion is an AI assistant, not a human friend. The free provider sees
the messages sent for generation; do not supply credentials or sensitive data.
There are at most twelve owner reply attempts per UTC day to leave room in the
free quota for public participation. No paid fallback is permitted.

Public posts never show S1/S2/S3-style citation labels. Private task answers
hide those labels and source lists by default, keeping evidence in persisted
records. Explicit requests for sources (Arabic or English), or
include_sources=true, show sources when available. No references are invented.

Telegram and WhatsApp are deferred; neither integration is configured.

Local focused verification:
python -m unittest -q test_moltbook_dialogue test_moltbook test_app test_browser_session test_general_learning

The focused tests use mocked network responses. The wider existing
suite has nine unrelated provider errors: its provider mocks do not intercept
the current default dual-model implementation. No live generation or
publication has yet been validated.

Official router documentation:
https://openrouter.ai/docs/guides/routing/routers/free-router

### Bilingual browser voice (1.8.2)
Private conversation now supports persisted auto/Arabic/English preferences. Explicit English applies to replies and daily initiated topics. Browser speech synthesis reads replies on demand; optional read-aloud starts only after an interaction, never on background polling. Microphone recognition is user-started, uses the selected language (Arabic in auto mode), and fills a reviewable transcript without sending it automatically. Availability and voices depend on the browser/device; browser speech services may process audio. Keyboard dictation remains a fallback. No paid speech API is introduced. 47 focused mocked tests and extracted JavaScript syntax checks pass; actual microphone permission, recognition accuracy and device voices require a user-device check.

### Private recall and requested topics (1.8.4)
Start a topic explicitly requests a new opening even after the automatic daily attempt failed or ran. Requested topics share the existing 12/day free conversation quota; automatic initiation remains once daily. Private conversation retains a bounded 200-message archive independently of the 30-message display history. The model receives up to six lexically related older messages plus the latest sixteen. Recent corrections take precedence; this is contextual recall, not unlimited retention, semantic memory or model-weight training. The archive uses the existing private encrypted checkpoint and never enters public Moltbook prompts. 49 focused mocked tests pass, including recall after display-history rollover and topic retry/quota behavior.
