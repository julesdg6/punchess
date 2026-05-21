import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess
import chess.pgn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

PORT = int(os.getenv("PUNCHESS_PORT", "8080"))
DEFAULT_REPORT_DIR = str(Path(__file__).resolve().parent.parent / "reports")
REPORT_DIR = Path(os.getenv("PUNCHESS_REPORT_DIR", DEFAULT_REPORT_DIR))
MOVE_TIMEOUT_SECONDS = int(os.getenv("PUNCHESS_MOVE_TIMEOUT_SECONDS", "30"))
ILLEGAL_MOVE_LIMIT = int(os.getenv("PUNCHESS_ILLEGAL_MOVE_LIMIT", "1"))
DISCONNECT_GRACE_SECONDS = int(os.getenv("PUNCHESS_DISCONNECT_GRACE_SECONDS", "10"))
AUTO_START = os.getenv("PUNCHESS_AUTO_START", "true").lower() == "true"

REPORT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Punchess")
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@dataclass
class Agent:
    id: str
    name: str
    metadata: Dict[str, Any]
    connected: bool = False


@dataclass
class Game:
    id: str
    white_id: str
    black_id: str
    created_at: float
    board: chess.Board = field(default_factory=chess.Board)
    moves: List[str] = field(default_factory=list)
    move_times: List[Dict[str, Any]] = field(default_factory=list)
    illegal_attempts: List[Dict[str, Any]] = field(default_factory=list)
    illegal_counts: Dict[str, int] = field(default_factory=dict)
    status: str = "active"
    result: Optional[str] = None
    termination_reason: Optional[str] = None
    ended_at: Optional[float] = None
    current_turn_started_at: float = field(default_factory=time.time)
    pending_disconnect_tasks: Dict[str, asyncio.Task] = field(default_factory=dict)
    move_debug: List[Dict[str, Any]] = field(default_factory=list)
    captures: int = 0
    promotions: int = 0
    castling: int = 0
    checks: int = 0
    material_balance: List[int] = field(default_factory=list)

    def current_player_id(self) -> str:
        return self.white_id if self.board.turn == chess.WHITE else self.black_id


agents: Dict[str, Agent] = {}
lobby: List[str] = []
games: Dict[str, Game] = {}
agent_ws: Dict[str, WebSocket] = {}
viewer_ws: Dict[str, List[WebSocket]] = {}


PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def material_delta(board: chess.Board) -> int:
    white = 0
    black = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.color == chess.WHITE:
            white += value
        else:
            black += value
    return white - black


def game_state(game: Game) -> Dict[str, Any]:
    white = agents[game.white_id]
    black = agents[game.black_id]
    turn_deadline = game.current_turn_started_at + MOVE_TIMEOUT_SECONDS
    return {
        "game_id": game.id,
        "status": game.status,
        "result": game.result,
        "termination_reason": game.termination_reason,
        "players": {
            "white": {"agent_id": white.id, "name": white.name, "metadata": white.metadata},
            "black": {"agent_id": black.id, "name": black.name, "metadata": black.metadata},
        },
        "turn": "white" if game.board.turn == chess.WHITE else "black",
        "turn_agent_id": game.current_player_id(),
        "fen": game.board.fen(),
        "moves": game.moves,
        "move_times": game.move_times,
        "illegal_attempts": game.illegal_attempts,
        "captured_pieces_count": game.captures,
        "checks": game.checks,
        "promotions": game.promotions,
        "castling": game.castling,
        "seconds_left": max(0.0, turn_deadline - time.time()) if game.status == "active" else 0.0,
        "report_url": f"/api/games/{game.id}/report" if game.status == "completed" else None,
    }


async def broadcast_game(game: Game) -> None:
    state = game_state(game)
    payload = json.dumps({"type": "game_update", "data": state})
    for ws in list(viewer_ws.get(game.id, [])):
        try:
            await ws.send_text(payload)
        except Exception:
            viewer_ws[game.id].remove(ws)
    for agent_id in [game.white_id, game.black_id]:
        ws = agent_ws.get(agent_id)
        if ws:
            try:
                await ws.send_text(payload)
            except Exception:
                pass


