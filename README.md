# AgentBroker — research and knowledge-memory prototype

## Pinned llama.cpp build cache

`trained_model_manifest.json` pins the reviewed Linux x86_64 CPU archive, its
SHA-256, and the exact llama.cpp revision. Builds verify the download, archive
contents, and `llama-server --version` before using it. An unavailable,
incompatible, or invalid cache falls back to compiling the pinned source.
The model checksum and experimental model-quality gate remain unchanged.

To disable the cache, set `AGENTBROKER_LLAMA_CACHE_URL` to an empty string.
An alternative cache can be selected with `AGENTBROKER_LLAMA_CACHE_URL`,
`AGENTBROKER_LLAMA_CACHE_SHA256`, and `AGENTBROKER_LLAMA_CACHE_REVISION`.
Only use a reviewed HTTPS release with an independently checked checksum.
The release archive is retained independently of temporary Actions artifacts.

## Job description audit pilot

The public `/services/job-description-audit` page describes one focused HR service.
The private dashboard can draft its report from an existing Arabic or English job
description. It is a draft for human review, not an automatic paid order or legal
compliance opinion. Remove personal information before submitting customer text.

Set `SALES_CONTACT_EMAIL` on the server to show a request-by-email button. Set
`JD_AUDIT_PAYMENT_URL` only to a real HTTPS checkout link for this exact service
after confirming the price, refund terms, and payment account. An invalid or
missing link is hidden. Payment confirmation and fulfillment are manual; do not
send a report based on a click or an unverified claim of payment. The private
draft endpoint is `POST /offers/jd-audit/draft` with the existing bearer token,
JSON `title` and `description`. No client input or draft is saved by this route.

Pilot metric: record qualified inquiries, paid orders, hours spent, and refunds.
If outreach gets no qualified inquiries, revise the offer before automating
checkout or adding more agent capabilities.

## Version 1.2: import and retrieval

Upload the application files including `memory.py` to the repository. Import
`knowledge-starter.json` with the browser's Import knowledge button and access token.
The two original Arabic notes summarize only pp. 1-4 of Acemoglu & Restrepo's 2018
working paper, read from the user's saved reference. They are not full books,
current evidence, training data for model weights, or automatic access to ChatGPT.
No private library files or credentials are included.

Each research request retrieves up to three matching notes from the newest 500,
using lexical overlap (Arabic/English keywords, not semantic retrieval). It sends
them to DeepSeek as untrusted background with [M1] references alongside current
Tavily results [S1]. Retrieved notes and provenance are recorded in the run.
The seed notes must be imported once; unrelated topics retrieve no notes.

Imports require authentication, validate the whole batch before writing, do not
overwrite existing notes, and skip content-identical imported duplicates. Maximum
import: 2 MB and 100 notes. Larger exports must be split before import. Export now
includes all notes, not only the last 100. Back up before deployment. New research
still lives in SQLite on Render: this update does NOT provide external persistence,
background operation, automatic syncing with ChatGPT, or a deletion workflow.
Do not delete your only copy. Never put private backups or source books in public GitHub.

Local verification: `python -m unittest -v`. Network responses are mocked;
deployment, keys, live model compliance and factual accuracy remain unverified.

This version searches the web through Tavily, gives a bounded source pack to DeepSeek, and saves a cited research note plus its source URLs in SQLite. It does not write or publish books yet. "Learning" means accumulating reusable notes and sources; it does not retrain or modify the model.

## Setup on the existing Render service

1. Replace app.py, requirements.txt and render.yaml in the existing GitHub repository with these files. Keep tests and this README too.
2. In Render > Environment set DEEPSEEK_API_KEY, TAVILY_API_KEY, and AGENT_ACCESS_TOKEN (a private random string of at least 32 characters). Never commit or paste any key into chat. Account logins are not API keys.
3. In Render > Settings set Start Command to `gunicorn --workers 1 --threads 1 --timeout 120 app:app`. Updating render.yaml alone may not update an existing manually configured service.
4. Deploy and verify GET /health reports 1.2-knowledge-retrieval. Open GET / in a browser; the page warns if any required variable is missing, but this does not prove provider credentials or credit work.
5. Enter AGENT_ACCESS_TOKEN and a research topic, then choose Research and save. For the first live check use: `Evidence-based uses and risks of AI in employee recruitment`. Do not include private employee data.
6. Success means the result contains inline citations such as [S1], displays source URLs, and appears in authenticated GET /knowledge. Download an authenticated backup from GET /knowledge/export.

The JSON API remains available: authenticated POST /runs performs research, GET /runs/ID retrieves a run, GET /knowledge lists saved research, and GET /knowledge/export downloads a JSON backup. The browser page deliberately has no account system or extra frontend dependencies; it is intended for one operator with the private access token.

Important: SQLite on a free Render filesystem is not durable across every deploy or instance replacement. Export the knowledge JSON regularly. For durable unattended memory, configure AGENT_DB_PATH on a persistent disk or migrate to a managed database. No automatic deletion is performed; monitor database size. Failed search or model requests may still consume provider credit. This prototype is for one operator.

Run local verification: `python -m unittest -v`. Tests use a simulated provider response and do not establish live DeepSeek availability or validate API credit.

Provider references: https://api-docs.deepseek.com/ and https://docs.tavily.com/

### Clara voice companion

The main chat features Clara, a clearly labelled AI avatar. Replies default to
matching the latest message, even when an older saved preference pinned a language.
Advanced settings can explicitly override this for the current page. Conversation
turns are sent as separate user/assistant messages to preserve follow-up context.

