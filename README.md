# Punchess

Punchess is a Dockerised web chess arena where chess bots play via API clients.

## Quick start

```bash
docker compose up --build
```

Web UI: `http://localhost:2700`

From the home page you can use the **Pre-game menu** to launch the bundled clients and immediately start a local match.

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
- `POST /api/matches/launch`
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
- `clients/python_minimax/` contains a simple minimax-based bot. The referenced `apostolisv/chess-ai` repository did not expose an explicit license in its repository root files or README, so this bot is an original implementation instead of a direct code copy.

### Launching bundled clients

Use the web UI pre-game menu to choose the white and black bundled clients, then click **Start bundled match**.

You can also launch them over HTTP:

```bash
curl -X POST http://localhost:2700/api/matches/launch \
  -H 'content-type: application/json' \
  -d '{
    "white_client": "python_template",
    "white_name": "Random White",
    "black_client": "python_minimax",
    "black_name": "Mini Black"
  }'
```

When `PUNCHESS_AUTO_START=true` (the default), the server launches the white client first so it joins the lobby first and gets the white pieces.

### Writing your own client

Any homemade client can connect and play as long as it follows the same API flow as the bundled bots:

1. `POST /api/agents/register` with a display name and optional metadata. Save the returned `agent_id`.
2. `POST /api/lobby/join` with that `agent_id` until the response includes a `game_id`.
3. Poll `GET /api/games/{game_id}` (or subscribe to `WS /ws/agent/{agent_id}`) to learn the current position and whose turn it is.
4. When `turn_agent_id` matches your `agent_id`, submit a UCI move such as `e2e4` to `POST /api/games/{game_id}/move`.
5. Optionally resign through `POST /api/games/{game_id}/resign`.

Minimal example payloads:

```json
POST /api/agents/register
{"name":"my-bot","metadata":{"language":"python"}}
```

```json
POST /api/lobby/join
{"agent_id":"<registered-agent-id>"}
```

```json
POST /api/games/<game_id>/move
{"agent_id":"<registered-agent-id>","move":"e2e4"}
```

The starter client in `clients/python_template/bot.py` is the reference implementation for a homemade bot.
