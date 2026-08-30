import importlib.util
from pathlib import Path

import pytest

launcher_path = Path(__file__).resolve().parents[2] / "scripts" / "start_local.py"
launcher_spec = importlib.util.spec_from_file_location("start_local", launcher_path)
assert launcher_spec and launcher_spec.loader
launcher = importlib.util.module_from_spec(launcher_spec)
launcher_spec.loader.exec_module(launcher)
configured_port = launcher.configured_port


def test_launcher_uses_stable_default_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHESS_COACH_BACKEND_PORT", raising=False)
    monkeypatch.delenv("CHESS_COACH_FRONTEND_PORT", raising=False)

    assert configured_port("CHESS_COACH_BACKEND_PORT", 53686) == 53686
    assert configured_port("CHESS_COACH_FRONTEND_PORT", 53687) == 53687


def test_launcher_rejects_invalid_configured_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHESS_COACH_FRONTEND_PORT", "not-a-port")

    with pytest.raises(ValueError, match="muss eine Portnummer sein"):
        configured_port("CHESS_COACH_FRONTEND_PORT", 53687)
