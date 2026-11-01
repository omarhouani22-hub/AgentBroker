# Clara audio-driven mouth repair — 1 November 2026

## Actual implementation and cause

Current main at 3a44a5d5d06f9544410328a50e0697dac1f6b955 renders a static 2×2 WebP atlas, not a 3D mesh, Live2D rig or generated video. Its late CSS overrides force the facial layer to blink even during speaking, so a Speaking label does not establish mouth movement. Browser device speech and natural HTMLAudio playback are separate paths.

This branch carries forward the already completed, previously unpublished avatar repair commit f7512fc06586da2b0cb962e2b59a3efce81a069a rather than rebuilding the character. That repair introduced a stable neutral atlas surface and independently clipped eye/mouth patches. Its first analyser used a binary RMS > .012 threshold and did not reliably recover measurement after a late AudioContext resume. Quiet speech could remain below that threshold. It also let playback initialization overwrite mute/volume preferences.

The PR against main includes that existing prerequisite commit plus this mouth-specific follow-up. The follow-up does not change any AgentVault/payment/sales/hosting file or provider-selection policy. Earlier prerequisite speech backend changes validate waveform responses only; they do not change backend selection, API keys, billing gates or quotas. No held PR is merged or modified.

## Playback and animation path

1. An owner tap on Send/Clara/Replay calls the existing voice unlock synchronously before awaiting a reply or audio download.
2. The current natural voice path posts to the existing /companion/speech endpoint, validates the returned audio and assigns a blob URL to #clara-natural-audio. Provider routing stays unchanged.
3. The existing HTMLAudio playing callback drives the avatar speaking state. A suspended/interrupted Web Audio context instead pauses and offers Play/Retry; a closed context enters the existing playback-error path. It does not claim successful audible playback from the label alone.
4. One MediaElementAudioSourceNode is bound to the reused element. A direct destination connection preserves sound. A parallel AnalyserNode → zero-gain destination branch supplies analysis without adding a second audible copy or changing playback gain. If only analysis fails, the direct sound connection remains available.
5. Time-domain RMS uses 512 samples, removes DC offset and updates at approximately 30 Hz. A .001 noise gate and slowly decaying recent-peak reference make quieter speech visible without amplifying playback. Exponential attack (40 ms) and release (90 ms) produce a bounded continuous mouth-open value.
6. Only the existing independent mouth patch opacity consumes --clara-mouth-open. The base character image, face geometry, eye patch and blink cadence remain unchanged. This is amplitude synchronization, not phoneme/viseme alignment.

Native speechSynthesis does not expose its generated waveform to Web Audio. It keeps the existing clearly approximate playback-event-gated fallback; no false claim of analyser/phoneme sync is made for that route. Reduced-motion preferences continue to suppress visual animation while allowing voice playback.

## Lifecycle and mobile considerations

Mute and zero media volume close the mouth immediately and are preserved across replay. Silence releases smoothly toward zero. Pause, ended, error, abort, emptied, buffering/stall, cancellation, hidden pages and context suspension clear visual activity; stale RAF callbacks cannot restart it. Context statechange/resume restarts measurement when playback is active. Context/source creation occurs only once per media element, avoiding Safari's duplicate-source exception.

The implementation supports AudioContext and webkitAudioContext, byte-domain sampling when float-domain sampling is unavailable, and resume implementations returning a promise or void. Existing tap-based element unlock, visible native controls, watchdogs and Play/Retry remain. These compatibility paths have automated tests; they are not evidence of successful physical iPhone Safari playback. A device silent switch, external/Bluetooth route or physical speaker volume cannot be verified from an AnalyserNode.

## Checks actually performed

- **10 JavaScript test files pass.** New envelope tests exercise quiet input below the old threshold, smoothed attack/release, silence/noise, mute, zero volume, pause/end/error/abort/empty/wait/stall closure, suspended/resumed contexts, stale RAF cancellation, one-source reuse, WebKit byte sampling and analysis-failure preservation of the direct sound connection. Natural-player tests additionally verify retained mute/volume, suspended-context Play/Retry and closed-context errors.
- The new regression fails against the prerequisite's old binary analyser (“Attack is smoothed, not binary”) and passes against this implementation.
- **103 Python tests pass**, matching the existing Clara chat/voice CI Python command. Existing avatar/voice/camera/mic regressions remain green; no real provider inference or payment was invoked.
- **Real headless Chromium 154** at 390×844 @2x decoded the existing prerecorded English Piper fixture. Context running, non-muted media, advancing playback and nonzero RMS were observed. The measured mouth value varied continuously during speech; 55 samples had more than 50 distinct rounded values in the recorded run.
- Closed/speaking/muted/ended/blink screenshots were captured and visually inspected. With only scene geometry and sway fixed by a test-only same-origin stylesheet, speaking changed only the mouth patch (device-pixel bounds 302,95–370,136), and muted/ended screenshots exactly matched neutral. Blink changes remained above the mouth (288,61–384,92). Production CSP was not relaxed.
- Browser tests also verified stop closure, preservation of .25 media volume on replay, a deliberately rejected initial play followed by successful Play/Retry, and an empty page-error list.
- JS syntax and git diff --check pass. The existing CI workflow now runs the new avatar/lip-sync regression files.

The media fixture is prerecorded, not a new synthesis benchmark. Physical speaker audibility, physical iPhone Safari, Bluetooth/silent-mode behavior, real microphone recognition and phoneme timing remain unverified. The broader repository's existing unrelated red suites were not rerun or represented as green; the earlier avatar report documents their baseline.

## Reproduce locally without production data

The isolated loopback preview uses a temporary SQLite database and synthetic chat/prerecorded speech. It never opens the owner's database or calls a provider. It is available for this development session at http://127.0.0.1:8775/clara/ with preview-only password preview-only-avatar.

```sh
python scripts/preview_clara.py --port 8775 --audio /path/to/approved-english-fixture.wav
python scripts/verify_clara_lipsync.py --url http://127.0.0.1:8775 --output /tmp/clara-lipsync
node --test tests/*.test.cjs
```

Playwright, Pillow and Chromium must already be available for the browser script. No paid service, hosting change, production data mutation, provider-routing change, merge or deployment is part of this work. Sales and all existing release gates remain unchanged.
