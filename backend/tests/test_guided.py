import json
import random
from pathlib import Path

import chess
import pytest
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
    lesson_book = GuidedLessonBook(REPERTOIRE_PATH)
    lesson = lesson_book.get(ITALIAN_WHITE_LESSON_ID)

    assert len(lesson_book.lessons) == 13
    assert sum(item.realistic_weight for item in lesson_book.lessons.values()) == 100
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
    assert all(
        lesson_book.first_divergence_ply(item) == item.drill_start_ply - 1
        for item in lesson_book.lessons.values()
        if item.lesson_id != ITALIAN_WHITE_LESSON_ID
    )
    active_italian = [
        item
        for item in lesson_book.lessons.values()
        if item.family == "italian-white" and item.realistic_weight > 0
    ]
    assert len(active_italian) == 7
    assert all(
        [move.move_san for move in item.moves[:5]] == ["e4", "e5", "Nf3", "Nc6", "Bc4"]
        for item in active_italian
    )
    assert all(
        item.lesson_id == ITALIAN_WHITE_LESSON_ID or item.drill_start_ply >= 6
        for item in active_italian
    )


def test_branch_drill_starts_after_deviation_without_revealing_answer() -> None:
    coach = guided_service()

    response = coach.create_session(
        "white",
        training_mode="guided",
        lesson_style="branches",
        lesson_id="italian-white-two-knights",
    )

    assert response["lesson_style"] == "branches"
    assert response["context_history"] == [
        {"actor": "learner", "san": "e4"},
        {"actor": "coach", "san": "e5"},
        {"actor": "learner", "san": "Nf3"},
        {"actor": "coach", "san": "Nc6"},
        {"actor": "learner", "san": "Bc4"},
        {"actor": "coach", "san": "Nf6"},
    ]
    assert response["move_history"] == []
    assert response["opening"]["name"] == "Italian Game: Two Knights Defense"
    assert response["training_progress"]["total"] == 3
    assert response["training_progress"]["completed"] == 0
    assert response["messages"][0]["summary"] == (
        "Schwarz hat zuletzt Nf6 gespielt. Was spielst du jetzt?"
    )
    assert "d3" not in json.dumps(response["messages"], ensure_ascii=False)

    suggestion = coach.suggest_move(response["session_id"])
    assert suggestion["move_san"] == "d3"


def test_realistic_opponent_hides_selected_line_until_italian_deviation() -> None:
    coach = guided_service()
    response = coach.create_session(
        "white",
        training_mode="guided",
        lesson_style="realistic",
        lesson_id="italian-white-two-knights",
    )

    assert response["lesson"]["lesson_id"] == "hidden-opponent-line"
    assert response["lesson"]["title"] == "Realistischer Gegner"
    assert response["training_progress"]["total"] == 10
    assert response["context_history"] == []
    assert "im Italienischen Spiel" in response["messages"][0]["summary"]
    assert "Sizilian" not in json.dumps(response, ensure_ascii=False)

    after_e4 = coach.play_learner_move(response["session_id"], "e2", "e4")
    after_nf3 = coach.play_learner_move(response["session_id"], "g1", "f3")

    assert after_e4["messages"][1]["move"] == "e5"
    assert after_e4["lesson"]["lesson_id"] == "hidden-opponent-line"
    assert after_nf3["messages"][1]["move"] == "Nc6"
    assert after_nf3["lesson"]["lesson_id"] == "hidden-opponent-line"

    played = coach.play_learner_move(response["session_id"], "f1", "c4")

    assert played["messages"][1]["move"] == "Nf6"
    assert "Zweispringer-Verteidigung" in played["messages"][1]["summary"]
    assert played["lesson"]["lesson_id"] == "italian-white-two-knights"
    assert played["lesson"]["title"] == "Italienisch gegen die Zweispringer-Verteidigung"
    assert played["opening"]["name"] == "Italian Game"


def test_realistic_opponent_does_not_reveal_a_later_deviation_early() -> None:
    coach = guided_service()
    response = coach.create_session(
        "white",
        training_mode="guided",
        lesson_style="realistic",
        lesson_id="italian-white-slow-h6",
    )

    coach.play_learner_move(response["session_id"], "e2", "e4")
    coach.play_learner_move(response["session_id"], "g1", "f3")
    after_bc4 = coach.play_learner_move(response["session_id"], "f1", "c4")

    assert after_bc4["messages"][1]["move"] == "Bc5"
    assert after_bc4["lesson"]["lesson_id"] == "hidden-opponent-line"
    assert after_bc4["lesson"]["title"] == "Realistischer Gegner"
    assert "h6" not in json.dumps(after_bc4["lesson"], ensure_ascii=False)

    after_d3 = coach.play_learner_move(response["session_id"], "d2", "d3")

    assert after_d3["messages"][1]["move"] == "h6"
    assert after_d3["lesson"]["lesson_id"] == "italian-white-slow-h6"


