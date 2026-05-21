import os
import time
from typing import Any, Dict

import chess
import requests

BASE_URL = os.getenv("PUNCHESS_URL", "http://localhost:2700")
BOT_NAME = os.getenv("PUNCHESS_BOT_NAME", "bootchess-bot")
PIECE_VALUES = {
    chess.PAWN: 4,
    chess.KNIGHT: 8,
    chess.BISHOP: 12,
    chess.ROOK: 16,
    chess.QUEEN: 24,
    chess.KING: 32,
}


def capture_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    captured_piece = board.piece_at(move.to_square)
    if captured_piece is None:
        return 0
    return PIECE_VALUES[captured_piece.piece_type]


def taxi_distance(square_a: chess.Square, square_b: chess.Square) -> int:
    return abs(chess.square_file(square_a) - chess.square_file(square_b)) + abs(
        chess.square_rank(square_a) - chess.square_rank(square_b)
    )


def choose_move(game_state: Dict[str, Any]) -> str:
    board = chess.Board(game_state["fen"])
    opponent_king = board.king(not board.turn)
    if opponent_king is None:
        raise ValueError("opponent king not found")

    best_move = None
    best_score = None
    for move in board.legal_moves:
        score = (capture_value(board, move), -taxi_distance(move.to_square, opponent_king))
        if best_score is None or score > best_score:
            best_score = score
            best_move = move

    if best_move is None:
        raise ValueError("no legal moves available")
    return best_move.uci()


def main() -> None:
    register = requests.post(
        f"{BASE_URL}/api/agents/register",
        json={"name": BOT_NAME, "metadata": {"template": "python", "strategy": "bootchess"}},
    )
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
            json={"agent_id": agent_id, "move": move, "debug": {"source": "python_bootchess"}},
        )
        if resp.status_code >= 400:
            print("Move rejected", resp.text)
            time.sleep(0.5)


if __name__ == "__main__":
    main()
