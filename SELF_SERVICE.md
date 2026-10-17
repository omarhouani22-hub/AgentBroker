# Local service workshop

AgentBroker's workshop builds its pinned CPU inference engine and checks the
existing checksum-pinned experimental weights without any external inference API.
It tries a smaller context after a failed profile and stops after a passing one.
It runs on relevant pull requests, main changes, manually, and weekly on Monday.
Only the standard public Ubuntu Actions runner is used. No purchases, service
creation, secrets, cloud inference, generated-code execution, or deployment writes
are included. The job has a 15-minute limit and the experiment a 5-minute limit.

The engine and test driver run together within a 512 MiB cgroup with no swap.
Reports contain synthetic test outcomes and timings only, never owner documents
or conversations. Failed builds and killed experiments are visible as failed jobs;
they must not be interpreted as passing candidates if no JSON report is produced.

`candidate_ready` means three narrow English smoke checks passed, each in at most
15 seconds. It does not mean a production-ready assistant. Real Render headroom,
representative conversation quality, Clara's JSON contract, memory honesty and
privacy behavior still require validation before any production routing change.

This is a bounded engineering experiment loop, not an unrestricted self-coding
agent. It does not invent or execute source patches, buy compute, fix arbitrary
failures, or silently promote a candidate. Clara's existing provider is unchanged.

## Voice

The workshop also runs the device speech, optional-voice guard, and native iPhone
bridge regression suites. The no-fee speech path uses browser speech synthesis or
AVSpeechSynthesizer on iPhone; it does not train or synthesize a new cloud voice.
These mocked adapter tests cannot prove audibility or microphone permission on
the owner's physical phone. Enhanced voice availability depends on that device.
The paid neural voice feature remains disabled unless separately authorized.
