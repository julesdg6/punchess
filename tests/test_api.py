import shutil
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import main
from server.app.main import app


@pytest.fixture(autouse=True)
def reset_state():
    main.agents.clear()
    main.lobby.clear()
    main.games.clear()
    main.agent_ws.clear()
    main.viewer_ws.clear()
    shutil.rmtree(Path(main.REPORT_DIR), ignore_errors=True)
    Path(main.REPORT_DIR).mkdir(parents=True, exist_ok=True)


def test_register_join_and_move_flow():
    client = TestClient(app)
    a = client.post("/api/agents/register", json={"name": "A"}).json()["agent_id"]
    b = client.post("/api/agents/register", json={"name": "B"}).json()["agent_id"]

    client.post("/api/lobby/join", json={"agent_id": a})
    paired = client.post("/api/lobby/join", json={"agent_id": b}).json()
    game_id = paired["game_id"]

    game = client.get(f"/api/games/{game_id}").json()
    white_id = game["players"]["white"]["agent_id"]

    ok = client.post(f"/api/games/{game_id}/move", json={"agent_id": white_id, "move": "e2e4"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "ok"


def test_illegal_move_forfeit_after_limit():
    client = TestClient(app)
    a = client.post("/api/agents/register", json={"name": "A2"}).json()["agent_id"]
    b = client.post("/api/agents/register", json={"name": "B2"}).json()["agent_id"]

    client.post("/api/lobby/join", json={"agent_id": a})
    paired = client.post("/api/lobby/join", json={"agent_id": b}).json()
    game_id = paired["game_id"]

    game = client.get(f"/api/games/{game_id}").json()
    white_id = game["players"]["white"]["agent_id"]

    first = client.post(f"/api/games/{game_id}/move", json={"agent_id": white_id, "move": "bad"})
    assert first.status_code == 200
    assert first.json()["status"] == "illegal"

    second = client.post(f"/api/games/{game_id}/move", json={"agent_id": white_id, "move": "bad"})
    assert second.status_code == 200

    final_state = client.get(f"/api/games/{game_id}").json()
    assert final_state["status"] == "completed"
    assert final_state["termination_reason"] == "illegal_move_forfeit"

    report = client.get(f"/api/games/{game_id}/report")
    assert report.status_code == 200


def test_join_lobby_returns_existing_pairing_for_first_agent():
    client = TestClient(app)
    white = client.post("/api/agents/register", json={"name": "White"}).json()["agent_id"]
    black = client.post("/api/agents/register", json={"name": "Black"}).json()["agent_id"]

    first_join = client.post("/api/lobby/join", json={"agent_id": white}).json()
    second_join = client.post("/api/lobby/join", json={"agent_id": black}).json()
    repeated_first_join = client.post("/api/lobby/join", json={"agent_id": white}).json()

    assert first_join["status"] == "queued"
    assert second_join["status"] == "paired"
    assert repeated_first_join == {
        "status": "paired",
        "game_id": second_join["game_id"],
        "assigned_color": "white",
    }


def test_index_renders_pre_game_menu():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'Pre-game menu' in response.text
    assert 'Start bundled match' in response.text
    assert 'value="python_template"' in response.text
    assert 'value="python_minimax"' in response.text


def test_launch_match_spawns_bundled_clients_and_returns_game(monkeypatch: pytest.MonkeyPatch):
    client = TestClient(app)
    launched = []

    def fake_popen(command, **kwargs):
        launched.append({"command": command, "kwargs": kwargs})
        return SimpleNamespace(pid=9000 + len(launched))

    async def fake_wait_for_agent_in_lobby(name, registered_after, timeout=5.0):
        return f"{name}-agent"

    async def fake_wait_for_launched_game(white_name, black_name, created_after, timeout=5.0):
        return SimpleNamespace(id="game-123")

    monkeypatch.setattr(main.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(main, "wait_for_agent_in_lobby", fake_wait_for_agent_in_lobby)
    monkeypatch.setattr(main, "wait_for_launched_game", fake_wait_for_launched_game)

    response = client.post(
        "/api/matches/launch",
        json={
            "white_client": "python_template",
            "white_name": "Alpha",
            "black_client": "python_minimax",
            "black_name": "Beta",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paired"
    assert response.json()["game_id"] == "game-123"
    assert [entry["command"][1] for entry in launched] == [
        str(main.REPO_ROOT / "clients/python_template/bot.py"),
        str(main.REPO_ROOT / "clients/python_minimax/bot.py"),
    ]
    assert launched[0]["kwargs"]["env"]["PUNCHESS_BOT_NAME"] == "Alpha"
    assert launched[1]["kwargs"]["env"]["PUNCHESS_BOT_NAME"] == "Beta"
    assert launched[0]["kwargs"]["env"]["PUNCHESS_URL"] == "http://127.0.0.1:2700"


def test_launch_match_rejects_unknown_client():
    client = TestClient(app)

    response = client.post(
        "/api/matches/launch",
        json={"white_client": "missing", "black_client": "python_template"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unknown bundled client"


def test_list_games_returns_active_and_completed_games():
    client = TestClient(app)
    a = client.post("/api/agents/register", json={"name": "ListA"}).json()["agent_id"]
    b = client.post("/api/agents/register", json={"name": "ListB"}).json()["agent_id"]

    client.post("/api/lobby/join", json={"agent_id": a})
    paired = client.post("/api/lobby/join", json={"agent_id": b}).json()
    game_id = paired["game_id"]

    response = client.get("/api/games")
    assert response.status_code == 200
    data = response.json()
    assert any(g["game_id"] == game_id for g in data["games"])
    entry = next(g for g in data["games"] if g["game_id"] == game_id)
    assert entry["status"] == "active"
    assert entry["white"] == "ListA"
    assert entry["black"] == "ListB"
