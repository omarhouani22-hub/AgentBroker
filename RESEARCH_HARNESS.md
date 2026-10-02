# Checkpointed research harness

POST /runs now checkpoints memory retrieval, search, synthesis, verification and storage in the existing private SQLite database. Completed runs are idempotent when resumed. POST /runs/<id>/resume explicitly resumes failed or interrupted runs; GET /runs/<id> shows saved events. Control Center has a resume field. Authentication and source-display preferences remain in force.

A durable SQLite lease prevents concurrent execution of the same run across workers. Expired leases allow recovery after a crashed process, after four minutes. Reserve provider attempts before sending requests, retaining the budget after a timeout. Research uses the configured single provider transport with no hidden team retries or fallback. Maximum per task: two search attempts and two model requests, including one optional citation-format repair. Failed transport calls require an explicit resume. This is an attempt bound, not a dollar spending cap.

Verification checks nonempty output, current-source citation presence, valid source/memory reference indices and the stored note matching the final draft. It does not prove source reliability or claim-level factual accuracy. The result explicitly requires human review. Failed verification does not save a knowledge note. Sources, memory provenance, stage events and errors remain private.

Scope is research drafts only. Existing private dialogue, scheduled learning and Moltbook workflows are unchanged. No browser automation, publishing, universal task runner, continuous background worker or model-weight training is added. Checkpoints use the existing database; on ephemeral Render storage they do not survive every deployment. Export knowledge before deploying and use persistent storage for durable task recovery.

Validation: 103 available tests pass, one optional seed-pack test skipped. Rendered browser JavaScript parses. Providers were mocked; live credentials and research still require a signed-in production check.
