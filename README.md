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
- `clients/python_bootchess/` contains a very simple BootChess-inspired client that prefers captures and otherwise moves closer to the opposing king.
- `clients/python_minimax/` contains a simple minimax-based bot. The referenced `apostolisv/chess-ai` repository did not expose an explicit license in its repository root files or README, so this bot is an original implementation instead of a direct code copy.
