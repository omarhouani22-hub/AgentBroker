# Clara avatar repair — local review and development preview

Base: current main `3a44a5d5d06f9544410328a50e0697dac1f6b955`. The earlier local avatar/audio work from `/workspace/AgentBroker-avatar-audio` was exported, including untracked files, before continuing in `/workspace/AgentBroker-avatar-dev`. The original worktree remains untouched. No remote branch, held PR, production database, hosting configuration or sales setting was changed.

## Reproductions and repairs

| Finding | Reproduction | Result |
| --- | --- | --- |
| Random outfit/pose on initialization and ordinary conversation | Baseline reloads selected casual, business/seated, business/standing and summer. `advance()` also ran on ordinary messages. | Removed random selection and automatic switching. Three fresh reloads retained business/seated; valid saved preferences remain supported. |
| Closer/back movement ignored | Baseline Come closer leaves framing=wide. Both client apply and server acknowledgement force wide. | Explicit closer/wider framing now applies and persists, without claiming actual walking. Seated/standing switch only between existing approved still assets. |
| Random appearance causes HTTP 400 | Baseline Wear shorts returns 400: frontend ships/selects shorts, backend rejects it. This can break ordinary replies after random selection of shorts. | Backend allowlist now matches that existing asset; unknown/incompatible values still reject. Regression test covers it. |
| Unstable blink changes too much of face | Forced baseline blink screenshots change a 151×187 device-pixel region, including head/mouth areas. | Neutral base cell stays fixed. Only eye patch changes: 96×31 device pixels in repaired capture; all body pixels below 25% of the avatar are identical. No whole-face replacement per blink. |
| Recovered portrait experiment disables original controls | Local recovered implementation detects claraAvatar and disables outfit/pose, even though approved assets exist. | Restored existing five outfit/pose combinations. One neutral surface remains; no transparent face layer sits over another moving face. |
| Asset failure can create a blank preset | Browser request for a new outfit deliberately aborted. | Decode-before-switch retains the previous loaded view and displays a clear error. Loads have an 8-second deadline; failed presets can be retried. Total startup asset outage is not claimed solved. |
| Silent/invalid speech or stuck Speaking | Automated empty, silent, truncated, wrong-content-type, buffering, missing start/end, stale callback and cancellation cases; autoplay rejection injected in Chromium. | Server validates PCM waveform before returning success. Client validates media and follows real playing/pause/waiting/ended/error events, with request/start/progress watchdogs. Play/Retry recovers a blocked play without another synthesis request. Device speech uses start/end events and bounded watchdogs. |
| Animation continues through silence/paused audio | Real HTMLAudio playback of an existing English Piper fixture; microphone is synthetic in the browser test. | Same audio element is unlocked on tap. Web Audio RMS drives the small mouth overlay where available; pause/end/cancel clears it. Device speech/unsupported analysis use an explicitly approximate playback-gated animation. No phoneme timing or true lip sync is claimed. |
| Original iPhone full-image disappearance / physical silence | Not reproduced on a physical iPhone; full image disappearance was not reproduced in baseline desktop Chromium. | Frame-swapping/fade mechanisms were removed from the repaired surface, but device-specific resolution remains unverified. |

The state controller supports idle, listening, thinking, speaking and error, with defined transitions. Speaking cannot directly restart recognition: playback ends/pauses before the controller returns to idle/listening. Invalid transitions and stale audio callbacks cannot resurrect canceled speech. Blink cadence is deterministic but varied; hidden/reduced-motion pages stop blink/meter work. Subtle whole-cutout nod/sway moves the head with the existing image; it is not an anatomical head rig or full-body motion.

## Appearance/assets and English interface

Audited all 13 Clara/companion image files and their dimensions/bytes; asset inventory is included in the evidence archive. The business/casual/summer/shorts seated atlases, standing-business atlas, blonde portrait/body atlases, scene atlas, companion image and three icons were inspected/reused. The prior recovered 512px approved portrait is used for the login card. No original atlas pixels, identity, hairstyle or character design were regenerated or replaced.

Legacy sprite selectors no longer drive the call-view surface. The new isolated CSS uses a neutral cell plus clipped eye/mouth patches from the exact selected atlas. Only an explicit user preset change swaps its source. Framing scales from the top to retain the head and crop the lower body intentionally. Interface labels stay English, including the user label and error/preview text; existing multilingual user input parsing is retained.

## Lightweight animation options evaluated

| Option | Evidence / suitability | Decision |
| --- | --- | --- |
| Native CSS + Web Animations / Web Audio | Existing browser APIs; no new dependency. This repair actually uses CSS transforms/opacity and a 30Hz audio-energy meter with 256 samples, not a 3D loop. | Use now. The new avatar JS+CSS total 7,414 bytes uncompressed at review time. |
| Motion (motiondivision/motion) | Upstream repository metadata identifies MIT; JavaScript/React animation library suited to coordinated gesture timelines. https://github.com/motiondivision/motion | Free candidate for a later rig/timeline; not installed or benchmarked. No need for it for two facial patches. |
| Anime.js (juliangarnier/anime) | Upstream metadata identifies MIT; JavaScript animation engine suitable for SVG/transform timelines. https://github.com/juliangarnier/anime | Free candidate after rigged assets exist; not installed or benchmarked. |
| 3D conversion | Current assets contain no mesh, bones, depth, viseme set or consistent intermediate poses. Conversion requires reviewed new assets and mobile GPU/memory evidence. | Defer; no 3D conversion or paid service introduced. |

