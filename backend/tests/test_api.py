import random

from chess_coach.api import create_app
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor
from fastapi.testclient import TestClient
from test_service import FakeEngine, opening_end_session


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

        suggested = client.post(f"/api/sessions/{session.json()['session_id']}/suggestion")

        assert suggested.status_code == 200
        assert suggested.json()["basis"] == "theory"
        assert suggested.json()["move_uci"] in session.json()["legal_moves"]
        assert suggested.json()["move_san"]

        answered = client.post(
            f"/api/sessions/{session.json()['session_id']}/questions",
            json={
                "question": "Warum ist dieser Zug gut?",
                "focus_move_uci": suggested.json()["move_uci"],
            },
        )

        assert answered.status_code == 200
        assert answered.json()["message"]["kind"] == "question"
        assert answered.json()["message"]["move"] == suggested.json()["move_san"]

        played = client.post(
            f"/api/sessions/{session.json()['session_id']}/moves",
            json={"from_square": "e2", "to_square": "e4"},
        )

        assert played.status_code == 200
        assert played.json()["move_history"][0]["san"] == "e4"

        undone = client.post(f"/api/sessions/{session.json()['session_id']}/undo")

        assert undone.status_code == 200
        assert undone.json()["move_history"] == []
        assert undone.json()["message_history"] == answered.json()["message_history"]
        assert undone.json()["can_undo"] is False


def test_api_finishes_and_persists_opening_summary() -> None:
    service = CoachService(
        OpeningBook(),
        FakeEngine(),
        OllamaTutor("http://127.0.0.1:1", timeout=0.01),
        SQLiteStore(":memory:"),
        rng=random.Random(3),
    )
    session_id, _ = opening_end_session(service)
    active = service.sessions[session_id]
    active.phase = "transition"
    active.opening_end = service._opening_end_evidence(active)

    with TestClient(create_app(service)) as client:
        reviewed = client.post(f"/api/sessions/{session_id}/opening/summary")

        assert reviewed.status_code == 200
        assert reviewed.json()["phase"] == "complete"
        assert reviewed.json()["opening_summary"]["opening"]["name"] == "Italian Game"

        repeated = client.post(f"/api/sessions/{session_id}/opening/summary")

        assert repeated.status_code == 200
        assert repeated.json()["opening_summary"] == reviewed.json()["opening_summary"]