async def finalize_game(game: Game, result: str, reason: str) -> None:
    if game.status == "completed":
        return
    game.status = "completed"
    game.result = result
    game.termination_reason = reason
    game.ended_at = time.time()
    write_report(game)
    await broadcast_game(game)


def write_report(game: Game) -> None:
    game_dir = REPORT_DIR / game.id
    game_dir.mkdir(parents=True, exist_ok=True)

    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "Punchess"
    pgn_game.headers["White"] = agents[game.white_id].name
    pgn_game.headers["Black"] = agents[game.black_id].name
    pgn_game.headers["Result"] = game.result or "*"
    board = chess.Board()
    node = pgn_game
    for move_uci in game.moves:
        move = chess.Move.from_uci(move_uci)
        node = node.add_variation(move)
        board.push(move)

    report = {
        "game_id": game.id,
        "start_time": datetime.fromtimestamp(game.created_at, tz=timezone.utc).isoformat(),
        "end_time": datetime.fromtimestamp(game.ended_at or time.time(), tz=timezone.utc).isoformat(),
        "total_duration_seconds": (game.ended_at or time.time()) - game.created_at,
        "players": {
            "white": {"name": agents[game.white_id].name, "metadata": agents[game.white_id].metadata},
            "black": {"name": agents[game.black_id].name, "metadata": agents[game.black_id].metadata},
        },
        "result": game.result,
        "termination_reason": game.termination_reason,
        "final_fen": game.board.fen(),
        "pgn": str(pgn_game),
        "moves": game.moves,
        "time_per_move_seconds": game.move_times,
        "average_move_time_seconds": {
            "white": avg_move_time(game.move_times, game.white_id),
            "black": avg_move_time(game.move_times, game.black_id),
        },
        "fastest_move": min(game.move_times, key=lambda x: x["seconds"], default=None),
        "slowest_move": max(game.move_times, key=lambda x: x["seconds"], default=None),
        "illegal_move_attempts": game.illegal_attempts,
        "resignations": [a for a in game.move_debug if a.get("type") == "resign"],
        "timeouts": [a for a in game.move_debug if a.get("type") == "timeout"],
        "material_balance": game.material_balance,
        "checks": game.checks,
        "captures": game.captures,
        "promotions": game.promotions,
        "castling": game.castling,
        "opening_name": None,
    }

    (game_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (game_dir / "game.pgn").write_text(str(pgn_game), encoding="utf-8")

    md = [
        f"# Punchess Report: {game.id}",
        f"- Start: {report['start_time']}",
        f"- End: {report['end_time']}",
        f"- Duration seconds: {report['total_duration_seconds']:.2f}",
        f"- White: {agents[game.white_id].name}",
        f"- Black: {agents[game.black_id].name}",
        f"- Result: {game.result}",
        f"- Termination: {game.termination_reason}",
        f"- Final FEN: `{game.board.fen()}`",
        "",
        "## Moves",
        " ".join(game.moves) if game.moves else "(no moves)",
        "",
        "## Stats",
        f"- Checks: {game.checks}",
        f"- Captures: {game.captures}",
        f"- Promotions: {game.promotions}",
        f"- Castling: {game.castling}",
        f"- Illegal attempts: {len(game.illegal_attempts)}",
    ]
    (game_dir / "report.md").write_text("\n".join(md), encoding="utf-8")


def avg_move_time(move_times: List[Dict[str, Any]], agent_id: str) -> float:
    times = [m["seconds"] for m in move_times if m["agent_id"] == agent_id]
    return sum(times) / len(times) if times else 0.0


async def mark_timeout_if_needed(game: Game) -> None:
    if game.status != "active":
        return
    if time.time() <= game.current_turn_started_at + MOVE_TIMEOUT_SECONDS:
        return
    loser = game.current_player_id()
    game.move_debug.append({"type": "timeout", "agent_id": loser, "at": utc_now()})
    winner = game.black_id if loser == game.white_id else game.white_id
    await finalize_game(game, "1-0" if winner == game.white_id else "0-1", "timeout")


async def create_game_if_ready() -> Optional[Game]:
    if len(lobby) < 2 or not AUTO_START:
        return None
    white_id = lobby.pop(0)
    black_id = lobby.pop(0)
    game = Game(id=str(uuid.uuid4()), white_id=white_id, black_id=black_id, created_at=time.time())
    game.illegal_counts = {white_id: 0, black_id: 0}
    game.material_balance.append(material_delta(game.board))
    games[game.id] = game
    await broadcast_game(game)
    return game


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "port": PORT})


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agents/register")
async def register_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    agent_id = str(uuid.uuid4())
    agents[agent_id] = Agent(id=agent_id, name=name, metadata=payload.get("metadata", {}))
    return {"agent_id": agent_id, "name": name}