## Tests actually run

- **62 targeted Python tests passed**: avatar movement/validation, waveform recovery, privacy, English interface, chat/connection/response quality, existing tasks, provider and AgentVault/payment protections.
- **9 JavaScript test files passed**: deterministic appearance/state transitions, speech lifecycle/guards, natural speech validation/replay/autoplay recovery, camera, connection/chat recovery, internal mic and native bridge.
- Root Python discovery: **208 run, 2 failures, 2 errors, 2 skips**, identical failure identities to the pinned current-main baseline.
- tests/ discovery: **146 run, 21 failures, 5 skips**, identical failing test/subtest identities to current main's retired JD routes/navigation. No pre-existing red tests were weakened. The previous presentation-command test expected the old no-zoom limitation; it now checks the intentional closer view, persisted close framing and unchanged model-call quota. Error-state assertions were updated for the explicit new error state.
- Python compilation, JS syntax and git diff --check passed.

Targeted command:

```sh
python -m unittest tests.test_clara_avatar_commands tests.test_local_speech tests.test_clara_privacy tests.test_english_interface tests.test_clara_chat tests.test_clara_connection tests.test_clara_response_quality tests.test_clara_tasks test_provider test_agentvault test_agentvault_api test_agentvault_paypal
node --test tests/*.test.cjs
```

## Actual browser / mobile-emulation evidence

Real headless Chromium 154, 390×844 @2x, actual HTMLAudio playback and Web Audio analysis:

- Complete prerecorded reply plays with nonzero decoded audio energy and advancing audio time. Mouth mode is energy; microphone mock remains off while playing, then resumes in call mode. Non-call replay completes and returns to idle. A deliberately rejected first blob play recovers using the visible Play/Retry button. Browser page error list is empty.
- All five original supported outfit/pose combinations load as one surface. Missing outfit resource retains the last loaded image. Reduced-motion context has animationName=none and no blink timer.
- Before/after idle, blink, speaking, ended, closer and narrow-mobile screenshots were captured. Blink screenshots were visually inspected and pixel-compared with sway frozen by a test-only same-origin stylesheet; production CSP was not relaxed.
- 320×740 @2x, **4× CPU throttle**, during real audio playback/energy analysis: **119 measured frame intervals, median 16.7ms, p95 16.7ms**, no horizontal overflow. These are requestAnimationFrame scheduling measurements on desktop Chromium, not proof of physical-phone GPU/compositor performance. Separate idle-view JS heap observation was about 2.02 MB; this excludes textures, native audio and total browser memory.

Speech is an existing prerecorded Piper fixture and the chat/model and recognition input are synthetic. No new synthesis model download, actual provider generation benchmark, live microphone transcription, physical-speaker audibility or iPhone Safari playback was tested. A Speaking label alone was not used as evidence. Physical iPhone playback, Bluetooth/silent-mode behavior, Safari background/foreground transitions and phone battery/thermal performance remain unverified.

## Working local preview

A development server is running at http://127.0.0.1:8765/clara/ with the synthetic preview-only password `preview-only-avatar`. The comparison baseline is localhost:8766. These bind only to loopback, use temporary databases and visibly label synthetic chat/prerecorded speech; they are not a deployment or a connection to Omar's data. They last only as long as this development environment/process runs.

Reproduce using an existing local WAV:

```sh
python scripts/preview_clara.py --port 8765 --audio /path/to/approved-english-fixture.wav
# Second terminal, only for before/after comparison; --root points to the pinned baseline source snapshot:
python scripts/preview_clara.py --port 8766 --root /path/to/baseline-checkout --audio /path/to/approved-english-fixture.wav
# Browser test environment requires Playwright, Pillow and Chromium already installed:
python scripts/verify_clara_playback.py --output /tmp/clara-avatar-checks
```

The preview clears provider keys from its child environment and overrides only its local synthetic chat/speech handlers. It does not provision a service, contact paid APIs or use production database files. Local preview processes were restarted while developing; the hosted service was not restarted.

## Next incremental milestone

After actual iPhone acceptance, prepare a reviewed 2D head/torso/arm rig from the same approved character, with neutral + one nod + one hand gesture, explicit landmarks and motion bounds. Keep all body parts inside the existing frame; do not fabricate a walking sequence from two still poses. Require stable eye/mouth attachment through each gesture and no regression under the same mobile test.

Then produce one **10-second local promotional draft** from synthetic product text using browser Canvas/MediaRecorder and an existing approved English voice, recording a local WebM plus sidecar timing metadata. Validate duration, nonzero audio, no clipping/ghosts, return to neutral, source/voice rights, and owner review. Rendering a local file is separate from publishing: no social account, ad spend or external publication is connected or authorized. Nothing is represented as an actual customer testimonial, verified storage recovery or sale.

## Release hold

Do not merge or deploy this work. The real private database still needs a consistent private backup and verified isolated restore, durable hosting/storage persistence, CI disposition and control of main auto-deployment. PR #82/#83 remain on HOLD; their memory/receipt/inbox blockers are unaffected. Sales remain disabled and no business outcome is established here. No live production data was read or modified, no hosting setting changed, and no paid resource was added.
