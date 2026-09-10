import json
import random
from pathlib import Path

import chess
from chess_coach.api import create_app
from chess_coach.guided import ITALIAN_WHITE_LESSON_ID, GuidedLessonBook
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor
from fastapi.testclient import TestClient
from test_service import FakeEngine

REPERTOIRE_PATH = Path(__file__).resolve().parents[2] / "data" / "repertoires"


def guided_service() -> CoachService:
    return CoachService(
        OpeningBook(),
        FakeEngine(),
        OllamaTutor("http://127.0.0.1:1", timeout=0.01),
        SQLiteStore(":memory:"),
        rng=random.Random(4),
        guided_lessons=GuidedLessonBook(REPERTOIRE_PATH),
    )


def test_italian_lesson_loads_from_annotated_pgn() -> None:
    lesson = GuidedLessonBook(REPERTOIRE_PATH).get(ITALIAN_WHITE_LESSON_ID)

    assert lesson.title == "Italienisches Spiel mit Weiß"
    assert lesson.eco == "C50"
    assert lesson.learner_color == chess.WHITE
    assert lesson.learner_move_count == 10
    assert len(lesson.moves) == 20
    assert [move.move_san for move in lesson.moves[:6]] == [
        "e4",
        "e5",
        "Nf3",
        "Nc6",
        "Bc4",
        "Bc5",
    ]
    assert all(len(move.hints) == 2 for move in lesson.moves if move.color == chess.WHITE)
    assert all(move.explanation for move in lesson.moves)


def test_guided_session_asks_immediately_without_revealing_the_move() -> None:
    coach = guided_service()

    response = coach.create_session("random", training_mode="guided")

    assert response["training_mode"] == "guided"
    assert response["learner_color"] == "white"
    assert response["move_history"] == []
    assert response["messages"][0]["kind"] == "prompt"
    assert response["messages"][0]["summary"] == "Du spielst Weiß. Was ist dein erster Zug?"
    assert "e4" not in json.dumps(response["messages"], ensure_ascii=False)
    assert response["training_progress"] == {
        "current": 1,
        "completed": 0,
        "total": 10,
        "question": "Was ist dein erster Zug?",
        "goal": response["lesson"]["goal"],
    }


def test_guided_correct_move_plays_fixed_reply_and_explains_both() -> None:
    coach = guided_service()
    session = coach.create_session("white", training_mode="guided")

    response = coach.play_learner_move(session["session_id"], "e2", "e4")

    assert [move["san"] for move in response["move_history"]] == ["e4", "e5"]
    assert response["messages"][0]["summary"].startswith("Richtig: e4.")
    assert "Zentrum" in response["messages"][0]["summary"]
    assert response["messages"][1]["summary"].startswith("Ich spiele e5.")
    assert response["training_progress"]["current"] == 2
    assert response["training_progress"]["completed"] == 1
    records = coach.store.session_interactions(session["session_id"])
    assert [record["repertoire_match"] for record in records] == [1, 1]
    assert all(record["training_mode"] == "guided" for record in records)
    assert all(record["lesson_id"] == ITALIAN_WHITE_LESSON_ID for record in records)


def test_guided_misses_keep_board_then_reveal_line_on_third_attempt() -> None:
    coach = guided_service()
    session = coach.create_session("white", training_mode="guided")
    initial_fen = session["fen"]

    first = coach.play_learner_move(session["session_id"], "d2", "d4")
    second = coach.play_learner_move(session["session_id"], "c2", "c4")
    third = coach.play_learner_move(session["session_id"], "g1", "f3")

    assert first["fen"] == initial_fen
    assert second["fen"] == initial_fen
    assert first["correction"]["attempt"] == 1
    assert second["correction"]["attempt"] == 2
    assert "Hinweis 1 von 2" in first["messages"][0]["summary"]
    assert "Hinweis 2 von 2" in second["messages"][0]["summary"]
    assert third["correction"] is None
    assert [move["san"] for move in third["move_history"]] == ["e4", "e5"]
    assert third["messages"][0]["summary"].startswith("Gesucht war e4")
    assert third["messages"][1]["move"] == "e5"
    records = coach.store.session_interactions(session["session_id"])
    assert [record["repertoire_match"] for record in records] == [0, 0, 0, 1, 1]


def test_guided_suggestion_reveals_expected_move_without_changing_board() -> None:
    coach = guided_service()
    session = coach.create_session("white", training_mode="guided")

    suggestion = coach.suggest_move(session["session_id"])

    assert suggestion["basis"] == "repertoire"
    assert suggestion["move_uci"] == "e2e4"
    assert suggestion["move_san"] == "e4"
    assert coach.sessions[session["session_id"]].board.fen() == session["fen"]
    assert coach.sessions[session["session_id"]].move_history == []


def test_guided_api_question_uses_authored_plan_for_suggested_move() -> None:
    coach = guided_service()

    with TestClient(create_app(coach)) as client:
        session = client.post(
            "/api/sessions",
            json={"color": "random", "training_mode": "guided"},
        )
        assert session.status_code == 200
        session_id = session.json()["session_id"]

        suggestion = client.post(f"/api/sessions/{session_id}/suggestion")
        answer = client.post(
            f"/api/sessions/{session_id}/questions",
            json={
                "question": "Warum ist dieser Zug gut?",
                "focus_move_uci": suggestion.json()["move_uci"],
            },
        )

        assert suggestion.json()["move_uci"] == "e2e4"
        assert answer.status_code == 200
        assert answer.json()["message"]["summary"] == (
            "Du besetzt das Zentrum und öffnest Dame und Läufer Wege ins Spiel."
        )
        assert answer.json()["message"]["source"] == "guided-repertoire"
        assert any(
            section["title"] == "Mittel- und langfristiger Plan"
            for section in answer.json()["message"]["explanation_sections"]
        )


def test_guided_undo_restores_lesson_position_and_progress() -> None:
    coach = guided_service()
    session = coach.create_session("white", training_mode="guided")
    coach.play_learner_move(session["session_id"], "e2", "e4")

    response = coach.undo_last_turn(session["session_id"])

    assert response["fen"] == session["fen"]
    assert response["move_history"] == []
    assert len(response["message_history"]) == 1
    assert response["message_history"][0]["kind"] == "prompt"
    assert response["training_progress"]["current"] == 1
    assert response["can_undo"] is False


def test_guided_full_self_play_completes_and_can_undo_final_turn() -> None:
    coach = guided_service()
    response = coach.create_session("white", training_mode="guided")
    session_id = response["session_id"]

    for move_uci in (
        "e2e4",
        "g1f3",
        "f1c4",
        "d2d3",
        "e1g1",
        "c2c3",
        "f1e1",
        "c4b3",
        "b1d2",
        "h2h3",
    ):
        response = coach.play_learner_move(
            session_id, move_uci[:2], move_uci[2:4], move_uci[4:] or None
        )

    assert response["phase"] == "complete"
    assert response["training_progress"] is None
    assert len(response["move_history"]) == 20
    assert response["move_history"][-2:] == [
        {"actor": "learner", "san": "h3"},
        {"actor": "coach", "san": "h6"},
    ]
    assert response["messages"][-1]["kind"] == "summary"
    assert response["opening_summary"]["lesson"]["lesson_id"] == ITALIAN_WHITE_LESSON_ID
    assert coach.store.get_session_summary(session_id) is not None

    undone = coach.undo_last_turn(session_id)

    assert undone["phase"] == "opening"
    assert len(undone["move_history"]) == 18
    assert undone["training_progress"]["current"] == 10
    assert coach.store.get_session_summary(session_id) is None
