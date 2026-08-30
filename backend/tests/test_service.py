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

    def get_best_move(self, board: chess.Board) -> tuple[chess.Move, MoveAnalysis]:
        move = next(iter(board.legal_moves))
        return move, self.analyze_move(board, move)


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
    assert suggestion["basis"] == "theory"
    assert suggestion["move_uci"] in {
        move.uci for move in coach.openings.theory_moves(unchanged.board)
    }
    assert suggestion["engine"]["loss_pawns"] < 0.40
    assert unchanged.board.fen() == session["fen"]
    assert unchanged.move_history == []
    assert unchanged.message_history == []
    assert coach.store.summary()["attempts"] == 0


def test_suggestion_falls_back_to_stockfish_after_local_theory_ends() -> None:
    coach = service()
    coach.openings.moves.clear()
    session = coach.create_session("white")

    suggestion = coach.suggest_move(session["session_id"])
    unchanged = coach.sessions[session["session_id"]]

    assert suggestion["basis"] == "engine"
    assert suggestion["move_uci"] in session["legal_moves"]
    assert suggestion["move_uci"] == suggestion["engine"]["best_move_uci"]
    assert "Stockfish bevorzugt" in suggestion["summary"]
    assert unchanged.board.fen() == session["fen"]
    assert unchanged.move_history == []
    assert coach.store.summary()["attempts"] == 0


def test_pawn_feedback_explains_irreversible_square_changes_concretely() -> None:
    coach = service()
    session = coach.create_session("white")

    response = coach.play_learner_move(session["session_id"], "c2", "c3")
    feedback = response["messages"][0]

    assert "b4 und d4" in feedback["details"]
    assert "b3 und d3" in feedback["details"]
    assert "nicht rückwärts" in feedback["details"]
    assert "Springer" in feedback["details"]
    assert feedback["details"] != feedback["summary"]


def test_feedback_explains_when_a_move_ignores_an_attacked_piece() -> None:
    coach = service()
    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6"):
        board.push_san(san)
    coach.openings.moves.clear()
    session = coach.create_session("white")
    active = coach.sessions[session["session_id"]]
    active.board = board

    class AttackedBishopEngine(FakeEngine):
        def analyze_move(self, board: chess.Board, move: chess.Move) -> MoveAnalysis:
            if board.turn == chess.BLACK:
                return super().analyze_move(board, move)
            best = board.parse_san("Ba4")
            return MoveAnalysis(
                available=True,
                engine_name=self.name,
                best_move_uci=best.uci(),
                best_move_san="Ba4",
                evaluation_before=0.2,
                evaluation_played=-0.45,
                mate_before=None,
                mate_played=None,
                loss_pawns=0.65,
                classification="inaccuracy",
                best_pv_san=("Ba4", "Nf6", "O-O"),
                played_pv_san=(board.san(move), "axb5"),
            )

    coach.engine = AttackedBishopEngine()
    response = coach.play_learner_move(session["session_id"], "c2", "c3")
    feedback = response["messages"][0]

    assert "Läufer auf b5 angegriffen" in feedback["details"]
    assert "c3 lässt diesen Angriff bestehen" in feedback["details"]
    assert "Ba4 bringt den Läufer aus dem Angriff" in feedback["details"]
    assert "konkreten Rechenweg" in feedback["details"]


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
