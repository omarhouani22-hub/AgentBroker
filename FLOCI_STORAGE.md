# Optional Floci file and knowledge storage

AgentBroker stays on Render. Floci runs separately on an always-on host with a persistent disk. This integration is disabled until FLOCI_ENDPOINT_URL is configured. It does not provision a host, make the agent autonomous, or train a model.

Start a local development instance: `docker compose -f compose.floci.yml up -d`. The named volume survives container recreation. Back it up off-host; never use `docker compose down -v` with live data. Pin a reviewed image digest before operating a permanent instance.

Create the bucket from the Floci host using the AWS CLI with dummy credentials:

```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 aws --endpoint-url http://127.0.0.1:4566 s3 mb s3://agentbroker-private
```

Set AgentBroker server environment:

- FLOCI_ENDPOINT_URL: the private endpoint reachable from Render, not localhost on your laptop.
- FLOCI_BUCKET: agentbroker-private
- FLOCI_REGION: us-east-1

Floci accepts dummy credentials; never expose its port directly to the public Internet. Use a private network or an authenticated tunnel/proxy. The sample Compose binds loopback only; remote connectivity must be explicitly arranged. No real AWS credentials are needed. Do not configure a public unauthenticated endpoint.

Every object is encrypted by AgentBroker using its existing checkpoint cipher. Keep AGENT_ACCESS_TOKEN stable and backed up securely: rotating it without decrypting and re-encrypting objects makes existing objects unreadable. No keys are stored in this repository.

## Private API

Existing bearer authentication or browser-session plus X-AgentBroker-Request: 1 applies to these routes:

- GET /storage/status: configured and reachable flags.
- POST /storage/files: multipart field `file`, maximum 1 MB; returns a random file ID.
- GET /storage/files: list IDs, capped at 500.
- GET /storage/files/{id}: encrypted-at-rest file download, delivered as an attachment.
- POST /storage/sync: restore validated remote notes to the local SQLite retrieval index without replacing existing IDs, then upload all local notes. Run once after initial configuration and after a fresh deployment. Partial remote writes can be retried.

New generated knowledge notes are mirrored after their local commit. Storage failures retain the local note and emit a warning; /storage/sync retries them. Imported notes are mirrored by explicit sync. Existing retrieval continues to use SQLite. Stored files are inert bytes: their content is not automatically parsed or added to model context. To use information in research, import sourced knowledge notes and sync them.

Storage is not active until the bucket exists, private connectivity is configured, and a live upload/download plus restart-and-restore check succeeds. This is an optional development-emulator integration, not a claim of managed production durability.

Validation: `python -m pip install -r requirements-dev.txt` then `python -m unittest test_floci_storage test_memory test_browser_session`. Storage tests use Moto S3 emulation; they do not establish compatibility with a live Floci instance.