@app.post("/api/lobby/join")
async def join_lobby(payload: Dict[str, Any]) -> Dict[str, Any]:
    agent_id = payload.get("agent_id")
    if agent_id not in agents:
        raise HTTPException(status_code=400, detail="unregistered client")
    if agent_id not in lobby:
        lobby.append(agent_id)
    game = await create_game_if_ready()
    assigned = None
    if game:
        assigned = "white" if game.white_id == agent_id else "black"
        return {"status": "paired", "game_id": game.id, "assigned_color": assigned}
    return {"status": "queued"}


@app.get("/api/games/{game_id}")
async def get_game(game_id: str) -> Dict[str, Any]:
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="game not found")
    await mark_timeout_if_needed(game)
    return game_state(game)


@app.post("/api/games/{game_id}/move")
async def submit_move(game_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="game not found")

    agent_id = payload.get("agent_id")
    if agent_id not in agents:
        raise HTTPException(status_code=400, detail="unregistered client")
    if game.status != "active":
        raise HTTPException(status_code=400, detail="game completed")

    now = time.time()
    if now > game.current_turn_started_at + MOVE_TIMEOUT_SECONDS:
        game.move_debug.append({"type": "timeout", "agent_id": game.current_player_id(), "at": utc_now()})
        loser = game.current_player_id()
        winner = game.black_id if loser == game.white_id else game.white_id
        await finalize_game(game, "1-0" if winner == game.white_id else "0-1", "timeout")
        raise HTTPException(status_code=400, detail="move submitted after timeout")

    if agent_id != game.current_player_id():
        raise HTTPException(status_code=400, detail="not this player's turn")

    move_uci = payload.get("move")
    if not isinstance(move_uci, str):
        raise HTTPException(status_code=400, detail="invalid UCI string")

    try:
        move = chess.Move.from_uci(move_uci)
    except ValueError:
        await handle_illegal(game, agent_id, move_uci, "invalid UCI")
        return {"status": "illegal", "detail": "invalid UCI string"}

    if move not in game.board.legal_moves:
        await handle_illegal(game, agent_id, move_uci, "illegal move")
        return {"status": "illegal", "detail": "illegal move"}

    elapsed = now - game.current_turn_started_at
    game.move_times.append({"ply": len(game.moves) + 1, "agent_id": agent_id, "seconds": elapsed, "move": move_uci})
    if game.board.is_capture(move):
        game.captures += 1
    if move.promotion:
        game.promotions += 1
    if game.board.is_castling(move):
        game.castling += 1

    game.board.push(move)
    game.moves.append(move_uci)
    if game.board.is_check():
        game.checks += 1
    game.material_balance.append(material_delta(game.board))

    game.current_turn_started_at = time.time()

    if game.board.is_game_over(claim_draw=True):
        outcome = game.board.outcome(claim_draw=True)
        result = outcome.result() if outcome else "1/2-1/2"
        reason = outcome.termination.name.lower() if outcome else "game_over"
        await finalize_game(game, result, reason)
    else:
        await broadcast_game(game)

    return {"status": "ok", "game": game_state(game)}


