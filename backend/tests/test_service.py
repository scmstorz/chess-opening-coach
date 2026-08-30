import random

import chess
from chess_coach.engine import CandidateAnalysis, MoveAnalysis, MoveComparison
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

    def compare_moves(
        self, board: chess.Board, *, count: int = 3, focus_move: chess.Move | None = None
    ) -> MoveComparison:
        candidates = []
        for index, move in enumerate(list(board.legal_moves)[:count]):
            candidates.append(
                CandidateAnalysis(
                    move_uci=move.uci(),
                    move_san=board.san(move),
                    evaluation=round(0.2 - index * 0.1, 2),
                    mate=None,
                    loss_pawns=round(index * 0.1, 2),
                    pv_san=(board.san(move),),
                )
            )
        if focus_move and all(candidate.move_uci != focus_move.uci() for candidate in candidates):
            candidates.append(
                CandidateAnalysis(
                    move_uci=focus_move.uci(),
                    move_san=board.san(focus_move),
                    evaluation=-0.5,
                    mate=None,
                    loss_pawns=0.7,
                    pv_san=(board.san(focus_move),),
                )
            )
        return MoveComparison(True, self.name, tuple(candidates))


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


def test_na2_question_corrects_the_generic_center_development_template() -> None:
    coach = service()
    session = coach.create_session("white")
    active = coach.sessions[session["session_id"]]
    active.board = chess.Board(
        "r1b2rk1/p3nppp/2pq1n2/1p2p1B1/Pb1pP2N/1BNP1Q2/1PP2PPP/R4RK1 w - - 0 13"
    )
    coach.openings.moves.clear()

    class Na2Engine(FakeEngine):
        def analyze_move(self, board: chess.Board, move: chess.Move) -> MoveAnalysis:
            best = chess.Move.from_uci("c3a2")
            return MoveAnalysis(
                available=True,
                engine_name=self.name,
                best_move_uci=best.uci(),
                best_move_san="Na2",
                evaluation_before=0.43,
                evaluation_played=0.43,
                mate_before=None,
                mate_played=None,
                loss_pawns=0.0,
                classification="practically_equal",
                best_pv_san=("Na2", "Bc5", "Nc1", "a5"),
                played_pv_san=("Na2", "Bc5", "Nc1", "a5"),
            )

        def compare_moves(
            self, board: chess.Board, *, count: int = 3, focus_move: chess.Move | None = None
        ) -> MoveComparison:
            candidates = (
                CandidateAnalysis(
                    "c3a2",
                    "Na2",
                    0.43,
                    None,
                    0.0,
                    ("Na2", "Bc5", "Nc1", "a5"),
                ),
                CandidateAnalysis(
                    "c3b1",
                    "Nb1",
                    -0.06,
                    None,
                    0.49,
                    ("Nb1", "a5", "c3", "Bc5"),
                ),
                CandidateAnalysis(
                    "c3d1",
                    "Nd1",
                    -0.34,
                    None,
                    0.77,
                    ("Nd1",),
                ),
            )
            return MoveComparison(True, self.name, candidates[:count])

    coach.engine = Na2Engine()
    response = coach.answer_question(
        session["session_id"],
        "Warum ist Na2 gut, obwohl ein Springer am Rand schlecht steht?",
        "c3a2",
    )
    details = response["message"]["details"]

    assert "Springer auf c3" in details
    assert "Bauern auf d4 angegriffen" in details
    assert "Na2 bringt den Springer aus diesem Angriff" in details
    assert "kontrolliert von dort c1, c3 und b4" in details
    assert "Keines davon ist eines der vier Zentrumsfelder" in details
    assert "greift er den gegnerischen Läufer auf b4 an" in details
    assert "Dein Einwand zur Faustregel „Springer am Rand“ ist richtig" in details
    assert "kein aktiver Zentrumszug" in details
    assert "Bc5 zieht den von Na2 angegriffenen Läufer von b4 weg" in details
    assert "Zwischenstation und kein dauerhafter Posten" in details
    assert "nächster Kandidat ist Nb1" in details
    assert "um 0,49 Bauerneinheiten schwächer" in details
    assert "Nur Na2 erzeugt zugleich einen direkten Gegenangriff" in details
    assert "entwickelt" not in details
    sections = response["message"]["explanation_sections"]
    assert [section["title"] for section in sections] == [
        "Was verändert der Zug konkret?",
        "Warum nicht die naheliegende Alternative?",
        "Stockfish-Rechenwege",
    ]
    assert "Nb1 (-0,06, 0,49 Bauerneinheiten hinter Platz 1)" in sections[2]["text"]


def test_question_uses_the_first_of_multiple_named_legal_moves() -> None:
    coach = service()
    board = chess.Board("3r1rk1/ppp2ppp/3q1n2/1B2p3/2Pn4/3P3P/P1P2PP1/R1BQR1K1 w - - 3 14")

    first = coach._mentioned_legal_move(board, "Warum ist c3 schlechter als Ba4?")
    reversed_order = coach._mentioned_legal_move(board, "Warum ist Ba4 besser als c3?")

    assert first == chess.Move.from_uci("c2c3")
    assert reversed_order == chess.Move.from_uci("b5a4")


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
