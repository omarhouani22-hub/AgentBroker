# Internal speech and avatar presentation

AgentBroker now provides private English text-to-speech using a fixed Piper CPU
worker. `/companion/speech` returns WAV audio. The worker receives text over stdin,
does not use a shell or inference API, and exits after every utterance to release
RAM. Audio is temporary, bounded and returned with no-store headers. Model files
are checksum verified during deployment, never downloaded during a conversation.
The existing authenticated session and request guards protect the service.

English female voice: `en_US-kristin-medium`, replacing the older LJ Speech voice,
pinned to the upstream revision and
SHA-256 hashes in `build_local_speech.py`. Piper 1.8.0 is GPL-3.0-or-later:
https://github.com/OHF-Voice/piper1-gpl . Voice repository metadata is MIT, and its
individual model card identifies the Kristin LibriVox dataset as public domain:
https://huggingface.co/rhasspy/piper-voices/tree/bae641dcb5a608cff81ccaf7ff018baaca1a33e1/en/en_US/kristin/medium .
Speech uses a 0.95 length scale for a slightly quicker conversational pace. The
upstream model is labelled US English female; a specific California/New York
accent or perceived age is not certified and requires listening on the device.
Dependencies retain their respective licenses. No proprietary voice is cloned.

The build also saves ONNX Runtime's extended CPU graph optimizations, without
hardware-specific layout rewrites. Each ephemeral speech worker can load this
prepared graph with optimizations disabled, reducing repeated startup work. The
build validates its checksum, and its source revision, runtime version, CPU
architecture and size are checked before selection. An unavailable, stale or
unloadable cache uses the original pinned local model. No inference-time download,
external fallback, persistent speech worker or private-audio cache is added.
Reference: https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html

Internal speech takes priority when installed. A local failure never switches to
a billed speech provider. The legacy optional billed route remains gated behind
its explicit approval/key/cap settings if local files are absent. No such approval
is introduced by this change. Browser device speech remains an optional fallback.
Long replies are split into bounded internal requests. Internal speech is currently
English only; Arabic conversations can continue using the existing device option.
Microphone recognition still uses the existing browser/native adapter; this change
does not claim internal speech recognition or an entirely offline assistant.

Actual public greeting and long-text synthesis were verified locally. CI also
tests actual synthesis under a 512 MiB no-swap cgroup. These are waveform and
resource checks, not perceptual quality certification. Real host headroom and
mobile autoplay restrictions can still affect playback.

Avatar rendering preserves approved artwork. The full-body renderer avoids an
unnecessary filter rasterization and caps enlargement at the 627px source-cell
resolution; initial poses are preloaded. No new Full HD detail, natural walking,
image-generation engine or live video has been invented. Runtime presentation
code is in the public repository; it requires no external avatar API.

AgentBroker's rendered interface, instructions, status strings and built-in
fictional HR example are English. Language support, existing conversations,
documents and retrieval behavior remain unchanged.
