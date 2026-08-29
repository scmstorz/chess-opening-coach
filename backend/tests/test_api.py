import random

from chess_coach.api import create_app
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor
from fastapi.testclient import TestClient
from test_service import FakeEngine


def test_api_session_and_move_round_trip() -> None:
    service = CoachService(
        OpeningBook(),
        FakeEngine(),
        OllamaTutor("http://127.0.0.1:1", timeout=0.01),
        SQLiteStore(":memory:"),
        rng=random.Random(3),
    )
    with TestClient(create_app(service)) as client:
        session = client.post("/api/sessions", json={"color": "white"})
        assert session.status_code == 200

        played = client.post(
            f"/api/sessions/{session.json()['session_id']}/moves",
            json={"from_square": "e2", "to_square": "e4"},
        )

        assert played.status_code == 200
        assert played.json()["move_history"][0]["san"] == "e4"
