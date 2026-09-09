import random

import chess
from chess_coach.engine import (
    CandidateAnalysis,
    MoveAnalysis,
    MoveComparison,
    MovePlanAnalysis,
    PlanBranch,
)
from chess_coach.openings import OpeningBook, OpeningIdentity
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
        self,
        board: chess.Board,
        *,
        count: int = 3,
        focus_move: chess.Move | None = None,
        required_moves: tuple[chess.Move, ...] = (),
        stable: bool = False,
        deep: bool = False,
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
        requested = tuple(move for move in (focus_move, *required_moves) if move)
        for requested_move in requested:
            if any(candidate.move_uci == requested_move.uci() for candidate in candidates):
                continue
            candidates.append(
                CandidateAnalysis(
                    move_uci=requested_move.uci(),
                    move_san=board.san(requested_move),
                    evaluation=0.1,
                    mate=None,
                    loss_pawns=0.1,
                    pv_san=(board.san(requested_move),),
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


def opening_end_session(coach: CoachService) -> tuple[str, chess.Board]:
    response = coach.create_session("white")
    session_id = response["session_id"]
    active = coach.sessions[session_id]
    board = chess.Board()
    moves = ("e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "O-O", "Nf6", "d3", "O-O", "c3", "d6")
    active.move_history = []
    for index, san in enumerate(moves):
        fen_before = board.fen()
        move = board.parse_san(san)
        actor = "learner" if index % 2 == 0 else "coach"
        coach.store.record(
            {
                "session_id": session_id,
                "fen_before": fen_before,
                "actor": actor,
                "move_uci": move.uci(),
                "move_san": san,
                "legal": 1,
                "accepted": 1,
                "theory_match": 1 if index < 6 else 0,
                "opening_eco": "C50",
                "opening_name": "Italian Game",
                "engine_evaluation": 0.2,
                "engine_loss": 0.0,
                "engine_classification": "practically_equal",
                "attempt_number": 0,
                "feedback_summary": "Test feedback",
                "llm_model": None,
            }
        )
        board.push(move)
        active.move_history.append({"actor": actor, "san": san})
    active.board = board
    active.opening = OpeningIdentity("C50", "Italian Game")
    return session_id, board


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


def test_bb5_question_explains_pressure_on_the_e5_defender() -> None:
    coach = service()
    response = coach.create_session("white")
    active = coach.sessions[response["session_id"]]
    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6"):
        board.push_san(san)
    active.board = board
    active.opening = OpeningIdentity("C60", "Ruy Lopez")

    message = coach.answer_question(
        response["session_id"], "Warum ist Bb5 gut?", "f1b5"
    )["message"]

    assert "Springer auf c6" in message["details"]
    assert "Bauern auf e5" in message["details"]
    assert "gewinnt ihn aber nicht automatisch" in message["details"]


def test_pawn_feedback_omits_trivial_irreversibility_template() -> None:
    coach = service()
    session = coach.create_session("white")

    response = coach.play_learner_move(session["session_id"], "c2", "c3")
    feedback = response["messages"][0]

    assert "b4 und d4" in feedback["details"]
    assert "b3 und d3" not in feedback["details"]
    assert "nicht rückwärts" not in feedback["details"]
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
            self,
            board: chess.Board,
            *,
            count: int = 3,
            focus_move: chess.Move | None = None,
            required_moves: tuple[chess.Move, ...] = (),
        ) -> MoveComparison:
            del board, focus_move, required_moves
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
    assert "Keines davon ist eines der vier Zentrumsfelder" not in details
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
        "Mittel- und langfristiger Plan",
        "Konkrete Wirkung in der Stellung",
        "Vergleich mit der besten Alternative",
        "Stockfish-Rechenwege",
    ]
    assert "Nb1 (-0,06, 0,49 Bauerneinheiten hinter Platz 1)" in sections[3]["text"]


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


def test_deep_question_marks_mode_and_adds_cross_line_plan_section() -> None:
    coach = service()
    class PlanEngine(FakeEngine):
        def analyze_plan_branches(
            self, board: chess.Board, focus_move: chess.Move, *, reply_count: int = 3
        ) -> MovePlanAnalysis:
            del board, reply_count
            return MovePlanAnalysis(
                True,
                self.name,
                focus_move.uci(),
                "e4",
                (
                    PlanBranch("c7c5", "c5", 0.2, None, ("e4", "c5", "Nf3")),
                    PlanBranch("e7e5", "e5", 0.2, None, ("e4", "e5", "Nf3")),
                    PlanBranch("e7e6", "e6", 0.2, None, ("e4", "e6", "d4")),
                ),
            )

    coach.engine = PlanEngine()
    session = coach.create_session("white")

    response = coach.answer_question(
        session["session_id"],
        "Warum ist e4 mittel- und langfristig gut?",
        "e2e4",
        deep=True,
    )

    message = response["message"]
    assert message["analysis_mode"] == "deep"
    assert [section["title"] for section in message["explanation_sections"]] == [
        "Mittel- und langfristiger Plan",
        "Was gegen mehrere Antworten stabil bleibt",
        "Konkrete Wirkung in der Stellung",
        "Vergleich mit der besten Alternative",
        "Stockfish-Rechenwege",
    ]
    stable = next(
        section["text"]
        for section in message["explanation_sections"]
        if section["title"] == "Was gegen mehrere Antworten stabil bleibt"
    )
    assert "Nf3 in 2 von 3 Varianten" in stable


def test_first_identified_opening_is_introduced_instead_of_continued() -> None:
    coach = service()
    response = coach.create_session("white")
    session = coach.sessions[response["session_id"]]
    session.board.push_san("e4")
    session.move_history.append({"actor": "learner", "san": "e4"})
    session.opening = OpeningIdentity("B00", "King's Pawn Game")
    move = session.board.parse_san("c5")
    analysis = coach.engine.analyze_move(session.board, move)

    message = coach._coach_message(
        session,
        move,
        "c5",
        True,
        analysis,
        OpeningIdentity("B20", "Sicilian Defense"),
    )

    assert message["summary"] == (
        "Ich spiele c5. Mit diesem Zug beginnt die Eröffnung „Sicilian Defense“."
    )
    assert "weiter" not in message["summary"]


def test_opening_end_combines_theory_development_castling_and_history() -> None:
    coach = service()
    session_id, _ = opening_end_session(coach)
    active = coach.sessions[session_id]

    evidence = coach._opening_end_evidence(active)

    assert evidence.likely is True
    assert evidence.can_continue is True
    assert "wahrscheinlich vorbei" in evidence.headline
    assert {signal["id"] for signal in evidence.signals if signal["met"]} >= {
        "theory",
        "development",
        "king_safety",
        "move_count",
    }


def test_early_theory_departure_does_not_end_opening_by_itself() -> None:
    coach = service()
    response = coach.create_session("white")
    active = coach.sessions[response["session_id"]]
    active.board.push_san("e4")
    active.board.push_san("a6")
    active.move_history = [
        {"actor": "learner", "san": "e4"},
        {"actor": "coach", "san": "a6"},
    ]

    evidence = coach._opening_end_evidence(active)

    assert evidence.likely is False
    assert next(signal for signal in evidence.signals if signal["id"] == "theory")["met"]
    assert not next(signal for signal in evidence.signals if signal["id"] == "move_count")["met"]


def test_opening_transition_pauses_until_learner_continues() -> None:
    coach = service()
    session_id, _ = opening_end_session(coach)
    active = coach.sessions[session_id]
    active.phase = "transition"
    active.opening_end = coach._opening_end_evidence(active)

    continued = coach.continue_after_opening(session_id)

    assert continued["phase"] == "middlegame"
    assert continued["opening_end"] is None
    assert continued["messages"][0]["kind"] == "phase"
    assert "Mittelspiel" in continued["messages"][0]["summary"]

    learner_move = next(iter(active.board.legal_moves))
    next_turn = coach.play_learner_move(
        session_id,
        chess.square_name(learner_move.from_square),
        chess.square_name(learner_move.to_square),
    )

    assert "Stockfish bevorzugt" in next_turn["messages"][1]["summary"]
    assert coach.store.session_interactions(session_id)[-1]["theory_match"] == 0


def test_completed_turn_adds_opening_end_notice_to_response() -> None:
    coach = service()
    session_id, board = opening_end_session(coach)
    active = coach.sessions[session_id]
    last_move = chess.Move.from_uci("d7d6")
    coach_message = {
        "actor": "coach",
        "move": "d6",
        "move_uci": last_move.uci(),
        "fen_after": board.fen(),
        "summary": "Der Coach hat d6 gespielt.",
        "details": "Test.",
        "source": "deterministic",
        "model": None,
        "attempt": None,
        "engine": None,
    }

    response = coach._response(active, messages=[coach_message])

    assert response["phase"] == "transition"
    assert response["opening_end"]["likely"] is True
    assert response["messages"][-1]["kind"] == "phase"
    assert response["message_history"][-1]["kind"] == "phase"


def test_opening_summary_is_grounded_and_persisted() -> None:
    coach = service()
    session_id, board = opening_end_session(coach)
    active = coach.sessions[session_id]
    coach.store.record(
        {
            "session_id": session_id,
            "fen_before": chess.Board().fen(),
            "actor": "learner",
            "move_uci": "f2f3",
            "move_san": "f3",
            "legal": 1,
            "accepted": 0,
            "theory_match": 0,
            "opening_eco": None,
            "opening_name": None,
            "engine_evaluation": -1.0,
            "engine_loss": 1.2,
            "engine_classification": "mistake",
            "attempt_number": 1,
            "feedback_summary": "Noch ein Versuch",
            "llm_model": None,
        }
    )
    active.phase = "transition"
    active.opening_end = coach._opening_end_evidence(active)

    response = coach.finish_opening(session_id)
    summary = response["opening_summary"]

    assert response["phase"] == "complete"
    assert response["fen"] == board.fen()
    assert summary["opening"] == {"eco": "C50", "name": "Italian Game"}
    assert summary["source"] == "verified-session-data"
    assert summary["concepts"] == [
        "Zentrum: Beide eigenen d- und e-Bauern haben ihre Ausgangsfelder verlassen.",
        (
            "Entwicklung: 2 von 4 eigenen Springern und Läufern wurden mindestens einmal von "
            "ihrem Ausgangsfeld gezogen."
        ),
        "Königssicherheit: Du hast in der Eröffnungsphase rochiert.",
    ]
    assert any("f3" in point and "1,20" in point for point in summary["review_points"])
    assert summary["recommendation"]["title"] == "Stellung vor f3 noch einmal üben"
    assert coach.store.get_session_summary(session_id) == summary
    assert coach.store.summary()["sessions_reviewed"] == 1
