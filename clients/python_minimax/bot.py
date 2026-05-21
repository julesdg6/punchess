import math
import os
import time
from typing import Any, Dict, Optional, Tuple

import chess
import requests

BASE_URL = os.getenv("PUNCHESS_URL", "http://localhost:2700")
BOT_NAME = os.getenv("PUNCHESS_BOT_NAME", "minimax-bot")
CHECKMATE_SCORE = 100000
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


def search_depth() -> int:
    raw_depth = os.getenv("PUNCHESS_MINIMAX_DEPTH", "2")
    try:
        return max(1, int(raw_depth))
    except ValueError as exc:
        raise ValueError(f"PUNCHESS_MINIMAX_DEPTH must be an integer, got {raw_depth!r}") from exc


def evaluate_board(board: chess.Board, root_turn: bool) -> int:
    if board.is_checkmate():
        return -CHECKMATE_SCORE if board.turn == root_turn else CHECKMATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
        return 0

    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value
    return score if root_turn == chess.WHITE else -score


def minimax(board: chess.Board, depth: int, root_turn: bool, alpha: float, beta: float) -> Tuple[int, Optional[chess.Move]]:
    if depth == 0 or board.is_game_over():
        return evaluate_board(board, root_turn), None

    best_move = None

    if board.turn == root_turn:
        best_score = -math.inf
        for move in board.legal_moves:
            board.push(move)
            score, _ = minimax(board, depth - 1, root_turn, alpha, beta)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, best_score)
            if alpha >= beta:
                break
        return int(best_score), best_move

    best_score = math.inf
    for move in board.legal_moves:
        board.push(move)
        score, _ = minimax(board, depth - 1, root_turn, alpha, beta)
        board.pop()
        if score < best_score:
            best_score = score
            best_move = move
        beta = min(beta, best_score)
        if alpha >= beta:
            break
    return int(best_score), best_move


def choose_move(game_state: Dict[str, Any]) -> str:
    board = chess.Board(game_state["fen"])
    _, move = minimax(board, search_depth(), board.turn, -math.inf, math.inf)
    if move is None:
        raise ValueError("no legal moves available")
    return move.uci()


def main() -> None:
    depth = search_depth()
    register = requests.post(
        f"{BASE_URL}/api/agents/register",
        json={"name": BOT_NAME, "metadata": {"template": "python", "strategy": "minimax", "depth": depth}},
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
            json={"agent_id": agent_id, "move": move, "debug": {"source": "python_minimax", "depth": depth}},
        )
        if resp.status_code >= 400:
            print("Move rejected", resp.text)
            time.sleep(0.5)


if __name__ == "__main__":
    main()