async def handle_illegal(game: Game, agent_id: str, move_uci: str, reason: str) -> None:
    game.illegal_counts[agent_id] = game.illegal_counts.get(agent_id, 0) + 1
    game.illegal_attempts.append(
        {
            "agent_id": agent_id,
            "move": move_uci,
            "reason": reason,
            "count": game.illegal_counts[agent_id],
            "at": utc_now(),
        }
    )
    if game.illegal_counts[agent_id] > ILLEGAL_MOVE_LIMIT:
        winner = game.black_id if agent_id == game.white_id else game.white_id
        await finalize_game(game, "1-0" if winner == game.white_id else "0-1", "illegal_move_forfeit")
    else:
        await broadcast_game(game)


@app.post("/api/games/{game_id}/resign")
async def resign(game_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="game not found")
    agent_id = payload.get("agent_id")
    if agent_id not in agents:
        raise HTTPException(status_code=400, detail="unregistered client")
    if game.status != "active":
        raise HTTPException(status_code=400, detail="game completed")
    if agent_id not in [game.white_id, game.black_id]:
        raise HTTPException(status_code=400, detail="agent not in game")

    game.move_debug.append({"type": "resign", "agent_id": agent_id, "at": utc_now()})
    winner = game.black_id if agent_id == game.white_id else game.white_id
    await finalize_game(game, "1-0" if winner == game.white_id else "0-1", "resignation")
    return {"status": "ok", "game": game_state(game)}


@app.get("/api/games/{game_id}/report")
async def game_report(game_id: str):
    report_path = REPORT_DIR / game_id / "report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="report not found")
    return JSONResponse(json.loads(report_path.read_text(encoding="utf-8")))


@app.get("/api/reports")
async def list_reports() -> Dict[str, Any]:
    reports = []
    for game_id in sorted(games.keys()):
        game = games[game_id]
        if game.status == "completed":
            reports.append(
                {
                    "game_id": game_id,
                    "result": game.result,
                    "termination_reason": game.termination_reason,
                    "report_json": f"/reports/{game_id}/report.json",
                    "report_md": f"/reports/{game_id}/report.md",
                    "game_pgn": f"/reports/{game_id}/game.pgn",
                }
            )
    return {"reports": reports}


@app.websocket("/ws/viewer/{game_id}")
async def ws_viewer(websocket: WebSocket, game_id: str):
    await websocket.accept()
    viewer_ws.setdefault(game_id, []).append(websocket)
    if game_id in games:
        await websocket.send_text(json.dumps({"type": "game_update", "data": game_state(games[game_id])}))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in viewer_ws.get(game_id, []):
            viewer_ws[game_id].remove(websocket)


@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(websocket: WebSocket, agent_id: str):
    if agent_id not in agents:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    agent_ws[agent_id] = websocket
    agents[agent_id].connected = True

    for game in games.values():
        if agent_id in [game.white_id, game.black_id]:
            task = game.pending_disconnect_tasks.pop(agent_id, None)
            if task and not task.done():
                task.cancel()

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        agents[agent_id].connected = False
        if agent_ws.get(agent_id) is websocket:
            agent_ws.pop(agent_id, None)
        await schedule_disconnect_forfeit(agent_id)


async def schedule_disconnect_forfeit(agent_id: str) -> None:
    for game in games.values():
        if game.status != "active" or agent_id not in [game.white_id, game.black_id]:
            continue

        async def do_forfeit(g: Game, a: str):
            await asyncio.sleep(DISCONNECT_GRACE_SECONDS)
            if agents.get(a) and not agents[a].connected and g.status == "active":
                winner = g.black_id if a == g.white_id else g.white_id
                await finalize_game(g, "1-0" if winner == g.white_id else "0-1", "disconnect")

        game.pending_disconnect_tasks[agent_id] = asyncio.create_task(do_forfeit(game, agent_id))


app.mount("/reports", StaticFiles(directory=str(REPORT_DIR)), name="reports")
