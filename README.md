# AgentBroker — research and knowledge-memory prototype

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
