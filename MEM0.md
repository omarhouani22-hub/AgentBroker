# Private conversation memory

Mem0 OSS recalls relevant owner facts before private companion replies and
extracts durable facts after successful replies. Public Moltbook generation,
research knowledge and private document excerpts do not receive this memory.
SQLite remains the transcript store. Existing transcripts are not bulk uploaded.
Mem0 failure leaves chat available and reports `mem0_saved: false`.

## Enable on Render

Install `requirements-memory.txt` in the build command, in addition to the
existing build steps. Set `MEM0_ENABLED=true`, a stable `MEM0_OWNER_ID`,
and `MEM0_CONFIG_JSON` containing an explicit `llm`, `embedder`, `vector_store`
and `history_db_path`. Example configuration (provider credentials belong in
Render secrets, never git):

```json
{
  "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini", "temperature": 0.1}},
  "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
  "vector_store": {"provider": "qdrant", "config": {"url": "https://YOUR-QDRANT-HOST", "api_key": "YOUR-QDRANT-KEY", "collection_name": "agentbroker_private"}},
  "history_db_path": "/var/data/mem0-history.db"
}
```

This example also requires `OPENAI_API_KEY`, a persistent disk mounted at
`/var/data` and a persistent Qdrant instance. The repository's free Render plan
does not configure a persistent disk. Do not use ephemeral local Qdrant for
production. OSS has no Mem0 platform fee, but selected model, embedding and
hosting services may charge. Keep disabled until those resources are configured
and their costs accepted. Other providers can be explicitly configured.

Check authenticated `GET /memory/status`. Then send a non-sensitive test fact
through `/companion/messages` and check `mem0_saved: true`; ask about it in a
later conversation. Unit tests use a mocked SDK; this is not a live service test.
Disable with `MEM0_ENABLED=false`. No existing memory is deleted.
