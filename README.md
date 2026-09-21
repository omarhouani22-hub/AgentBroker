# AgentBroker — DeepSeek execution prototype

This is replacement code, not a deployed service. It calls DeepSeek, executes an allowlisted service-margin calculator, feeds the result back to the model, and stores the output and tool results in SQLite. Four model requests maximum per run; each can incur provider charges. No unattended scheduler, browsing, outreach, payment or self-training is implemented.

## Setup on the existing Render service

1. Replace app.py, requirements.txt and render.yaml in the existing GitHub repository with these files. Keep tests and this README too.
2. In Render > Environment set DEEPSEEK_API_KEY to your provider API key and AGENT_ACCESS_TOKEN to a private random string of at least 32 characters. Never commit either value or paste them into chat. A chat login is not an API key.
3. In Render > Settings set Start Command to `gunicorn --workers 1 --threads 1 --timeout 120 app:app`. Updating render.yaml alone may not update an existing manually configured service.
4. Deploy and verify GET /health reports 1.0-deepseek-agent. Open GET / in a browser; the page warns if either required variable is missing, but this does NOT prove provider credentials work.
5. Enter AGENT_ACCESS_TOKEN and a task in the browser page, then choose Run task. The token stays in the page's memory and is not stored by the page. For the live acceptance check use: `Prepare an HR service offer. Price 100, hours 3, hourly cost 15, other cost 5; calculate margin and label all assumptions.` These numbers use one chosen currency. Do not include sensitive HR records.
6. Success requires a completed output and an events entry with cost=50, profit=50 and margin_percent=50. This is the live acceptance check, not yet performed by the author.

The JSON API remains available: authenticated POST /runs starts a run and GET /runs/ID retrieves one. /quote also requires authentication. The browser page deliberately has no account system or extra frontend dependencies; it is intended for one operator with the private access token.

SQLite survives process restarts on the same filesystem, but not ephemeral Render replacement/deploy events. For durable retention configure AGENT_DB_PATH on a persistent disk or migrate to a managed database. No automatic deletion is performed; monitor database size. Failed network requests may still have consumed provider credit. Single worker processes one run at a time; this prototype is for one operator.

Run local verification: `python -m unittest -v`. Tests use a simulated provider response and do not establish live DeepSeek availability or validate API credit.

Provider reference: https://api-docs.deepseek.com/guides/tool_calls
