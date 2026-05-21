# Punchess

Punchess is a Dockerised web chess arena where chess bots play via API clients.

## Quick start

```bash
docker compose up --build
```

Web UI: `http://localhost:8080`

## Environment variables

- `PUNCHESS_PORT` (default `8080`)
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

## Python bot template

See `clients/python_template/` for a random legal-move bot starter.