def test_realistic_selector_uses_multiple_curated_opponent_lines() -> None:
    lesson_book = GuidedLessonBook(REPERTOIRE_PATH)
    rng = random.Random(12)

    selected = {lesson_book.select("realistic", rng).lesson_id for _ in range(1_000)}

    assert selected == {
        ITALIAN_WHITE_LESSON_ID,
        "italian-white-two-knights",
        "italian-white-hungarian",
        "italian-white-rousseau",
        "italian-white-blackburne-shilling",
        "italian-white-slow-h6",
        "italian-white-slow-a6",
    }


def test_other_first_move_openings_are_retained_but_not_selected_for_italian() -> None:
    lesson_book = GuidedLessonBook(REPERTOIRE_PATH)
    coach = guided_service()

    assert lesson_book.get("italian-white-vs-sicilian").family == "e4-white-foundations"
    assert lesson_book.get("italian-white-vs-sicilian").realistic_weight == 0

    with pytest.raises(ValueError, match="gehört nicht zum Italienisch-Training"):
        coach.create_session(
            "white",
            training_mode="guided",
            lesson_style="branches",
            lesson_id="italian-white-vs-sicilian",
        )


def test_branch_drill_can_end_on_learner_move_and_reopen_with_undo() -> None:
    coach = guided_service()
    session = coach.create_session(
        "white",
        training_mode="guided",
        lesson_style="branches",
        lesson_id="italian-white-hungarian",
    )

    coach.play_learner_move(session["session_id"], "d2", "d4")
    completed = coach.play_learner_move(session["session_id"], "d4", "d5")

    assert completed["phase"] == "complete"
    assert completed["move_history"][-1] == {"actor": "learner", "san": "d5"}
    assert completed["messages"][0]["move"] == "d5"
    assert completed["messages"][-1]["kind"] == "summary"
    assert all(message.get("move") != "Nb8" for message in completed["messages"])
    assert coach.store.session_interactions(session["session_id"])[0]["lesson_style"] == (
        "branches"
    )

    reopened = coach.undo_last_turn(session["session_id"])

    assert reopened["phase"] == "opening"
    assert reopened["move_history"][-2:] == [
        {"actor": "learner", "san": "d4"},
        {"actor": "coach", "san": "d6"},
    ]
    assert reopened["context_history"][-1]["san"] == "Be7"
    assert reopened["training_progress"]["current"] == 2


def test_branch_historical_question_replays_from_drill_start_position() -> None:
    coach = guided_service()
    session = coach.create_session(
        "white",
        training_mode="guided",
        lesson_style="branches",
        lesson_id="italian-white-two-knights",
    )
    coach.play_learner_move(session["session_id"], "d2", "d3")

    answer = coach.answer_question(
        session["session_id"], "Warum war mein letzter Zug d3 gut?"
    )["message"]

    assert answer["move"] == "d3"
    assert answer["summary"].startswith("Du stützt e4")
    assert answer["position_fen"] == session["fen"]


def test_guided_session_asks_immediately_without_revealing_the_move() -> None:
    coach = guided_service()

    response = coach.create_session("random", training_mode="guided")

    assert response["training_mode"] == "guided"
    assert response["learner_color"] == "white"
    assert response["move_history"] == []
    assert response["messages"][0]["kind"] == "prompt"
    assert response["messages"][0]["summary"] == "Du spielst Weiß. Was ist dein erster Zug?"
    visible_prompt = " ".join(
        f"{message['summary']} {message['details']}" for message in response["messages"]
    )
    assert "e4" not in visible_prompt
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


def test_guided_style_is_part_of_the_public_session_api() -> None:
    coach = guided_service()

    with TestClient(create_app(coach)) as client:
        branch = client.post(
            "/api/sessions",
            json={
                "color": "white",
                "training_mode": "guided",
                "lesson_style": "branches",
                "lesson_id": "italian-white-two-knights",
            },
        )
        invalid = client.post(
            "/api/sessions",
            json={
                "color": "white",
                "training_mode": "guided",
                "lesson_style": "surprise-me",
            },
        )

    assert branch.status_code == 200
    assert branch.json()["lesson_style"] == "branches"
    assert branch.json()["context_history"][-1]["san"] == "Nf6"
    assert invalid.status_code == 422


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
