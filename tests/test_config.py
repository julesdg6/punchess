import importlib

from server.app import main


def test_default_port_is_2700(monkeypatch):
    monkeypatch.delenv("PUNCHESS_PORT", raising=False)
    reloaded = importlib.reload(main)
    assert reloaded.PORT == 2700
