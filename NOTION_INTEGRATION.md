# Optional Notion knowledge export (pilot)

This branch adds a **manual, preview-first** export to the existing
[AgentBroker Knowledge](https://app.notion.com/p/770170b4c0434e2abf4a4bdd0fe8d744)
database. It does NOT deploy itself, migrate private records, turn on background
sync, enable paid services, or retrain models.

## Configuration (server only)
- `NOTION_API_KEY`: a Notion integration secret, stored privately on Render.
- `NOTION_KNOWLEDGE_DATABASE_ID`: the **database ID** of the pre-existing
  AgentBroker Knowledge database, not a page or a data source ID.
- Share that database with the Notion integration. Do not put credentials in GitHub,
  a prompt, or frontend JavaScript.

## Authenticated endpoints
- `GET /knowledge/notion/status`: shows configured true/false, never secrets.
- `POST /knowledge/notion/sync` with `{"note_id":"KNOWN_ID"}`: returns a
  preview of precisely what would leave the local AgentBroker database.
- After human review, explicitly send
  `{"note_id":"KNOWN_ID","publish":true,"reviewed_public":true}` to export
  that one note. The result includes a Notion URL.
- Notes are **not** sent during ordinary research, chat or scheduled learning.
- Limit: max 1,800 characters, HTTPS evidence link, at least one source,
  and a valid topic. No automatic truncation of note content.
- The pilot records successful exported IDs locally to avoid routine duplicates.
  Ambiguous failures (e.g. network timeout after server creation) require manual
  verification in Notion before retrying.
- Never export private customer/employee information, internal HR records,
  secrets, copyrighted book contents or unreviewed text.

The integration uses only Python standard library calls to Notion's API.
Its schema currently maps `Topic`, `Summary`, `Source URL`,
`Source Type`, `Category`, `Status`, and `Tags`.
Validate the live API/database permissions before enabling export.

Offline tests: `python -m unittest -v test_notion_bridge`.
This pilot is one-way export, **not** cross-session semantic retrieval.

## Reverse direction (Notion to AgentBroker)
- `GET /knowledge/notion/pull`: retrieves a read-only preview of up to 20
  complete pages with status `Done` and an HTTPS evidence URL. It never imports
  by itself.
- `POST /knowledge/notion/import` with
  `{"page_ids":["<id from preview>"],"reviewed_public":true}`: explicitly
  imports selected pages to the existing SQLite knowledge table, using stable
  `notion-<page_id>` identifiers and `INSERT OR IGNORE` to prevent normal
  duplicate imports. Only the first 50 Notion records can be selected in this
  initial bounded pilot. Do not use this for private customer information.
- Import makes the notes eligible for existing lexical retrieval; relevance
  ranking is still keyword-based, not embeddings. Notion is **not** queried
  automatically for every conversation.
- There is no full bidirectional reconciliation or guarantee against duplicate
  exports after a server-local database reset. Verify Notion manually after an
  uncertain network failure.

## Rollout gate
Run offline tests and a live read-only Notion preview before merging. Check
Render credentials and integration permissions in the owner's selected Render
workspace. Do not run a production deployment without checking branch/workspace.
