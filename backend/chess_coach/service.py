from __future__ import annotations

import random
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import chess

from chess_coach.engine import CandidateAnalysis, MoveAnalysis, MoveComparison, StockfishService
from chess_coach.openings import OpeningBook, OpeningIdentity, TheoryMove
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor, TutorText


@dataclass(slots=True)
class TurnSnapshot:
    fen: str
    opening: OpeningIdentity | None
    move_history_length: int
    message_history_length: int
    interaction_id: int | None


@dataclass(slots=True)
class GameSession:
    session_id: str
    board: chess.Board
    learner_color: chess.Color
    opening: OpeningIdentity | None = None
    move_history: list[dict[str, str]] = field(default_factory=list)
    message_history: list[dict[str, Any]] = field(default_factory=list)
    undo_stack: list[TurnSnapshot] = field(default_factory=list)
    attempts_at_position: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


class CoachService:
    correction_threshold = 0.75

    def __init__(
        self,
        opening_book: OpeningBook,
        engine: StockfishService,
        tutor: OllamaTutor,
        store: SQLiteStore,
        *,
        rng: random.Random | None = None,
    ) -> None:
        self.openings = opening_book
        self.engine = engine
        self.tutor = tutor
        self.store = store
        self.rng = rng or random.Random()
        self.sessions: dict[str, GameSession] = {}

    def create_session(self, requested_color: str) -> dict[str, Any]:
        if requested_color == "random":
            requested_color = self.rng.choice(["white", "black"])
        learner_color = chess.WHITE if requested_color == "white" else chess.BLACK
        session = GameSession(
            session_id=str(uuid.uuid4()),
            board=chess.Board(),
            learner_color=learner_color,
        )
        self.sessions[session.session_id] = session
        messages: list[dict[str, Any]] = []
        if learner_color == chess.BLACK:
            messages.append(self._play_coach_move(session))
        return self._response(session, messages=messages)

    def play_learner_move(
        self, session_id: str, from_square: str, to_square: str, promotion: str | None = None
    ) -> dict[str, Any]:
        session = self._session(session_id)
        with session.lock:
            if session.board.turn != session.learner_color:
                raise ValueError("Der Coach ist am Zug")
            fen_before = session.board.fen()
            move = self._parse_move(session.board, from_square, to_square, promotion)
            if move not in session.board.legal_moves:
                session.attempts_at_position += 1
                message = self._illegal_message(session.attempts_at_position)
                self._record(
                    session, fen_before, "learner", None, False, False, None, None, message
                )
                return self._response(
                    session,
                    messages=[message],
                    correction=self._correction(session, None),
                )

            san = session.board.san(move)
            theory_moves = self.openings.theory_moves(session.board)
            theory_match = move.uci() in {candidate.uci for candidate in theory_moves}
            analysis = self.engine.analyze_move(session.board, move)
            needs_correction = bool(
                analysis.available
                and analysis.loss_pawns is not None
                and analysis.loss_pawns >= self.correction_threshold
            )

            if needs_correction:
                session.attempts_at_position += 1
                if session.attempts_at_position < 3:
                    message = self._mistake_message(
                        session, move, san, theory_match, analysis, session.attempts_at_position
                    )
                    self._record(
                        session,
                        fen_before,
                        "learner",
                        move,
                        True,
                        False,
                        theory_match,
                        analysis,
                        message,
                    )
                    return self._response(
                        session,
                        messages=[message],
                        correction=self._correction(session, analysis),
                    )

                recommended = chess.Move.from_uci(analysis.best_move_uci or move.uci())
                recommended_san = session.board.san(recommended)
                message = self._solution_message(session, san, recommended_san, analysis)
                self._save_turn_snapshot(session)
                session.board.push(recommended)
                self._attach_transition(message, recommended, session.board)
                session.move_history.append({"actor": "learner", "san": recommended_san})
                session.opening = self.openings.identify(session.board, session.opening)
                self._record(
                    session,
                    fen_before,
                    "learner",
                    recommended,
                    True,
                    True,
                    recommended.uci() in {candidate.uci for candidate in theory_moves},
                    analysis,
                    message,
                )
                session.attempts_at_position = 0
                messages = [message]
                if not session.board.is_game_over():
                    messages.append(self._play_coach_move(session))
                return self._response(session, messages=messages)

            projected = session.board.copy(stack=False)
            projected.push(move)
            next_opening = self.openings.identify(projected, session.opening)
            message = self._accepted_message(
                session,
                move,
                san,
                theory_match,
                theory_moves,
                analysis,
                next_opening,
            )
            self._save_turn_snapshot(session)
            session.board.push(move)
            self._attach_transition(message, move, session.board)
            session.move_history.append({"actor": "learner", "san": san})
            session.opening = next_opening
            self._record(
                session, fen_before, "learner", move, True, True, theory_match, analysis, message
            )
            session.attempts_at_position = 0
            messages = [message]
            if not session.board.is_game_over():
                messages.append(self._play_coach_move(session))
            return self._response(session, messages=messages)

    def undo_last_turn(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        with session.lock:
            if not session.undo_stack:
                raise ValueError("Es gibt noch keinen vollständigen Zug zum Zurücknehmen")
            snapshot = session.undo_stack.pop()
            removed_moves = len(session.move_history) - snapshot.move_history_length
            removed_messages = len(session.message_history) - snapshot.message_history_length
            session.board = chess.Board(snapshot.fen)
            session.opening = snapshot.opening
            del session.move_history[snapshot.move_history_length :]
            del session.message_history[snapshot.message_history_length :]
            session.attempts_at_position = 0
            self.store.delete_interactions_after(session.session_id, snapshot.interaction_id)
            response = self._response(session, messages=[])
            response["undo"] = {
                "removed_moves": removed_moves,
                "removed_messages": removed_messages,
            }
            return response

    def suggest_move(self, session_id: str) -> dict[str, Any]:
        """Return a theory-first, engine-checked hint without changing the game."""
        session = self._session(session_id)
        with session.lock:
            if session.board.turn != session.learner_color:
                raise ValueError("Der Coach ist am Zug")

            move, analysis, basis, theory_move = self._select_suggestion(session.board)
            san = theory_move.san if theory_move else session.board.san(move)
            projected = session.board.copy(stack=False)
            projected.push(move)
            opening = self.openings.identify(projected, session.opening)
            if basis == "theory":
                opening_name = opening.name if opening else "den lokalen Eröffnungslinien"
                if analysis.available and analysis.loss_pawns is not None:
                    quality = (
                        "Stockfish bewertet ihn als objektiv stark."
                        if analysis.loss_pawns < 0.15
                        else "Stockfish bewertet ihn als gut spielbar."
                    )
                else:
                    quality = (
                        "Stockfish ist gerade nicht verfügbar; der Hinweis stammt aus der Theorie."
                    )
                summary = f"{san} ist ein bewährter Zug in {opening_name}. {quality}"
                source_detail = "Der Vorschlag stammt aus den lokalen Eröffnungslinien."
            else:
                summary = (
                    f"Stockfish bevorzugt {san} in dieser Stellung. "
                    "Die lokale Eröffnungstheorie enthält hier keine Fortsetzung mehr."
                )
                source_detail = (
                    "Der Vorschlag stammt deshalb direkt aus der aktuellen Engine-Analyse."
                )

            return {
                "move_uci": move.uci(),
                "move_san": san,
                "basis": basis,
                "opening": asdict(opening) if opening else None,
                "summary": summary,
                "details": (
                    f"{_move_concept(session.board, move)} "
                    f"{_move_response_context(session.board, move)} "
                    f"{_heuristic_context(session.board, move)} "
                    f"{_concrete_board_changes(session.board, move)} "
                    f"{_continuation_context(session.board, move, analysis)} "
                    f"{source_detail} "
                    "Der Zug wird nur auf dem Brett markiert; du spielst ihn selbst."
                ).replace("  ", " "),
                "engine": asdict(analysis),
            }

    def answer_question(
        self, session_id: str, question: str, focus_move_uci: str | None = None
    ) -> dict[str, Any]:
        """Answer a position question from verified theory and engine facts."""
        session = self._session(session_id)
        with session.lock:
            clean_question = question.strip()
            if not clean_question:
                raise ValueError("Bitte gib eine Frage ein")

            board = session.board
            move = self._mentioned_legal_move(board, clean_question)
            if move is None and focus_move_uci:
                try:
                    focused = chess.Move.from_uci(focus_move_uci)
                except (chess.InvalidMoveError, ValueError) as exc:
                    raise ValueError("Der Bezugszug ist ungültig") from exc
                if focused not in board.legal_moves:
                    raise ValueError("Der Bezugszug passt nicht mehr zur aktuellen Stellung")
                move = focused

            precomputed_analysis: MoveAnalysis | None = None
            if move is None:
                try:
                    move, precomputed_analysis, _, _ = self._select_suggestion(board)
                except ValueError:
                    move = None

            if move is None:
                fallback = TutorText(
                    summary=(
                        "Für diese Stellung enthalten die lokalen Eröffnungsdaten keinen weiteren "
                        "Zug, auf den ich die Frage sicher beziehen kann."
                    ),
                    details=(
                        "Ich möchte keine Begründung erfinden. Nenne einen konkreten legalen Zug "
                        "oder beginne eine neue Eröffnungsstellung."
                    ),
                    source="deterministic",
                    model=None,
                )
                text = fallback
                analysis = None
                san = None
                theory_match = False
                opening = session.opening
                explanation_sections: list[dict[str, str]] = []
            else:
                san = board.san(move)
                theory_moves = self.openings.theory_moves(board)
                theory_match = move.uci() in {candidate.uci for candidate in theory_moves}
                analysis = precomputed_analysis or self.engine.analyze_move(board, move)
                comparison = self.engine.compare_moves(board, count=3, focus_move=move)
                projected = board.copy(stack=False)
                projected.push(move)
                opening = self.openings.identify(projected, session.opening)
                fallback, answer_facts, explanation_sections = self._question_fallback(
                    board, san, move, theory_match, analysis, comparison, opening
                )
                facts = {
                    "task": "Beantworte die Rückfrage zur aktuellen Stellung.",
                    "user_question": clean_question,
                    "fen": board.fen(),
                    "side_to_move": "white" if board.turn == chess.WHITE else "black",
                    "focus_move": {"uci": move.uci(), "san": san},
                    "opening": asdict(opening) if opening else None,
                    "theory_match": theory_match,
                    "theory_moves": [candidate.san for candidate in theory_moves[:5]],
                    "engine": asdict(analysis),
                    "engine_comparison": asdict(comparison),
                    "answer_facts": answer_facts,
                }
                text = self.tutor.answer_question(facts, fallback)

            message = {
                "kind": "question",
                "actor": "coach",
                "question": clean_question,
                "move": san,
                "summary": text.summary,
                "details": text.details,
                "source": text.source,
                "model": text.model,
                "attempt": None,
                "engine": asdict(analysis) if analysis else None,
                "explanation_sections": explanation_sections,
            }
            session.message_history.append(message)
            return {"message": message, "message_history": session.message_history}

    def _select_theory_suggestion(self, board: chess.Board) -> tuple[TheoryMove, MoveAnalysis]:
        theory_moves = self.openings.theory_moves(board)
        if not theory_moves:
            raise ValueError(
                "Für diese Stellung ist kein Zug in der lokalen Eröffnungstheorie hinterlegt"
            )

        candidates: list[tuple[TheoryMove, MoveAnalysis]] = []
        for candidate in theory_moves[:5]:
            analysis = self.engine.analyze_move(board, chess.Move.from_uci(candidate.uci))
            candidates.append((candidate, analysis))
            if (
                analysis.available
                and analysis.loss_pawns is not None
                and analysis.loss_pawns < 0.40
            ):
                return candidate, analysis

        engine_candidates = [
            item for item in candidates if item[1].available and item[1].loss_pawns is not None
        ]
        return (
            min(engine_candidates, key=lambda item: item[1].loss_pawns)
            if engine_candidates
            else candidates[0]
        )

    def _select_suggestion(
        self, board: chess.Board
    ) -> tuple[chess.Move, MoveAnalysis, str, TheoryMove | None]:
        try:
            theory_move, analysis = self._select_theory_suggestion(board)
            return chess.Move.from_uci(theory_move.uci), analysis, "theory", theory_move
        except ValueError:
            move, analysis = self.engine.get_best_move(board)
            if move is None or not analysis.available:
                raise ValueError(
                    "Außerhalb der lokalen Eröffnungstheorie wird Stockfish für einen "
                    "verlässlichen Zugvorschlag benötigt"
                ) from None
            return move, analysis, "engine", None

    @staticmethod
    def _mentioned_legal_move(board: chess.Board, question: str) -> chess.Move | None:
        matches: list[tuple[int, chess.Move]] = []
        for move in board.legal_moves:
            san = board.san(move).rstrip("+#")
            if match := re.search(
                rf"(?<![A-Za-z0-9]){re.escape(san)}(?![A-Za-z0-9])", question, re.I
            ):
                matches.append((match.start(), move))
            if (uci_position := question.lower().find(move.uci().lower())) >= 0:
                matches.append((uci_position, move))
        return min(matches, key=lambda item: item[0])[1] if matches else None

    def _question_fallback(
        self,
        board: chess.Board,
        san: str,
        move: chess.Move,
        theory_match: bool,
        analysis: MoveAnalysis,
        comparison: MoveComparison,
        opening: OpeningIdentity | None,
    ) -> tuple[TutorText, list[dict[str, Any]], list[dict[str, str]]]:
        if theory_match:
            theory_text = "Der Zug ist in den lokalen Eröffnungslinien enthalten."
        else:
            theory_text = "Der Zug ist legal, aber nicht in den lokalen Eröffnungslinien enthalten."

        if analysis.available and analysis.loss_pawns is not None:
            if analysis.loss_pawns < 0.15:
                quality_text = "Stockfish sieht ihn praktisch auf Augenhöhe mit dem besten Zug."
            elif analysis.loss_pawns < 0.40:
                quality_text = "Stockfish sieht nur einen kleinen Unterschied zum besten Zug."
            else:
                quality_text = (
                    "Stockfish sieht einen spürbaren Nachteil gegenüber dem besten Zug "
                    f"{analysis.best_move_san}."
                )
        else:
            quality_text = "Stockfish ist gerade nicht verfügbar."

        opening_text = (
            f"Nach dem Zug ist die Stellung als {opening.name} eingeordnet. " if opening else ""
        )
        concept_text = _move_concept(board, move)
        response_text = _move_response_context(board, move)
        heuristic_text = _heuristic_context(board, move)
        board_changes_text = _concrete_board_changes(board, move)
        continuation_text = _continuation_context(board, move, analysis)
        contrast_text = _tactical_contrast(board, move, analysis)
        comparison_text = _candidate_comparison_text(board, move, analysis, comparison)
        engine_lines_text = _candidate_lines_text(move, analysis, comparison)
        pv_moves = " ".join(analysis.played_pv_san[:4])
        pv_text = f"Eine kurze Stockfish-Prüfvariante beginnt mit: {pv_moves}." if pv_moves else ""
        if (
            theory_match
            and analysis.available
            and analysis.loss_pawns is not None
            and analysis.loss_pawns < 0.15
        ):
            verdict_text = f"{san} ist hier ein bewährter und objektiv starker Zug."
        elif theory_match:
            verdict_text = f"{san} ist hier ein bewährter Eröffnungszug."
        elif analysis.available and analysis.best_move_uci == move.uci():
            verdict_text = f"Stockfish bevorzugt {san} in dieser Stellung."
        else:
            verdict_text = f"{san} ist hier eine legale Alternative."

        fact_values = (
            ("focus", f"Ich beziehe deine Frage auf {san}.", False),
            ("verdict", verdict_text, False),
            ("concept", concept_text, True),
            ("direct_threat", response_text, True),
            ("heuristic", heuristic_text, True),
            ("board_changes", board_changes_text, True),
            ("continuation", continuation_text, True),
            ("contrast", contrast_text, True),
            ("comparison", comparison_text, True),
            ("theory", theory_text, False),
            ("engine", quality_text, False),
            ("opening", opening_text.strip(), False),
            ("pv", pv_text, not engine_lines_text),
        )
        answer_facts = [
            {"id": fact_id, "text": text, "required": required}
            for fact_id, text, required in fact_values
            if text
        ]
        fallback = TutorText(
            summary=f"Ich beziehe deine Frage auf {san}. {verdict_text}",
            details=" ".join(
                part
                for part in (
                    response_text,
                    heuristic_text,
                    concept_text,
                    board_changes_text,
                    continuation_text,
                    contrast_text,
                    comparison_text,
                    theory_text,
                    quality_text,
                    pv_text,
                )
                if part
            ),
            source="deterministic",
            model=None,
        )
        concrete_text = " ".join(
            part
            for part in (
                response_text,
                heuristic_text,
                concept_text,
                board_changes_text,
                continuation_text,
                contrast_text,
            )
            if part
        )
        explanation_sections = [
            {"title": "Was verändert der Zug konkret?", "text": concrete_text},
            {
                "title": "Warum nicht die naheliegende Alternative?",
                "text": comparison_text
                or "Für einen belastbaren Alternativenvergleich fehlen Engine-Kandidaten.",
            },
            {
                "title": "Stockfish-Rechenwege",
                "text": engine_lines_text or pv_text or quality_text,
            },
        ]
        return fallback, answer_facts, explanation_sections

    def _play_coach_move(self, session: GameSession) -> dict[str, Any]:
        board = session.board
        fen_before = board.fen()
        theory_moves = self.openings.theory_moves(board)
        move = self._weighted_theory_move(theory_moves)
        if move is None:
            legal = list(board.legal_moves)
            move = self.rng.choice(legal)
        analysis = self.engine.analyze_move(board, move)
        if (
            analysis.available
            and analysis.loss_pawns is not None
            and analysis.loss_pawns >= 0.40
            and analysis.best_move_uci
        ):
            move = chess.Move.from_uci(analysis.best_move_uci)
            analysis = self.engine.analyze_move(board, move)
        san = board.san(move)
        theory_match = move.uci() in {candidate.uci for candidate in theory_moves}
        projected = board.copy(stack=False)
        projected.push(move)
        next_opening = self.openings.identify(projected, session.opening)
        message = self._coach_message(session, move, san, theory_match, analysis, next_opening)
        board.push(move)
        self._attach_transition(message, move, board)
        session.move_history.append({"actor": "coach", "san": san})
        session.opening = next_opening
        self._record(
            session, fen_before, "coach", move, True, True, theory_match, analysis, message
        )
        return message

    def _weighted_theory_move(self, moves: tuple[TheoryMove, ...]) -> chess.Move | None:
        if not moves:
            return None
        selected = self.rng.choices(moves, weights=[max(1, move.weight) for move in moves], k=1)[0]
        return chess.Move.from_uci(selected.uci)

    def _accepted_message(
        self,
        session: GameSession,
        move: chess.Move,
        san: str,
        theory_match: bool,
        theory_moves: tuple[TheoryMove, ...],
        analysis: MoveAnalysis,
        opening_after: OpeningIdentity | None,
    ) -> dict[str, Any]:
        if theory_match and analysis.classification == "practically_equal":
            verdict = f"{san} ist theoretisch etabliert und objektiv stark."
        elif theory_match:
            verdict = f"{san} gehört zur Eröffnungstheorie."
        elif analysis.classification in {"practically_equal", "slight_inaccuracy"}:
            alternatives = ", ".join(move.san for move in theory_moves[:2])
            verdict = (
                f"{san} ist spielbar, aber ungewöhnlich. Häufiger ist {alternatives}."
                if alternatives
                else f"{san} ist spielbar."
            )
        else:
            verdict = f"{san} ist legal, bringt aber eine kleine praktische Ungenauigkeit mit."
        fallback = TutorText(
            summary=verdict,
            details=self._move_details(session.board, move, analysis),
            source="deterministic",
            model=None,
        )
        facts = self._grounded(session, "learner", san, theory_match, analysis, opening_after)
        return self._message("learner", san, facts, fallback)

    def _coach_message(
        self,
        session: GameSession,
        move: chess.Move,
        san: str,
        theory_match: bool,
        analysis: MoveAnalysis,
        opening_after: OpeningIdentity | None,
    ) -> dict[str, Any]:
        opening = opening_after.name if opening_after else "der aktuellen Stellung"
        fallback = TutorText(
            summary=f"Ich spiele {san}. Der Zug führt {opening} solide weiter.",
            details=self._move_details(session.board, move, analysis),
            source="deterministic",
            model=None,
        )
        facts = self._grounded(session, "coach", san, theory_match, analysis, opening_after)
        return self._message("coach", san, facts, fallback)

    def _mistake_message(
        self,
        session: GameSession,
        move: chess.Move,
        san: str,
        theory_match: bool,
        analysis: MoveAnalysis,
        attempt: int,
    ) -> dict[str, Any]:
        if attempt == 1:
            hint = "Prüfe zuerst Entwicklung, Zentrum, Königssicherheit und direkte Drohungen."
        else:
            best = chess.Move.from_uci(analysis.best_move_uci or move.uci())
            piece = session.board.piece_at(best.from_square)
            piece_name = {
                chess.PAWN: "Bauern",
                chess.KNIGHT: "Springer",
                chess.BISHOP: "Läufer",
                chess.ROOK: "Turm",
                chess.QUEEN: "Dame",
                chess.KING: "König",
            }.get(piece.piece_type if piece else None, "eine andere Figur")
            hint = f"Der stärkere Zug wird mit dem {piece_name} gespielt."
        fallback = TutorText(
            summary=f"{san} verschlechtert deine Stellung deutlich. Noch ein Versuch: {hint}",
            details=self._engine_details(analysis, reveal_best=False),
            source="deterministic",
            model=None,
        )
        facts = self._grounded(session, "learner", san, theory_match, analysis, session.opening)
        return self._message("learner", san, facts, fallback)

    def _solution_message(
        self, session: GameSession, played_san: str, recommended_san: str, analysis: MoveAnalysis
    ) -> dict[str, Any]:
        fallback = TutorText(
            summary=f"Die Lösung ist {recommended_san}. Ich setze den Zug jetzt aufs Brett.",
            details=f"{played_san} verlor laut Engine {analysis.loss_pawns:.2f} Bauerneinheiten. "
            + self._engine_details(analysis),
            source="deterministic",
            model=None,
        )
        facts = self._grounded(session, "learner", recommended_san, True, analysis, session.opening)
        return self._message("learner", recommended_san, facts, fallback)

    def _illegal_message(self, attempt: int) -> dict[str, Any]:
        return {
            "actor": "learner",
            "move": None,
            "summary": "Dieser Zug ist in der aktuellen Stellung nicht legal.",
            "details": (
                "Prüfe, ob der Weg der Figur frei ist und ob dein König danach sicher steht."
            ),
            "source": "python-chess",
            "model": None,
            "attempt": attempt,
            "engine": None,
        }

    def _message(
        self, actor: str, san: str, facts: dict[str, Any], fallback: TutorText
    ) -> dict[str, Any]:
        text = self.tutor.explain(facts, fallback)
        return {
            "actor": actor,
            "move": san,
            "summary": text.summary,
            "details": text.details,
            "source": text.source,
            "model": text.model,
            "attempt": None,
            "engine": facts["engine"],
        }

    def _grounded(
        self,
        session: GameSession,
        actor: str,
        san: str,
        theory_match: bool,
        analysis: MoveAnalysis,
        opening: OpeningIdentity | None,
    ) -> dict[str, Any]:
        return {
            "task": "Erkläre den gerade gespielten Eröffnungszug.",
            "fen": session.board.fen(),
            "move": san,
            "actor": actor,
            "opening": asdict(opening) if opening else None,
            "theory_match": theory_match,
            "engine": asdict(analysis),
        }

    @staticmethod
    def _engine_details(analysis: MoveAnalysis, *, reveal_best: bool = True) -> str:
        if not analysis.available:
            return (
                "Stockfish ist derzeit nicht verfügbar; die objektive Bewertung wird nachgereicht."
            )
        evaluation = _format_evaluation(analysis.evaluation_played, analysis.mate_played)
        best = f" Der beste Engine-Zug ist {analysis.best_move_san}." if reveal_best else ""
        loss = ""
        if reveal_best and analysis.loss_pawns is not None and analysis.loss_pawns >= 0.15:
            formatted_loss = f"{analysis.loss_pawns:.2f}".replace(".", ",")
            loss = (
                f" Der Abstand zum besten Zug beträgt {formatted_loss} Bauerneinheiten; "
                "1,00 entspricht ungefähr dem Wert eines Bauern."
            )
        variation = ""
        if (
            reveal_best
            and analysis.played_pv_san
            and analysis.best_pv_san
            and analysis.played_pv_san[0] != analysis.best_pv_san[0]
        ):
            played_line = " ".join(analysis.played_pv_san[:4])
            best_line = " ".join(analysis.best_pv_san[:4])
            variation = (
                f" Als konkreten Rechenweg prüft Stockfish nach deinem Zug {played_line}; "
                f"nach der Alternative {best_line}. Diese Varianten sind Beispiele, keine "
                "erzwungenen Zugfolgen."
            )
        return (
            f"Stockfish bewertet die entstehende Stellung mit {evaluation}.{best}{loss}{variation}"
        )

    def _move_details(self, board: chess.Board, move: chess.Move, analysis: MoveAnalysis) -> str:
        return " ".join(
            part
            for part in (
                _move_response_context(board, move),
                _heuristic_context(board, move),
                _move_concept(board, move),
                _concrete_board_changes(board, move),
                _continuation_context(board, move, analysis),
                _tactical_contrast(board, move, analysis),
                self._engine_details(analysis),
            )
            if part
        )

    def _record(
        self,
        session: GameSession,
        fen_before: str,
        actor: str,
        move: chess.Move | None,
        legal: bool,
        accepted: bool,
        theory_match: bool | None,
        analysis: MoveAnalysis | None,
        message: dict[str, Any],
    ) -> None:
        self.store.record(
            {
                "session_id": session.session_id,
                "fen_before": fen_before,
                "actor": actor,
                "move_uci": move.uci() if move else None,
                "move_san": message.get("move"),
                "legal": int(legal),
                "accepted": int(accepted),
                "theory_match": None if theory_match is None else int(theory_match),
                "opening_eco": session.opening.eco if session.opening else None,
                "opening_name": session.opening.name if session.opening else None,
                "engine_evaluation": analysis.evaluation_played if analysis else None,
                "engine_loss": analysis.loss_pawns if analysis else None,
                "engine_classification": analysis.classification if analysis else None,
                "attempt_number": session.attempts_at_position,
                "feedback_summary": message["summary"],
                "llm_model": message.get("model"),
            }
        )

    @staticmethod
    def _attach_transition(
        message: dict[str, Any], move: chess.Move, board_after: chess.Board
    ) -> None:
        message["move_uci"] = move.uci()
        message["fen_after"] = board_after.fen()

    def _save_turn_snapshot(self, session: GameSession) -> None:
        session.undo_stack.append(
            TurnSnapshot(
                fen=session.board.fen(),
                opening=session.opening,
                move_history_length=len(session.move_history),
                message_history_length=len(session.message_history),
                interaction_id=self.store.latest_interaction_id(session.session_id),
            )
        )

    def _response(
        self,
        session: GameSession,
        *,
        messages: list[dict[str, Any]],
        correction: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session.message_history.extend(messages)
        opening = asdict(session.opening) if session.opening else None
        legal_moves = [move.uci() for move in session.board.legal_moves]
        return {
            "session_id": session.session_id,
            "fen": session.board.fen(),
            "learner_color": "white" if session.learner_color == chess.WHITE else "black",
            "turn": "white" if session.board.turn == chess.WHITE else "black",
            "opening": opening,
            "legal_moves": legal_moves,
            "move_history": session.move_history,
            "messages": messages,
            "message_history": session.message_history,
            "can_undo": bool(session.undo_stack),
            "correction": correction,
            "game_over": session.board.is_game_over(),
        }

    def _correction(self, session: GameSession, analysis: MoveAnalysis | None) -> dict[str, Any]:
        return {
            "active": True,
            "attempt": session.attempts_at_position,
            "remaining": max(0, 3 - session.attempts_at_position),
            "solution_revealed": session.attempts_at_position >= 3,
            "recommended_move": analysis.best_move_san
            if analysis and session.attempts_at_position >= 3
            else None,
        }

    def _session(self, session_id: str) -> GameSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise KeyError("Diese Trainingssitzung existiert nicht mehr") from exc

    @staticmethod
    def _parse_move(
        board: chess.Board, from_square: str, to_square: str, promotion: str | None
    ) -> chess.Move:
        suffix = promotion or ""
        if board.piece_at(chess.parse_square(from_square)) == chess.Piece(chess.PAWN, board.turn):
            if to_square[1] in {"1", "8"} and not suffix:
                suffix = "q"
        try:
            return chess.Move.from_uci(f"{from_square}{to_square}{suffix}")
        except (chess.InvalidMoveError, ValueError) as exc:
            raise ValueError("Ungültige Feldangabe") from exc


def _format_evaluation(score: float | None, mate: int | None) -> str:
    if mate is not None:
        return f"#{abs(mate)} für {'Weiß' if mate > 0 else 'Schwarz'}"
    if score is None:
        return "nicht verfügbar"
    return f"{score:+.2f}".replace(".", ",")


def _move_concept(board: chess.Board, move: chess.Move) -> str:
    piece = board.piece_at(move.from_square)
    if piece is None:
        return "Der Zug verändert die Figurenkoordination."
    target = chess.square_name(move.to_square)
    if board.is_castling(move):
        return "Die Rochade bringt den König in Sicherheit und verbindet die Türme."
    if piece.piece_type == chess.PAWN:
        before = _square_list(board.attacks(move.from_square))
        projected = board.copy(stack=False)
        projected.push(move)
        after = _square_list(projected.attacks(move.to_square))
        explanation = (
            f"Mit {board.san(move)} kontrolliert der Bauer nun {after}; von "
            f"{chess.square_name(move.from_square)} aus kontrollierte er {before}. "
            "Weil Bauern nicht rückwärts ziehen können, ist diese Änderung nicht einfach "
            "rückgängig zu machen."
        )
        if any(
            move.to_square in chess.SquareSet(chess.BB_KNIGHT_ATTACKS[square])
            for square in board.pieces(chess.KNIGHT, board.turn)
        ):
            explanation += " Außerdem kann ein eigener Springer dieses Feld nun nicht benutzen."
        return explanation
    if piece.piece_type == chess.KNIGHT:
        projected = board.copy(stack=False)
        projected.push(move)
        controlled = projected.attacks(move.to_square)
        central = controlled & chess.SquareSet(chess.BB_CENTER)
        center_text = (
            f" Davon {'ist' if len(central) == 1 else 'sind'} {_square_list(central)} "
            f"{'ein Zentrumsfeld' if len(central) == 1 else 'Zentrumsfelder'}."
            if central
            else " Keines davon ist eines der vier Zentrumsfelder d4, e4, d5 und e5."
        )
        attacked_pieces = _attacked_piece_list(projected, move.to_square, board.turn)
        attack_text = f" Dabei greift er {attacked_pieces} an." if attacked_pieces else ""
        return (
            f"Der Springer zieht nach {target} und kontrolliert von dort "
            f"{_square_list(controlled)}.{center_text}{attack_text}"
        )

    piece_name, pronoun = {
        chess.BISHOP: ("Läufer", "er"),
        chess.ROOK: ("Turm", "er"),
        chess.QUEEN: ("Dame", "sie"),
        chess.KING: ("König", "er"),
    }[piece.piece_type]
    projected = board.copy(stack=False)
    projected.push(move)
    controlled = projected.attacks(move.to_square)
    central = controlled & chess.SquareSet(chess.BB_CENTER)
    if central:
        center_text = f"Von dort kontrolliert {pronoun} direkt {_square_list(central)} im Zentrum."
    else:
        center_text = (
            f"Von dort kontrolliert {pronoun} keines der vier Zentrumsfelder "
            "d4, e4, d5 und e5 direkt."
        )
    attacked_pieces = _attacked_piece_list(projected, move.to_square, board.turn)
    attack_text = f" Außerdem greift {pronoun} {attacked_pieces} an." if attacked_pieces else ""
    return f"Der {piece_name} zieht nach {target}. {center_text}{attack_text}"


def _square_list(squares: chess.SquareSet) -> str:
    names = [chess.square_name(square) for square in squares]
    if not names:
        return "keine Felder"
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} und {names[-1]}"


def _move_response_context(board: chess.Board, move: chess.Move) -> str:
    """Describe when the move answers a direct attack on the moving piece."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        return ""
    attackers = board.attackers(not board.turn, move.from_square)
    if not attackers:
        return ""

    attacker_square = next(
        (
            square
            for square in attackers
            if (attacker := board.piece_at(square)) and attacker.piece_type == chess.PAWN
        ),
        next(iter(attackers)),
    )
    attacker = board.piece_at(attacker_square)
    if attacker is None:
        return ""
    piece_name, possessive, accusative = {
        chess.PAWN: ("Bauer", "dein", "den Bauern"),
        chess.KNIGHT: ("Springer", "dein", "den Springer"),
        chess.BISHOP: ("Läufer", "dein", "den Läufer"),
        chess.ROOK: ("Turm", "dein", "den Turm"),
        chess.QUEEN: ("Dame", "deine", "die Dame"),
        chess.KING: ("König", "dein", "den König"),
    }[piece.piece_type]
    attacker_phrase = {
        chess.PAWN: "vom gegnerischen Bauern",
        chess.KNIGHT: "vom gegnerischen Springer",
        chess.BISHOP: "vom gegnerischen Läufer",
        chess.ROOK: "vom gegnerischen Turm",
        chess.QUEEN: "von der gegnerischen Dame",
        chess.KING: "vom gegnerischen König",
    }[attacker.piece_type]
    san = board.san(move)
    source = chess.square_name(move.from_square)
    projected = board.copy(stack=False)
    projected.push(move)
    if projected.attackers(not board.turn, move.to_square):
        result = (
            f"{san} löst den bisherigen Angriff, auf {chess.square_name(move.to_square)} "
            f"ist {accusative} aber weiterhin angegriffen."
        )
    else:
        result = f"{san} bringt {accusative} aus diesem Angriff."
    return (
        f"Vor {san} wird {possessive} {piece_name} auf {source} {attacker_phrase} auf "
        f"{chess.square_name(attacker_square)} angegriffen. {result}"
    )


def _continuation_context(board: chess.Board, move: chess.Move, analysis: MoveAnalysis) -> str:
    """Identify a verified temporary square when the PV moves the same piece again."""
    line = analysis.played_pv_san
    if len(line) < 3:
        return ""
    replay = board.copy(stack=False)
    try:
        first = replay.parse_san(line[0])
        if first != move:
            return ""
        moved_piece = replay.piece_at(first.from_square)
        replay.push(first)
        reply = replay.parse_san(line[1])
        reply_piece = replay.piece_at(reply.from_square)
        reply_was_attacked = reply.from_square in replay.attacks(first.to_square)
        reply_from = chess.square_name(reply.from_square)
        replay.push(reply)
        continuation = replay.parse_san(line[2])
        continuing_piece = replay.piece_at(continuation.from_square)
    except (chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError, ValueError):
        return ""
    if (
        moved_piece is None
        or continuing_piece != moved_piece
        or continuation.from_square != move.to_square
    ):
        return ""
    reply_context = ""
    if reply_was_attacked and reply_piece is not None and reply_piece.color != moved_piece.color:
        reply_name = {
            chess.PAWN: "Bauern",
            chess.KNIGHT: "Springer",
            chess.BISHOP: "Läufer",
            chess.ROOK: "Turm",
            chess.QUEEN: "Dame",
            chess.KING: "König",
        }[reply_piece.piece_type]
        reply_context = (
            f"Die Antwort {line[1]} zieht den von {line[0]} angegriffenen {reply_name} "
            f"von {reply_from} weg. "
        )
    return (
        f"{reply_context}In der Stockfish-Prüfvariante zieht dieselbe Figur nach der Antwort "
        f"{line[1]} mit {line[2]} gleich noch einmal weiter. "
        f"{chess.square_name(move.to_square)} ist in dieser Variante also eine "
        "Zwischenstation und kein dauerhafter Posten."
    )


def _heuristic_context(board: chess.Board, move: chess.Move) -> str:
    """Put a knight-on-the-rim heuristic behind a verified immediate threat."""
    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type != chess.KNIGHT:
        return ""
    if chess.square_file(move.to_square) not in {0, 7}:
        return ""
    if not board.attackers(not board.turn, move.from_square):
        return ""
    projected = board.copy(stack=False)
    projected.push(move)
    if projected.attacks(move.to_square) & chess.SquareSet(chess.BB_CENTER):
        return ""
    san = board.san(move)
    return (
        f"Dein Einwand zur Faustregel „Springer am Rand“ ist richtig: {san} ist kein "
        "aktiver Zentrumszug. Die Faustregel ist aber nicht absolut; zuerst muss der "
        "konkret angegriffene Springer einen brauchbaren Rückzugsplatz finden."
    )


def _concrete_board_changes(board: chess.Board, move: chess.Move) -> str:
    """Describe captures, checks, and newly opened lines without strategic guessing."""
    changes: list[str] = []
    san = board.san(move)
    if board.is_capture(move):
        capture_square = move.to_square
        if board.is_en_passant(move):
            capture_square += -8 if board.turn == chess.WHITE else 8
        captured = board.piece_at(capture_square)
        if captured:
            captured_name = {
                chess.PAWN: "den gegnerischen Bauern",
                chess.KNIGHT: "den gegnerischen Springer",
                chess.BISHOP: "den gegnerischen Läufer",
                chess.ROOK: "den gegnerischen Turm",
                chess.QUEEN: "die gegnerische Dame",
                chess.KING: "den gegnerischen König",
            }[captured.piece_type]
            changes.append(
                f"{san} schlägt {captured_name} auf {chess.square_name(capture_square)}."
            )

    projected = board.copy(stack=False)
    projected.push(move)
    if projected.is_check():
        changes.append(f"{san} gibt dem gegnerischen König Schach.")

    opened_lines: list[str] = []
    piece_labels = {
        chess.BISHOP: "des Läufers",
        chess.ROOK: "des Turms",
        chess.QUEEN: "der Dame",
    }
    for piece_type, label in piece_labels.items():
        for square in board.pieces(piece_type, board.turn):
            if square == move.from_square:
                continue
            before = board.attacks(square)
            same_piece = projected.piece_at(square)
            if same_piece != chess.Piece(piece_type, board.turn):
                continue
            newly_reached = projected.attacks(square) - before
            if newly_reached:
                opened_lines.append(
                    f"{label} auf {chess.square_name(square)} bis "
                    f"{_limited_square_list(newly_reached)}"
                )
    if opened_lines:
        changes.append(
            f"Der Zug öffnet oder verlängert außerdem die Wirkung "
            f"{' sowie '.join(opened_lines[:2])}."
        )
    return " ".join(changes)


def _limited_square_list(squares: chess.SquareSet, *, limit: int = 4) -> str:
    names = [chess.square_name(square) for square in squares]
    if len(names) <= limit:
        return _square_list(chess.SquareSet(squares))
    visible = names[:limit]
    return f"{', '.join(visible)} und {len(names) - limit} weitere Felder"


def _attacked_piece_list(
    board: chess.Board, attacking_square: chess.Square, color: chess.Color
) -> str:
    targets: list[str] = []
    labels = {
        chess.PAWN: "den gegnerischen Bauern",
        chess.KNIGHT: "den gegnerischen Springer",
        chess.BISHOP: "den gegnerischen Läufer",
        chess.ROOK: "den gegnerischen Turm",
        chess.QUEEN: "die gegnerische Dame",
        chess.KING: "den gegnerischen König",
    }
    for square in board.attacks(attacking_square):
        piece = board.piece_at(square)
        if piece and piece.color != color:
            targets.append(f"{labels[piece.piece_type]} auf {chess.square_name(square)}")
    if len(targets) <= 1:
        return "" if not targets else targets[0]
    return f"{', '.join(targets[:-1])} und {targets[-1]}"


def _candidate_comparison_text(
    board: chess.Board,
    focus_move: chess.Move,
    focus_analysis: MoveAnalysis,
    comparison: MoveComparison,
) -> str:
    if not comparison.available or not comparison.candidates:
        return ""
    candidates = list(comparison.candidates)
    focus = next(
        (candidate for candidate in candidates if candidate.move_uci == focus_move.uci()),
        None,
    )
    if focus is None and focus_analysis.evaluation_played is not None:
        focus = CandidateAnalysis(
            move_uci=focus_move.uci(),
            move_san=board.san(focus_move),
            evaluation=focus_analysis.evaluation_played,
            mate=focus_analysis.mate_played,
            loss_pawns=focus_analysis.loss_pawns or 0.0,
            pv_san=focus_analysis.played_pv_san,
        )
    if focus is None:
        return ""

    best = candidates[0]
    if focus.move_uci == best.move_uci:
        alternative = next(
            (candidate for candidate in candidates if candidate.move_uci != focus.move_uci),
            None,
        )
        if alternative is None:
            return ""
        gap = alternative.loss_pawns
        comparison_intro = (
            f"Stockfishs nächster Kandidat ist {alternative.move_san}; die vertiefte "
            f"Analyse bewertet ihn um {_format_pawns(gap)} Bauerneinheiten schwächer."
        )
    else:
        alternative = best
        gap = focus.loss_pawns
        comparison_intro = (
            f"Stockfish bevorzugt {best.move_san} gegenüber {focus.move_san} um "
            f"{_format_pawns(gap)} Bauerneinheiten."
        )

    focus_effects = _move_effects(board, focus_move)
    try:
        alternative_move = chess.Move.from_uci(alternative.move_uci)
    except (chess.InvalidMoveError, ValueError):
        alternative_move = None
    alternative_effects = (
        _move_effects(board, alternative_move)
        if alternative_move is not None and alternative_move in board.legal_moves
        else None
    )

    differences: list[str] = []
    if alternative_effects:
        if focus_effects["escapes_attack"] and alternative_effects["escapes_attack"]:
            if focus_move.from_square == alternative_move.from_square:
                piece_name = _piece_name(board.piece_at(focus_move.from_square))
                differences.append(
                    f"Beide Züge bringen den angegriffenen {piece_name} aus dem bisherigen Angriff."
                )
            else:
                differences.append(
                    f"{focus.move_san} beantwortet den Angriff auf "
                    f"{focus_effects['escaped_piece']}; {alternative.move_san} dagegen den "
                    f"Angriff auf {alternative_effects['escaped_piece']}."
                )
        focus_unresolved = focus_effects["unresolved_attacks"]
        alternative_unresolved = alternative_effects["unresolved_attacks"]
        if focus_unresolved != alternative_unresolved and (
            focus_unresolved or alternative_unresolved
        ):
            differences.append(
                f"Nach {focus.move_san} bleiben angegriffen: "
                f"{focus_unresolved or 'keine eigenen Steine'}; nach "
                f"{alternative.move_san}: "
                f"{alternative_unresolved or 'keine eigenen Steine'}."
            )
            focus_value = focus_effects["highest_unresolved_value"]
            alternative_value = alternative_effects["highest_unresolved_value"]
            if focus_value > alternative_value:
                differences.append(
                    f"Der nach {focus.move_san} weiter angegriffene Stein ist materiell "
                    f"wertvoller ({focus_value} gegenüber {alternative_value} ungefähren "
                    "Bauerneinheiten)."
                )
        focus_targets = focus_effects["new_targets"]
        alternative_targets = alternative_effects["new_targets"]
        if focus_targets and not alternative_targets:
            differences.append(
                f"Nur {focus.move_san} erzeugt zugleich einen direkten Gegenangriff: "
                f"{focus_targets}. {alternative.move_san} greift unmittelbar keine neue "
                "gegnerische Figur an."
            )
        elif focus_targets != alternative_targets and (focus_targets or alternative_targets):
            differences.append(
                f"{focus.move_san} greift neu {focus_targets or 'keine Figur'} an; "
                f"{alternative.move_san} dagegen {alternative_targets or 'keine Figur'}."
            )
        focus_center = focus_effects["central_squares"]
        alternative_center = alternative_effects["central_squares"]
        if focus_center != alternative_center:
            differences.append(
                f"Direkte Zentrumsfelder nach {focus.move_san}: {focus_center or 'keine'}; "
                f"nach {alternative.move_san}: {alternative_center or 'keine'}."
            )

    focus_reply = _first_reply_event(board, focus)
    alternative_reply = _first_reply_event(board, alternative)
    if focus_reply:
        differences.append(focus_reply)
    if alternative_reply and alternative_reply != focus_reply:
        differences.append(alternative_reply)

    if differences:
        interpretation = (
            "Diese sichtbaren Unterschiede erklären plausibel einen Teil des Engine-Abstands; "
            "die Bewertung allein beweist aber keinen einzigen ausschließlichen Grund."
        )
    else:
        interpretation = (
            "Aus der Bewertungszahl allein folgt kein eindeutiger strategischer Grund; die "
            "unterschiedlichen Rechenwege stehen im nächsten Abschnitt."
        )
    return " ".join((comparison_intro, *differences, interpretation))


def _candidate_lines_text(
    focus_move: chess.Move,
    focus_analysis: MoveAnalysis,
    comparison: MoveComparison,
) -> str:
    if not comparison.available or not comparison.candidates:
        return ""
    candidates = list(comparison.candidates)
    if (
        all(candidate.move_uci != focus_move.uci() for candidate in candidates)
        and focus_analysis.evaluation_played is not None
    ):
        candidates.append(
            CandidateAnalysis(
                move_uci=focus_move.uci(),
                move_san=focus_analysis.played_pv_san[0]
                if focus_analysis.played_pv_san
                else focus_move.uci(),
                evaluation=focus_analysis.evaluation_played,
                mate=focus_analysis.mate_played,
                loss_pawns=focus_analysis.loss_pawns or 0.0,
                pv_san=focus_analysis.played_pv_san,
            )
        )
    lines: list[str] = []
    for candidate in candidates[:4]:
        evaluation = _format_evaluation(candidate.evaluation, candidate.mate)
        loss = (
            f", {_format_pawns(candidate.loss_pawns)} Bauerneinheiten hinter Platz 1"
            if candidate.loss_pawns >= 0.01
            else ""
        )
        pv = " ".join(candidate.pv_san[:6]) or "keine Variante verfügbar"
        lines.append(f"{candidate.move_san} ({evaluation}{loss}): {pv}.")
    return "Bewertungen aus weißer Sicht; + bedeutet Vorteil für Weiß. " + " ".join(lines)


def _move_effects(board: chess.Board, move: chess.Move) -> dict[str, Any]:
    piece = board.piece_at(move.from_square)
    before_targets = board.attacks(move.from_square)
    attacked_before = bool(board.attackers(not board.turn, move.from_square))
    projected = board.copy(stack=False)
    projected.push(move)
    after_targets = projected.attacks(move.to_square)
    new_target_squares = after_targets - before_targets
    new_targets = _target_descriptions(projected, new_target_squares, board.turn)
    central = after_targets & chess.SquareSet(chess.BB_CENTER)
    escaped = attacked_before and not projected.attackers(not board.turn, move.to_square)
    unresolved: list[tuple[str, int]] = []
    for square in chess.SQUARES:
        before_piece = board.piece_at(square)
        if before_piece is None or before_piece.color != board.turn:
            continue
        if not board.attackers(not board.turn, square):
            continue
        after_piece = projected.piece_at(square)
        if after_piece == before_piece and projected.attackers(not board.turn, square):
            unresolved.append(
                (
                    f"{_piece_name_singular(before_piece)} auf {chess.square_name(square)}",
                    _piece_value(before_piece),
                )
            )
    unresolved.sort(key=lambda item: item[1], reverse=True)
    return {
        "piece": _piece_name(piece),
        "escapes_attack": escaped,
        "escaped_piece": (
            f"{_piece_name_accusative(piece)} auf {chess.square_name(move.from_square)}"
            if escaped
            else ""
        ),
        "unresolved_attacks": _join_descriptions([item[0] for item in unresolved]),
        "highest_unresolved_value": unresolved[0][1] if unresolved else 0,
        "new_targets": new_targets,
        "central_squares": _square_list(central) if central else "",
    }


def _first_reply_event(board: chess.Board, candidate: CandidateAnalysis) -> str:
    if len(candidate.pv_san) < 2:
        return ""
    replay = board.copy(stack=False)
    try:
        first = replay.parse_san(candidate.pv_san[0])
        replay.push(first)
        reply = replay.parse_san(candidate.pv_san[1])
    except (chess.IllegalMoveError, chess.InvalidMoveError, chess.AmbiguousMoveError, ValueError):
        return ""
    if not replay.is_capture(reply):
        return ""
    capture_square = reply.to_square
    if replay.is_en_passant(reply):
        capture_square += -8 if replay.turn == chess.WHITE else 8
    captured = replay.piece_at(capture_square)
    if captured is None:
        return ""
    actor = "Weiß" if replay.turn == chess.WHITE else "Schwarz"
    return (
        f"Im konkreten Rechenweg nach {candidate.move_san} folgt sofort "
        f"{candidate.pv_san[1]}: {actor} schlägt damit "
        f"{_piece_name_accusative(captured)} auf {chess.square_name(capture_square)}."
    )


def _target_descriptions(
    board: chess.Board, squares: chess.SquareSet, moving_color: chess.Color
) -> str:
    labels = {
        chess.PAWN: "den gegnerischen Bauern",
        chess.KNIGHT: "den gegnerischen Springer",
        chess.BISHOP: "den gegnerischen Läufer",
        chess.ROOK: "den gegnerischen Turm",
        chess.QUEEN: "die gegnerische Dame",
        chess.KING: "den gegnerischen König",
    }
    targets = [
        f"{labels[piece.piece_type]} auf {chess.square_name(square)}"
        for square in squares
        if (piece := board.piece_at(square)) and piece.color != moving_color
    ]
    if not targets:
        return ""
    if len(targets) == 1:
        return targets[0]
    return f"{', '.join(targets[:-1])} und {targets[-1]}"


def _piece_name(piece: chess.Piece | None) -> str:
    if piece is None:
        return "Figur"
    return {
        chess.PAWN: "Bauern",
        chess.KNIGHT: "Springer",
        chess.BISHOP: "Läufer",
        chess.ROOK: "Turm",
        chess.QUEEN: "Dame",
        chess.KING: "König",
    }[piece.piece_type]


def _piece_name_singular(piece: chess.Piece | None) -> str:
    if piece is None:
        return "Figur"
    return {
        chess.PAWN: "Bauer",
        chess.KNIGHT: "Springer",
        chess.BISHOP: "Läufer",
        chess.ROOK: "Turm",
        chess.QUEEN: "Dame",
        chess.KING: "König",
    }[piece.piece_type]


def _piece_name_accusative(piece: chess.Piece | None) -> str:
    if piece is None:
        return "die Figur"
    return {
        chess.PAWN: "den Bauern",
        chess.KNIGHT: "den Springer",
        chess.BISHOP: "den Läufer",
        chess.ROOK: "den Turm",
        chess.QUEEN: "die Dame",
        chess.KING: "den König",
    }[piece.piece_type]


def _piece_value(piece: chess.Piece) -> int:
    return {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 100,
    }[piece.piece_type]


def _join_descriptions(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} und {items[-1]}"


def _format_pawns(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _tactical_contrast(board: chess.Board, move: chess.Move, analysis: MoveAnalysis) -> str:
    """Explain one mechanically verifiable reason for an engine alternative."""
    if not analysis.available or not analysis.best_move_uci:
        return ""
    try:
        best = chess.Move.from_uci(analysis.best_move_uci)
    except (chess.InvalidMoveError, ValueError):
        return ""
    if best not in board.legal_moves or best == move or best.from_square == move.from_square:
        return ""

    piece = board.piece_at(best.from_square)
    if piece is None or piece.color != board.turn:
        return ""
    attackers = board.attackers(not board.turn, best.from_square)
    if not attackers:
        return ""

    projected = board.copy(stack=False)
    projected.push(move)
    remaining = projected.piece_at(best.from_square)
    if remaining != piece or not projected.attackers(not board.turn, best.from_square):
        return ""

    piece_name, possessive, accusative = {
        chess.PAWN: ("Bauer", "dein", "den Bauern"),
        chess.KNIGHT: ("Springer", "dein", "den Springer"),
        chess.BISHOP: ("Läufer", "dein", "den Läufer"),
        chess.ROOK: ("Turm", "dein", "den Turm"),
        chess.QUEEN: ("Dame", "deine", "die Dame"),
        chess.KING: ("König", "dein", "den König"),
    }[piece.piece_type]
    attacked_square = chess.square_name(best.from_square)
    played_san = board.san(move)
    best_san = board.san(best)
    best_position = board.copy(stack=False)
    best_position.push(best)
    if best_position.attackers(not board.turn, best.to_square):
        response = f"{best_san} reagiert dagegen unmittelbar mit dieser Figur."
    else:
        response = f"{best_san} bringt {accusative} aus dem Angriff."
    return (
        f"Vor {played_san} ist {possessive} {piece_name} auf {attacked_square} angegriffen. "
        f"{played_san} lässt diesen Angriff bestehen; {response}"
    )
