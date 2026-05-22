import os
import random
import time
from typing import Dict, Any

import requests
import chess

BASE_URL = os.getenv("PUNCHESS_URL", "http://localhost:2700")
BOT_NAME = os.getenv("PUNCHESS_BOT_NAME", "random-bot")
RETRY_DELAY_SECONDS = float(os.getenv("PUNCHESS_RETRY_DELAY_SECONDS", "2"))
MAX_RETRIES = int(os.getenv("PUNCHESS_MAX_RETRIES", "10"))


def choose_move(game_state: Dict[str, Any]) -> str:
    board = chess.Board(game_state["fen"])
    return random.choice(list(board.legal_moves)).uci()


def main() -> None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            register = requests.post(f"{BASE_URL}/api/agents/register", json={"name": BOT_NAME, "metadata": {"template": "python"}})
            register.raise_for_status()
            break
        except Exception as exc:
            print(f"Registration attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY_SECONDS)
    agent_id = register.json()["agent_id"]

    game_id = None
    while not game_id:
        try:
            join = requests.post(f"{BASE_URL}/api/lobby/join", json={"agent_id": agent_id})
            join.raise_for_status()
            info = join.json()
            game_id = info.get("game_id")
            if not game_id:
                print("Waiting in lobby...")
                time.sleep(1)
        except Exception as exc:
            print(f"Lobby join error: {exc}")
            time.sleep(RETRY_DELAY_SECONDS)

    print(f"Joined game {game_id}")

    while True:
        try:
            state = requests.get(f"{BASE_URL}/api/games/{game_id}")
            state.raise_for_status()
            game_state = state.json()
        except Exception as exc:
            print(f"Error polling game state: {exc}")
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        if game_state["status"] != "active":
            print("Game complete", game_state["result"], game_state["termination_reason"])
            break

        if game_state["turn_agent_id"] != agent_id:
            time.sleep(0.5)
            continue

        move = choose_move(game_state)
        print(f"Playing {move}")
        try:
            resp = requests.post(
                f"{BASE_URL}/api/games/{game_id}/move",
                json={"agent_id": agent_id, "move": move, "debug": {"source": "python_template"}},
            )
            if resp.status_code >= 400:
                print("Move rejected", resp.text)
                time.sleep(0.5)
        except Exception as exc:
            print(f"Error submitting move: {exc}")
            time.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    main()
