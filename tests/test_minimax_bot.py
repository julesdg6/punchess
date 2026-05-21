import chess
import pytest

from clients.python_minimax.bot import choose_move, search_depth


def test_choose_move_returns_legal_move():
    game_state = {"fen": chess.STARTING_FEN}

    move = choose_move(game_state)

    assert chess.Move.from_uci(move) in chess.Board(game_state["fen"]).legal_moves


def test_choose_move_prefers_winning_queen():
    game_state = {"fen": "4k3/8/8/8/8/8/4q3/3QK3 w - - 0 1"}
    board = chess.Board(game_state["fen"])

    move = choose_move(game_state)
    board.push(chess.Move.from_uci(move))

    assert board.piece_at(chess.E2).color == chess.WHITE
    assert not board.pieces(chess.QUEEN, chess.BLACK)


def test_search_depth_rejects_invalid_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PUNCHESS_MINIMAX_DEPTH", "nope")

    with pytest.raises(ValueError, match="PUNCHESS_MINIMAX_DEPTH must be an integer"):
        search_depth()
