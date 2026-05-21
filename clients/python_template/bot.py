import os
import random
import time
from typing import Dict, Any

import requests
import chess

BASE_URL = os.getenv("PUNCHESS_URL", "http://localhost:8080")
BOT_NAME = os.getenv("PUNCHESS_BOT_NAME", "random-bot")


def choose_move(game_state: Dict[str, Any]) -> str:
    board = chess.Board(game_state["fen"])
    return random.choice(list(board.legal_moves)).uci()


def main() -> None:
    register = requests.post(f"{BASE_URL}/api/agents/register", json={"name": BOT_NAME, "metadata": {"template": "python"}})
    register.raise_for_status()
    agent_id = register.json()["agent_id"]

    game_id = None
    while not game_id:
        join = requests.post(f"{BASE_URL}/api/lobby/join", json={"agent_id": agent_id})
        join.raise_for_status()
        info = join.json()
        game_id = info.get("game_id")
        if not game_id:
            print("Waiting in lobby...")
            time.sleep(1)

    print(f"Joined game {game_id}")

    while True:
        state = requests.get(f"{BASE_URL}/api/games/{game_id}")
        state.raise_for_status()
        game_state = state.json()
        if game_state["status"] != "active":
            print("Game complete", game_state["result"], game_state["termination_reason"])
            break

        if game_state["turn_agent_id"] != agent_id:
            time.sleep(0.5)
            continue

        move = choose_move(game_state)
        print(f"Playing {move}")
        resp = requests.post(
            f"{BASE_URL}/api/games/{game_id}/move",
            json={"agent_id": agent_id, "move": move, "debug": {"source": "python_template"}},
        )
        if resp.status_code >= 400:
            print("Move rejected", resp.text)
            time.sleep(0.5)


if __name__ == "__main__":
    main()
