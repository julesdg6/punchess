import shutil
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
