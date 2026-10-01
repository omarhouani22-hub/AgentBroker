# AgentBroker trained dialogue experiment

The owner's **My trained model — experimental** conversation choice runs an actual
Qwen3-0.6B LoRA model on the same server as AgentBroker. The current free router
remains the default. Moltbook publication stays on the current free router: the
experimental candidate has not passed its promotion gate.

The expanded run continued from the real 24-step pilot, using 80 public handwritten
Arabic/English examples for 128 additional steps, with 20 held-out target answers.
Mean target-answer loss improved from 2.4793 to 1.9890, but three individual cases
regressed. Arabic generations remain awkward, and memory/security wording needs
improvement. A lower loss is not proof of conversational quality or intelligence.

No private owner conversations were included in weight training. Owner memory and
corrections still enter inference prompts, without automatically updating weights.
The current adapter was merged and quantized to Q3_K_M to fit a small CPU host.
Quantization can reduce quality further; this is explicitly an experiment. Q2_K was rejected after degenerate outputs; Q3_K_M can generate English prose but often fails Arabic language selection, so such responses are rejected and routed to the existing free model. The CPU runtime uses a bounded 1,024-token context with quantized KV cache and avoids silently truncating long user questions.

Inference binds only to 127.0.0.1. The existing owner authentication protects the
dialogue and model-status routes. Model RAM is released after each request.
Invalid, incomplete, busy or unavailable local responses fall back to the fixed
free OpenRouter endpoint. Reply provenance shows which model actually responded.
There is no paid API fallback, new hosting subscription or externally exposed
model-server port. Free hosting may sleep and CPU replies can be slow.

`trained_model_manifest.json` identifies the public, synthetic-only weights,
SHA-256 checksum and pinned official llama.cpp runtime. `build_trained_runtime.py`
builds the CPU binary and verifies the downloaded artifact. The base model is
Apache-2.0; see Qwen/Qwen3-0.6B's upstream model card and license.

Focused mocked routing checks verify opt-in, public separation, fallback and
context preservation. Live inference is a separate deployment check; mocked tests
do not establish live model availability or quality.
