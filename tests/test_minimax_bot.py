import chess

from clients.python_minimax.bot import choose_move


def test_choose_move_returns_legal_move():
    game_state = {"fen": chess.STARTING_FEN}

    move = choose_move(game_state)

    assert chess.Move.from_uci(move) in chess.Board(game_state["fen"]).legal_moves


def test_choose_move_prefers_winning_queen():
    game_state = {"fen": "4k3/8/8/8/8/8/4q3/3QK3 w - - 0 1"}

    move = choose_move(game_state)

    assert move == "d1e2"
