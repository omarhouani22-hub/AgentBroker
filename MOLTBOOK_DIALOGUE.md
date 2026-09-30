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

Local focused verification:
python -m unittest -q test_moltbook_dialogue test_moltbook test_app test_browser_session test_general_learning

All 29 focused tests passed with mocked network responses. The wider existing
suite has nine unrelated provider errors: its provider mocks do not intercept
the current default dual-model implementation. No live generation or
publication has yet been validated.

Official router documentation:
https://openrouter.ai/docs/guides/routing/routers/free-router
