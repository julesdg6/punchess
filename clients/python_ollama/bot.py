import os
import re
import time
from typing import Any, Dict, Iterable, List

import chess
import httpx

BASE_URL = os.getenv("PUNCHESS_URL", "http://localhost:2700")
BOT_NAME = os.getenv("PUNCHESS_BOT_NAME", "ollama-bot")
OLLAMA_URL = os.getenv("PUNCHESS_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("PUNCHESS_OLLAMA_MODEL", "llama3.2")
POLL_INTERVAL_SECONDS = float(os.getenv("PUNCHESS_POLL_INTERVAL_SECONDS", "0.5"))
HTTP_TIMEOUT_SECONDS = float(os.getenv("PUNCHESS_HTTP_TIMEOUT_SECONDS", "30"))
OLLAMA_TEMPERATURE = float(os.getenv("PUNCHESS_OLLAMA_TEMPERATURE", "0"))

UCI_MOVE_RE = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b")


def legal_moves(game_state: Dict[str, Any]) -> List[str]:
    board = chess.Board(game_state["fen"])
    return [move.uci() for move in board.legal_moves]


def build_prompt(game_state: Dict[str, Any], moves: Iterable[str]) -> str:
    move_list = list(moves)
    previous_moves = " ".join(game_state.get("moves", [])) or "(start of game)"
    return (
        "You are playing chess in a Punchess API match.\n"
        f"Game ID: {game_state['game_id']}\n"
        f"Side to move: {game_state['turn']}\n"
        f"FEN: {game_state['fen']}\n"
        f"Previous moves: {previous_moves}\n"
        "Choose exactly one legal move from this list and reply with only the move in UCI format.\n"
        f"Legal moves: {', '.join(move_list)}"
    )


def extract_move(response_text: str, moves: Iterable[str]) -> str:
    legal = {move.lower() for move in moves}
    candidate = response_text.strip().lower()
    if candidate in legal:
        return candidate

    for match in UCI_MOVE_RE.findall(response_text):
        lowered = match.lower()
        if lowered in legal:
            return lowered

    raise ValueError(f"no legal UCI move found in Ollama response: {response_text!r}")


def request_llm_move(game_state: Dict[str, Any], client: httpx.Client) -> str:
    moves = legal_moves(game_state)
    response = client.post(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": build_prompt(game_state, moves),
            "stream": False,
            "options": {"temperature": OLLAMA_TEMPERATURE},
        },
    )
    response.raise_for_status()
    payload = response.json()
    text = payload.get("response")
    if not isinstance(text, str):
        raise ValueError(f"unexpected Ollama response payload: {payload!r}")
    return extract_move(text, moves)


def main() -> None:
    with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
        register = client.post(
            f"{BASE_URL}/api/agents/register",
            json={
                "name": BOT_NAME,
                "metadata": {"template": "python", "strategy": "ollama", "model": OLLAMA_MODEL},
            },
        )
        register.raise_for_status()
        agent_id = register.json()["agent_id"]

        game_id = None
        while not game_id:
            join = client.post(f"{BASE_URL}/api/lobby/join", json={"agent_id": agent_id})
            join.raise_for_status()
            info = join.json()
            game_id = info.get("game_id")
            if not game_id:
                print("Waiting in lobby...")
                time.sleep(1)

        print(f"Joined game {game_id}")

        while True:
            state = client.get(f"{BASE_URL}/api/games/{game_id}")
            state.raise_for_status()
            game_state = state.json()
            if game_state["status"] != "active":
                print(f"Game complete: {game_state['result']} ({game_state['termination_reason']})")
                break

            if game_state["turn_agent_id"] != agent_id:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            try:
                move = request_llm_move(game_state, client)
            except Exception as exc:
                print(f"Ollama move selection failed: {exc}")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            print(f"Playing {move}")
            resp = client.post(
                f"{BASE_URL}/api/games/{game_id}/move",
                json={"agent_id": agent_id, "move": move, "debug": {"source": "python_ollama", "model": OLLAMA_MODEL}},
            )
            if resp.status_code >= 400:
                print("Move rejected", resp.text)
                time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