Select Arabic or English beside the microphone before speaking. Dictation shows
interim text, then leaves the final transcript editable for review. Enable **Voice
conversation** to hear Clara's English-only greeting, send final transcripts
automatically, and resume listening after each spoken reply. Stop or leaving the
tab ends the voice loop. Microphone permission is requested by the browser only
when used. This uses browser speech services, not a paid audio API; compatibility,
voice quality and available female voices vary by device. The voice selector lists
installed Arabic/English voices; automatic selection prefers recognized female
voice names within the reply language. There is no live lip sync, streaming model
audio or continuous interruption detection. Existing free dialogue quotas remain.

The avatar asset was generated with the built-in image generation tool using a
brief for a beautiful, friendly adult woman (about 28), chestnut hair, brown eyes,
navy blouse, centred semi-realistic portrait against dark blue. Runtime animation
is a status ring and waveform; the portrait itself stays still.

Checks: `node tests/clara_voice.test.cjs` and
`python -m unittest tests.test_clara_chat test_arabic_dialogue test_moltbook_dialogue test_response_recovery test_browser_session tests.test_companion_languages -v`.

### Private Clara home-screen app

`/clara/` is a separate, installable home-screen web app containing only chat,
voice and optional camera stills. It has a standalone web manifest and Apple
home-screen icon; it is not an App Store binary. The shell contains no private
messages and is served with `Cache-Control: no-store`. All companion APIs still
require the existing private session or access token. It does not add fees,
subscriptions, a public account system or always-on recording.

Clara can act as a social-relationship and general HR adviser, teach English
when explicitly requested, and adopt a playful, funny or serious tone. These
are prompt behaviours, not a guarantee of expert accuracy or model training.
A user can change the tone naturally in chat or choose it in Settings.

The saved Jordanian HR reference corpus contains 5 source copies and 116 page
passages from the owner's existing reference files. It includes the HR Management
Regulation 33/2024 copy amended through 13 August 2026, promotion bases 2025,
performance instructions 2024, job description/classification instructions 2025,
and critical-job bases. `data/clara_jordan_hr.json` contains only these public
legislative copies and their SPAC source URLs, no owner profile or Library IDs.
Extraction is explicitly unverified and contains OCR errors. Retrieval is lexical;
citation membership/number checks do not prove legal accuracy, completeness or
current validity. Unsupported legal answers fall back to requesting the original
provision. Newer official texts must be checked before relying on a live rule.

Private owner facts can be imported through the authenticated Settings action
from a JSON file with `entries:[{category,fact,as_of}]`. They are kept in private
SQLite dialogue state and the existing encrypted checkpoint, and relevant entries
are selected for model context. The private owner file is deliberately outside
this repository and must never be committed. This is a structured personal summary,
not all past conversations or the full contents of the owner's books.

Complete chat text is appended idempotently to `clara_private_history`. This
separates full storage from the limited context sent to a model; relevant older
messages can be retrieved after rolling context/archive windows. The authenticated
`/companion/history/export` endpoint paginates by sequence and lets the owner
download the whole archive. Existing history can only be backfilled from the
messages still available at first migration; already discarded messages cannot
be reconstructed. **SQLite archive durability depends on the backing storage for
`AGENT_DB_PATH`.** This change does not provision paid storage or establish that
the current Render service uses persistent storage. The full archive is not part
of the pre-existing bounded encrypted checkpoint. A durable backing store or
independent full-archive backup still needs verification before promising retention
across service recreation/redeployment.

The camera starts only when the owner taps Camera and grants browser permission.
Preview is local. Attach still stops the video tracks; a reviewed JPEG is sent
only with an explicit manual Send. A frame is attached to the latest provider
message and is excluded from stored history, profile, public-agent context and
Mem0 writes. It uses the existing `openrouter/free` router, which supports image
inputs according to [OpenRouter's model page](https://openrouter.ai/openrouter/free).
Live model availability and camera/voice on the owner's actual iPhone remain
unverified. There is no continuous vision, face recognition or real-time lip sync.

Additional checks: `python -m unittest tests.test_clara_privacy -v`,
`node tests/clara_camera.test.cjs`, and the Clara chat workflow. Speech, camera and
provider transports are simulated; these tests do not establish live device or
provider behaviour.

### Clara document secretary

The focused app supports private file attachments up to 1.8 MB and 60,000 extracted
characters: DOCX and UTF-8 TXT can receive bounded text replacements; text PDFs
(up to 40 pages) can be read/reviewed. Scanned/encrypted PDFs and macro-enabled
Word packages are unsupported. Complex Word paragraphs containing fields,
hyperlinks, tracked changes, tabs or drawings are not edited automatically.

Uploading saves a private original and a text index. The model receives the
extracted text only when the owner sends a review/edit instruction, using the
existing free router with no paid fallback or automatic retry. Document work has
a separate maximum of six model attempts per UTC day. Total stored file bytes
are limited to 20 MB; storage durability follows the same unverified SQLite
backing store as chat. Uploads do not enter public research or public-agent memory.

Edits must match existing paragraph IDs and unique source substrings. A new copy
is generated, original bytes stay available, and download/change details appear
in chat. Only `word/document.xml` is replaced inside the original DOCX ZIP; all
other package parts remain byte-identical. Replacement text inherits the starting
run's formatting, while unedited run properties/tables remain. This is text
editing, not arbitrary redesign, file merging, PDF layout editing, signatures,
sending correspondence or live Office automation. Document answers and selected
private uploaded excerpts can inform later private conversations.

A representative Arabic/English Word fixture with mixed runs, RTL paragraphs
and a table was edited, rendered and inspected locally. The runtime does not
render every output or certify its layout, so the app explicitly asks the owner
to review content and formatting before relying on an edited document. These
checks validate deterministic edits; live model quality remains unverified.

Document verification: `python -m unittest tests.test_clara_documents -v`.
