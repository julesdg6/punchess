# Punchess

Punchess is a Dockerised web chess arena where chess bots play via API clients.

## Quick start

```bash
docker compose up --build
```

Web UI: `http://localhost:2700`

## Environment variables

- `PUNCHESS_PORT` (default `2700`)
- `PUNCHESS_REPORT_DIR` (default `/app/reports`)
- `PUNCHESS_MOVE_TIMEOUT_SECONDS` (default `30`)
- `PUNCHESS_ILLEGAL_MOVE_LIMIT` (default `1`)
- `PUNCHESS_DISCONNECT_GRACE_SECONDS` (default `10`)
- `PUNCHESS_AUTO_START` (default `true`)

## API

- `GET /health`
- `POST /api/agents/register`
- `POST /api/lobby/join`
- `GET /api/games/{game_id}`
- `POST /api/games/{game_id}/move`
- `POST /api/games/{game_id}/resign`
- `GET /api/games/{game_id}/report`
- `GET /api/reports`
- `WS /ws/agent/{agent_id}`
- `WS /ws/viewer/{game_id}`

Reports are generated to `/reports/<game_id>/report.json`, `/report.md`, and `/game.pgn`.

## Python clients

- `clients/python_template/` contains a random legal-move bot starter.
- `clients/python_ollama/` contains an LLM-based bot that queries an Ollama model for moves.

### Ollama client

The Ollama client uses the existing Punchess HTTP API and asks a locally running Ollama model to pick a legal move in UCI format.

Environment variables:

- `PUNCHESS_URL` (default `http://localhost:2700`)
- `PUNCHESS_BOT_NAME` (default `ollama-bot`)
- `PUNCHESS_OLLAMA_URL` (default `http://localhost:11434`)
- `PUNCHESS_OLLAMA_MODEL` (default `llama3.2`)
- `PUNCHESS_OLLAMA_TEMPERATURE` (default `0`)
- `PUNCHESS_HTTP_TIMEOUT_SECONDS` (default `30`)
- `PUNCHESS_POLL_INTERVAL_SECONDS` (default `0.5`)

Example:

```bash
PUNCHESS_OLLAMA_MODEL=llama3.2 python clients/python_ollama/bot.py
```
