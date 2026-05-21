import chess

from clients.python_bootchess.bot import capture_value, choose_move, taxi_distance


def test_choose_move_returns_legal_move():
    game_state = {"fen": chess.STARTING_FEN}

    move = choose_move(game_state)

    assert chess.Move.from_uci(move) in chess.Board(game_state["fen"]).legal_moves


def test_choose_move_prefers_high_value_capture():
    game_state = {"fen": "4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1"}

    assert choose_move(game_state) == "e4d5"


def test_choose_move_prefers_closer_move_when_no_capture():
    game_state = {"fen": "4k3/8/8/8/8/8/4N3/4K3 w - - 0 1"}
    board = chess.Board(game_state["fen"])
    opponent_king = board.king(chess.BLACK)

    move = chess.Move.from_uci(choose_move(game_state))
    best_distance = min(taxi_distance(legal_move.to_square, opponent_king) for legal_move in board.legal_moves)

    assert taxi_distance(move.to_square, opponent_king) == best_distance


def test_capture_value_handles_en_passant():
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")

    assert capture_value(board, chess.Move.from_uci("e5d6")) == 4


def test_capture_value_handles_standard_capture():
    board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")

    assert capture_value(board, chess.Move.from_uci("e4d5")) == 24


def test_taxi_distance_counts_file_and_rank_steps():
    assert taxi_distance(chess.E2, chess.E8) == 6
