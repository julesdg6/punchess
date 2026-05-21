from clients.python_ollama import bot


def test_build_prompt_includes_position_context():
    game_state = {
        "game_id": "game-1",
        "turn": "white",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "moves": [],
    }

    prompt = bot.build_prompt(game_state, ["e2e4", "d2d4"])

    assert "Game ID: game-1" in prompt
    assert "Side to move: white" in prompt
    assert "Legal moves: e2e4, d2d4" in prompt


def test_build_prompt_includes_previous_moves():
    game_state = {
        "game_id": "game-2",
        "turn": "black",
        "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2",
        "moves": ["e2e4", "e7e5"],
    }

    prompt = bot.build_prompt(game_state, ["g8f6", "b8c6"])

    assert "Previous moves: e2e4 e7e5" in prompt


def test_extract_move_accepts_plain_uci_response():
    assert bot.extract_move("e2e4", ["e2e4", "d2d4"]) == "e2e4"


def test_extract_move_finds_legal_move_inside_text():
    response = "I choose e2e5 first, but the legal move is e2e4."

    assert bot.extract_move(response, ["e2e4", "d2d4"]) == "e2e4"


def test_extract_move_raises_when_no_legal_move_is_present():
    try:
        bot.extract_move("I would castle here.", ["e2e4", "d2d4"])
    except ValueError as exc:
        assert "no legal UCI move found" in str(exc)
    else:
        raise AssertionError("expected ValueError")
