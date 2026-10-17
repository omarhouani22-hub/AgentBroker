# Internal English voice mode

Set `CLARA_LOCAL_ONLY=true` on the existing server after the pinned model build and
voice smoke check pass. This selects local speech capture/recognition, local chat
and local output speech for the private companion. It does not change public
Moltbook, research or AgentBroker team-provider jobs.

The browser captures up to 28 seconds of microphone audio after an explicit user
gesture, resamples to mono 16 kHz PCM and sends it only to this origin. Vosk runs
in an ephemeral worker. SmolLM2 replies in English through a loopback-only llama
server. Piper produces English female speech. Each worker releases RAM before the
next stage. Authenticated routes and request guards also protect transcription.
Audio is not written to permanent storage; transcripts remain in private chat.

There is no daily private dialogue counter in this mode. Calls are serialized and
bounded by input size, context capacity and timeouts to keep the free web host
usable. This is not unlimited compute or guaranteed availability. Large complex
questions can exceed the small context or model's ability. This model is much
weaker than a hosted frontier model. Important answers require human review.

Local errors never trigger external model or voice inference. Hosted Mem0 recall
and writes are bypassed for these private conversations; local history/profile
storage remains. Camera analysis and model-assisted document editing are rejected
instead of silently sending attachments to an external provider. Original files
and saved conversations are preserved. The UI declares these limitations.

The previous fine-tuned Qwen candidate failed simple public fixtures; the original
Qwen alternative also failed recall and used too much RSS in our initial test.
The selected small SmolLM2 candidate passed basic identity, arithmetic, immediate
recall and conversational checks locally. Those checks are not certification of
general intelligence, long-term memory, HR expertise or legal correctness.

Sources / licenses:

- SmolLM2: https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct (Apache-2.0).
- Fixed quantization: https://huggingface.co/bartowski/SmolLM2-360M-Instruct-GGUF/tree/7be6f65f1db715fe5dc5a4634c0d459b4eed42ec .
- Vosk and small US English model: https://alphacephei.com/vosk/models (Apache-2.0).
- Piper and LJ Speech voice: see INTERNAL_MEDIA.md.

Model downloads are public build-time downloads, not inference requests. Exact
SHA-256 and revision pins are in `build_internal_voice.py`. The runtime never
downloads models. Build caches retain verified artifacts, not private user audio.

CI loads the real web app before the end-to-end synthetic speech test within a
512 MiB no-swap cgroup. Each deployed web process runs one fixed-public-fixture
check; `/health` reports its result. The check holds the dialogue lock, so a user
may briefly receive a busy response during the first startup. It makes no external
inference calls and does not read owner messages. It never promotes itself based
on a failed test or modifies production code.
