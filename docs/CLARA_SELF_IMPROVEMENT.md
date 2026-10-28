# Clara daily improvement

The existing `skills/clara-self-improvement/SKILL.md` now governs a bounded
engineering diagnostic in `.github/workflows/agent-learning.yml`. The existing
three-hour heartbeat runs this job in its midnight UTC window, or on manual
dispatch. It reads and fingerprints the skill, runs voice regressions, measures
a synthetic scheduling benchmark, and saves a report for 14 days. The private
retrieval evolution and encrypted checkpoint job continue separately. No model,
paid API, private conversation, new service, or generated code is used here.
A failed diagnostic fails the job; it never promotes code or deploys itself.
Changes still follow branch, regression tests, PR, merge to main, and the existing
Render auto-deploy. Keep the skill file private-data-free in this public repo.

## First improvement: time to first speech segment

Previously the natural-voice client awaited generation of every segment before
playing any audio. It now plays the first segment immediately, then generates the
remaining segments sequentially during playback. It waits safely if playback
catches synthesis, and preserves cancellation, timeout, replay cache, mobile
manual Play, the existing character limits, transport, and provider selection.
English prompts, authentication, quotas and free-only routing are unchanged.
The change adds no speech requests and enables no paid configuration.

Baseline and acceptance use the same English three-segment fixture with simulated
synthesis times of 120, 180, and 240 ms. Baseline first playback is 540 ms; the
candidate must start at 120 ms while total synthesis remains 540 ms (420 ms / 77.8%
less scheduling delay). The original one-segment behavior remains unchanged.
The regression gate also covers out-of-order readiness versus playback, premature
completion, cached replay, cancellation, stale responses, mid-generation errors,
request privacy headers and the five-segment cap.

Run `node scripts/clara_voice_latency.cjs --report /tmp/clara-report.json`.
This uses a virtual clock and mocked speech/audio, and does not establish actual
model response time, Piper speed, audible output or device microphone performance.
Live verification must first confirm the deployed revision and asset checksum.
Running the benchmark on that exact downloaded asset verifies deployed scheduling;
it must still be described as synthetic, not a measured live voice conversation.
Authenticated real-device end-to-end audio is a separate verification.

Rollback is a revert of the PR through the existing main/Render workflow. The
next improvement should measure real authenticated send-to-first-audible-speech
on the owner's device before choosing another latency change.
