import random

import chess
from chess_coach.engine import MoveAnalysis
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor


class FakeEngine:
    available = True
    executable = "fake-stockfish"
    name = "Fake Stockfish"

    def analyze_move(self, board: chess.Board, move: chess.Move) -> MoveAnalysis:
        bad = move.uci() == "f2f3"
        best = next(iter(board.legal_moves))
        return MoveAnalysis(
            available=True,
            engine_name=self.name,
            best_move_uci=best.uci(),
            best_move_san=board.san(best),
            evaluation_before=0.2,
            evaluation_played=-1.0 if bad else 0.2,
            mate_before=None,
            mate_played=None,
            loss_pawns=1.2 if bad else 0.0,
            classification="mistake" if bad else "practically_equal",
            best_pv_san=(board.san(best),),
            played_pv_san=(board.san(move),),
        )

    def close(self) -> None:
        pass


def service() -> CoachService:
    return CoachService(
        OpeningBook(),
        FakeEngine(),
        OllamaTutor("http://127.0.0.1:1", timeout=0.01),
        SQLiteStore(":memory:"),
        rng=random.Random(4),
    )


def test_complete_white_turn_keeps_truth_layers_separate() -> None:
    coach = service()
    session = coach.create_session("white")
    initial_fen = session["fen"]

    response = coach.play_learner_move(session["session_id"], "e2", "e4")

    assert len(response["move_history"]) == 2
    assert response["messages"][0]["actor"] == "learner"
    assert response["messages"][1]["actor"] == "coach"
    assert response["messages"][0]["move_uci"] == "e2e4"
    assert response["messages"][0]["fen_after"].split()[1] == "b"
    assert response["messages"][1]["move_uci"]
    assert response["messages"][1]["fen_after"] == response["fen"]
    assert response["message_history"] == response["messages"]
    assert response["can_undo"] is True
    assert response["correction"] is None
    assert response["opening"] is not None

    undone = coach.undo_last_turn(session["session_id"])

    assert undone["fen"] == initial_fen
    assert undone["move_history"] == []
    assert undone["message_history"] == []
    assert undone["can_undo"] is False
    assert undone["undo"] == {"removed_moves": 2, "removed_messages": 2}
    assert coach.store.summary()["attempts"] == 0


def test_material_mistake_starts_three_attempt_correction_loop() -> None:
    coach = service()
    session = coach.create_session("white")

    first = coach.play_learner_move(session["session_id"], "f2", "f3")
    second = coach.play_learner_move(session["session_id"], "f2", "f3")
    third = coach.play_learner_move(session["session_id"], "f2", "f3")

    assert first["correction"]["attempt"] == 1
    assert second["correction"]["attempt"] == 2
    assert third["correction"] is None
    assert len(third["move_history"]) == 2


def test_suggestion_is_theory_grounded_and_does_not_change_the_session() -> None:
    coach = service()
    session = coach.create_session("white")

    suggestion = coach.suggest_move(session["session_id"])
    unchanged = coach.sessions[session["session_id"]]

    assert suggestion["move_uci"] in session["legal_moves"]
    assert suggestion["move_uci"] in {
        move.uci for move in coach.openings.theory_moves(unchanged.board)
    }
    assert suggestion["engine"]["loss_pawns"] < 0.40
    assert unchanged.board.fen() == session["fen"]
    assert unchanged.move_history == []
    assert unchanged.message_history == []
    assert coach.store.summary()["attempts"] == 0


def test_question_about_suggestion_is_grounded_without_playing_the_move() -> None:
    coach = service()
    session = coach.create_session("white")
    suggestion = coach.suggest_move(session["session_id"])

    response = coach.answer_question(
        session["session_id"],
        "Warum ist dieser Zug gut?",
        suggestion["move_uci"],
    )
    unchanged = coach.sessions[session["session_id"]]

    assert response["message"]["kind"] == "question"
    assert response["message"]["question"] == "Warum ist dieser Zug gut?"
    assert response["message"]["move"] == suggestion["move_san"]
    assert response["message"]["source"] == "deterministic"
    assert response["message"]["engine"]["loss_pawns"] < 0.40
    assert unchanged.board.fen() == session["fen"]
    assert unchanged.move_history == []
    assert unchanged.message_history == response["message_history"]
    assert coach.store.summary()["attempts"] == 0

    alternative = coach.answer_question(
        session["session_id"],
        "Warum nicht d4?",
        suggestion["move_uci"],
    )

    assert alternative["message"]["move"] == "d4"
