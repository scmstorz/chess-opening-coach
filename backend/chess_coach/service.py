from __future__ import annotations

import json
import random
import re
import threading
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

import chess

from chess_coach.book_knowledge import BookKnowledgeBase, NullBookKnowledgeBase
from chess_coach.book_knowledge.models import BookEvidence, BookFact
from chess_coach.engine import (
    CandidateAnalysis,
    MoveAnalysis,
    MoveComparison,
    MovePlanAnalysis,
    StockfishService,
)
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
    phase: str
    opening_end: OpeningEndEvidence | None


@dataclass(frozen=True, slots=True)
class HistoricalMoveContext:
    """A learner move together with the position in which it was played."""

    board: chess.Board
    move: chess.Move
    opening: OpeningIdentity | None
    phase: str


@dataclass(frozen=True, slots=True)
class MoveNotationClarification:
    """A coordinate-resolvable move whose piece designators contradict the board."""

    original_question: str
    corrected_question: str
    move_uci: str
    move_san: str
    fen: str
    prompt: str
    explanation: str


@dataclass(frozen=True, slots=True)
class OpeningEndEvidence:
    likely: bool
    headline: str
    explanation: str
    signals: tuple[dict[str, Any], ...]
    can_continue: bool


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
    phase: str = "opening"
    opening_end: OpeningEndEvidence | None = None
    opening_summary: dict[str, Any] | None = None
    pending_move_clarification: MoveNotationClarification | None = None
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
        book_knowledge: BookKnowledgeBase | NullBookKnowledgeBase | None = None,
    ) -> None:
        self.openings = opening_book
        self.engine = engine
        self.tutor = tutor
        self.store = store
        self.book_knowledge = book_knowledge or NullBookKnowledgeBase()
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
            if session.phase == "transition":
                raise ValueError(
                    "Bitte entscheide zuerst, ob du weiterspielen oder die Eröffnung "
                    "auswerten möchtest"
                )
            if session.phase == "complete":
                raise ValueError("Diese Eröffnungseinheit ist bereits abgeschlossen")
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
            theory_moves = (
                () if session.phase == "middlegame" else self.openings.theory_moves(session.board)
            )
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
            if session.phase == "complete":
                raise ValueError("Die abgeschlossene Auswertung kann nicht zurückgenommen werden")
            if not session.undo_stack:
                raise ValueError("Es gibt noch keinen vollständigen Zug zum Zurücknehmen")
            snapshot = session.undo_stack.pop()
            removed_moves = len(session.move_history) - snapshot.move_history_length
            removed_messages = len(session.message_history) - snapshot.message_history_length
            session.board = chess.Board(snapshot.fen)
            session.opening = snapshot.opening
            session.phase = snapshot.phase
            session.opening_end = snapshot.opening_end
            session.opening_summary = None
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

    def continue_after_opening(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        with session.lock:
            if session.phase != "transition":
                raise ValueError("Für diese Sitzung steht keine Eröffnungsentscheidung an")
            if session.board.is_game_over():
                raise ValueError("Die Partie ist beendet und kann nur noch ausgewertet werden")
            session.phase = "middlegame"
            message = {
                "kind": "phase",
                "actor": "coach",
                "move": None,
                "summary": (
                    "Wir spielen weiter. Ab jetzt behandle ich die Stellung als Mittelspiel."
                ),
                "details": (
                    "Zuglegalität und Stockfish-Prüfung bleiben unverändert. Die lokale "
                    "Eröffnungstheorie ist ab jetzt nur noch Kontext und keine erwartete Zugfolge."
                ),
                "source": "verified-phase-heuristic",
                "model": None,
                "attempt": None,
                "engine": None,
            }
            return self._response(session, messages=[message])

    def finish_opening(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        with session.lock:
            if session.phase == "complete" and session.opening_summary:
                return self._response(session, messages=[])
            if session.phase not in {"transition", "middlegame"}:
                raise ValueError("Die Eröffnungsphase ist für diese Sitzung noch nicht beendet")

            summary = self._build_opening_summary(session)
            session.opening_summary = self.store.record_session_summary(
                session_id=session.session_id,
                opening_eco=session.opening.eco if session.opening else None,
                opening_name=session.opening.name if session.opening else None,
                final_fen=session.board.fen(),
                move_count=len(session.move_history),
                summary=summary,
            )
            session.phase = "complete"
            message = {
                "kind": "summary",
                "actor": "coach",
                "move": None,
                "summary": "Die Eröffnung ist ausgewertet. Dein wichtigster Merksatz steht unten.",
                "details": session.opening_summary["takeaway"],
                "source": "verified-session-data",
                "model": None,
                "attempt": None,
                "engine": None,
            }
            return self._response(session, messages=[message])

    def suggest_move(self, session_id: str) -> dict[str, Any]:
        """Return a theory-first, engine-checked hint without changing the game."""
        session = self._session(session_id)
        with session.lock:
            if session.phase == "transition":
                raise ValueError(
                    "Bitte entscheide zuerst, ob du weiterspielen oder die Eröffnung "
                    "auswerten möchtest"
                )
            if session.phase == "complete":
                raise ValueError("Diese Eröffnungseinheit ist bereits abgeschlossen")
            if session.board.turn != session.learner_color:
                raise ValueError("Der Coach ist am Zug")

            if session.phase == "middlegame":
                move, analysis = self.engine.get_best_move(session.board)
                if move is None or not analysis.available:
                    raise ValueError(
                        "Im Mittelspiel wird Stockfish für einen verlässlichen Zugvorschlag "
                        "benötigt"
                    )
                basis = "engine"
                theory_move = None
            else:
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
                if session.phase == "middlegame":
                    summary = (
                        f"Stockfish bevorzugt {san} in dieser Mittelspielstellung. "
                        "Du hast dich entschieden, die Partie weiterzuspielen."
                    )
                    source_detail = (
                        "Der Vorschlag stammt direkt aus der aktuellen Engine-Analyse; "
                        "Eröffnungstheorie wird hier nicht als Zugvorgabe verwendet."
                    )
                else:
                    summary = (
                        f"Stockfish bevorzugt {san} in dieser Stellung. "
                        "Die lokale Eröffnungstheorie enthält hier keine Fortsetzung mehr."
                    )
                    source_detail = (
                        "Der Vorschlag stammt deshalb direkt aus der aktuellen Engine-Analyse."
                    )

            response_context = _move_response_context(session.board, move)
            defender_context = _defender_pressure_context(session.board, move)
            development_context = _development_context(session.board, move)
            concept_context = _useful_move_concept(
                session.board,
                move,
                analysis,
                defender_pressure_text=defender_context,
            )

            return {
                "move_uci": move.uci(),
                "move_san": san,
                "basis": basis,
                "opening": asdict(opening) if opening else None,
                "summary": summary,
                "details": " ".join(
                    part
                    for part in (
                        response_context,
                        defender_context,
                        _heuristic_context(session.board, move),
                        development_context,
                        concept_context,
                        _concrete_board_changes(session.board, move),
                        _continuation_context(session.board, move, analysis),
                        source_detail,
                        "Der Zug wird nur auf dem Brett markiert; du spielst ihn selbst.",
                    )
                    if part
                ),
                "engine": asdict(analysis),
            }

    def answer_question(
        self,
        session_id: str,
        question: str,
        focus_move_uci: str | None = None,
        *,
        deep: bool = False,
    ) -> dict[str, Any]:
        """Answer a position question from verified theory and engine facts."""
        session = self._session(session_id)
        with session.lock:
            display_question = question.strip()
            if not display_question:
                raise ValueError("Bitte gib eine Frage ein")

            board = session.board
            clean_question = display_question
            confirmed_clarification = False
            pending = session.pending_move_clarification
            if pending is not None:
                session.pending_move_clarification = None
                if _is_affirmative_answer(display_question) and pending.fen == board.fen():
                    clean_question = pending.corrected_question
                    focus_move_uci = pending.move_uci
                    confirmed_clarification = True

            if not confirmed_clarification:
                clarification = self._move_notation_clarification(board, clean_question)
                if clarification is not None:
                    session.pending_move_clarification = clarification
                    message = {
                        "kind": "clarification",
                        "actor": "coach",
                        "question": display_question,
                        "move": clarification.move_san,
                        "move_uci": clarification.move_uci,
                        "summary": clarification.prompt,
                        "details": clarification.explanation,
                        "source": "deterministic",
                        "model": None,
                        "attempt": None,
                        "engine": None,
                        "explanation_sections": [],
                        "analysis_mode": "standard",
                        "references": [],
                        "knowledge": {
                            "status": "no_evidence",
                            "reason": "move_notation_requires_confirmation",
                            "evidence_count": 0,
                            "perspective_filtered_count": 0,
                            "used_evidence_ids": [],
                        },
                        "opening": asdict(session.opening) if session.opening else None,
                    }
                    self._prepare_message(message, board.fen())
                    session.message_history.append(message)
                    return {"message": message, "message_history": session.message_history}

            context_opening = session.opening
            question_phase = session.phase
            book_evidence = BookEvidence((), "none", False)
            knowledge_status = "no_evidence"
            knowledge_reason: str | None = None
            used_evidence_ids: tuple[str, ...] = ()
            answer_facts: list[dict[str, Any]] = []
            selection_facts: dict[str, Any] | None = None
            current_mentions = self._mentioned_legal_moves(board, clean_question)
            recent_attempt = (
                self._recent_unaccepted_learner_move(session)
                if not current_mentions and self._refers_to_own_past_move(clean_question)
                else None
            )
            historical_focus = (
                self._historical_learner_focus(session, clean_question)
                if not current_mentions and recent_attempt is None
                else None
            )
            if historical_focus is not None and not focus_move_uci:
                board = historical_focus.board
                context_opening = historical_focus.opening
                question_phase = historical_focus.phase

            mentioned_moves = (
                current_mentions
                if historical_focus is None
                else self._mentioned_legal_moves(board, clean_question)
            )
            move = mentioned_moves[0] if mentioned_moves else recent_attempt
            comparison_move = mentioned_moves[1] if len(mentioned_moves) > 1 else None
            if move is None and historical_focus is not None and not focus_move_uci:
                move = historical_focus.move
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
                    if question_phase == "middlegame":
                        move, precomputed_analysis = self.engine.get_best_move(board)
                    else:
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
                plan_analysis = None
            else:
                san = board.san(move)
                theory_moves = (
                    () if question_phase == "middlegame" else self.openings.theory_moves(board)
                )
                theory_match = move.uci() in {candidate.uci for candidate in theory_moves}
                comparison = (
                    self.engine.compare_moves(
                        board,
                        count=4,
                        focus_move=move,
                        required_moves=(comparison_move,) if comparison_move else (),
                        deep=True,
                    )
                    if deep
                    else self.engine.compare_moves(
                        board,
                        count=3,
                        focus_move=move,
                        required_moves=(comparison_move,) if comparison_move else (),
                    )
                )
                plan_method = getattr(self.engine, "analyze_plan_branches", None)
                plan_analysis = plan_method(board, move) if deep and plan_method else None
                analysis = StockfishService.analysis_from_comparison(board, move, comparison)
                if not analysis.available:
                    analysis = precomputed_analysis or self.engine.analyze_move(board, move)
                projected = board.copy(stack=False)
                projected.push(move)
                opening = self.openings.identify(projected, context_opening)
                fallback, answer_facts, explanation_sections = self._question_fallback(
                    board,
                    san,
                    move,
                    theory_match,
                    analysis,
                    comparison,
                    opening,
                    plan_analysis=plan_analysis,
                    preferred_alternative=comparison_move,
                    deep=deep,
                )
                selection_facts = {
                    "task": (
                        "Erkläre den mittel- und langfristigen Nutzen des Zuges anhand einer "
                        "vertieften Analyse."
                        if deep
                        else "Beantworte die Rückfrage zur aktuellen Stellung."
                    ),
                    "user_question": clean_question,
                    "fen": board.fen(),
                    "side_to_move": "white" if board.turn == chess.WHITE else "black",
                    "focus_move": {"uci": move.uci(), "san": san},
                    "opening": asdict(opening) if opening else None,
                    "theory_match": theory_match,
                    "theory_moves": [candidate.san for candidate in theory_moves[:5]],
                    "engine": asdict(analysis),
                    "engine_comparison": asdict(comparison),
                    "plan_branches": asdict(plan_analysis) if plan_analysis else None,
                    "answer_facts": answer_facts,
                    "analysis_mode": "deep" if deep else "standard",
                }
                text = fallback

            immediate_tactic = next(
                (
                    str(fact["text"])
                    for fact in answer_facts
                    if fact.get("id") == "immediate_material_tactic"
                ),
                None,
            )
            if immediate_tactic:
                # A directly provable one-ply material loss answers the learner's
                # question more precisely than broad opening prose or LLM selection.
                # Keep this path short, deterministic, and free of book retrieval.
                text = TutorText(
                    summary=immediate_tactic,
                    details=text.details,
                    source="deterministic",
                    model=None,
                )
                perspective_filtered = 0
                knowledge_status = "no_evidence"
                knowledge_reason = "immediate_tactic_takes_priority"
            else:
                book_evidence = self.book_knowledge.retrieve(
                    question=clean_question,
                    board=board,
                    opening=opening,
                    focus_move=move,
                )
                if selection_facts is not None:
                    text = self.tutor.answer_question(selection_facts, text)

                relevant_book_facts = _relevant_book_facts(
                    book_evidence.facts,
                    board=board,
                    focus_move=move,
                    question=clean_question,
                )
                perspective_filtered = len(book_evidence.facts) - len(relevant_book_facts)
                synthesis = self.tutor.synthesize_book_explanation(
                    question=clean_question,
                    verified_facts=_book_synthesis_facts(answer_facts),
                    book_facts=[
                        {
                            "id": fact.id,
                            "text": fact.text,
                            "claim_type": fact.claim_type,
                            "validation_status": fact.validation_status,
                            "match_kind": fact.match_kind,
                        }
                        for fact in relevant_book_facts
                    ],
                )
                knowledge_status = synthesis.status
                knowledge_reason = (
                    "opponent_plan_not_relevant_to_focus_move"
                    if perspective_filtered and not relevant_book_facts
                    else synthesis.reason or book_evidence.reason
                )
                used_evidence_ids = synthesis.evidence_ids
                if synthesis.text:
                    book_text = synthesis.text
                    text = TutorText(
                        summary=text.summary,
                        details=text.details,
                        source=book_text.source,
                        model=book_text.model,
                    )
                    explanation_sections.insert(
                        0,
                        {
                            "title": "Buchgestützter Plan",
                            # The deterministic sections already contain the verified
                            # board effects. Keep the book layer to its actual source
                            # idea instead of repeating those effects a second time.
                            "text": book_text.summary,
                        },
                    )
                elif not _has_supported_explanation(answer_facts, explanation_sections):
                    limitation = (
                        "Ich kann den Zug schachlich bewerten, habe aber noch keine ausreichend "
                        "belegte Erklärung für seinen langfristigen Zweck."
                    )
                    text = TutorText(
                        summary=f"{text.summary} {limitation}",
                        details=text.details,
                        source=text.source,
                        model=text.model,
                    )
                    explanation_sections.insert(
                        0,
                        {"title": "Wissensgrenze", "text": limitation},
                    )

            explanation_sections = _deduplicate_explanation_sections(
                text.summary, explanation_sections
            )

            used_facts = [
                fact for fact in book_evidence.facts if fact.id in set(used_evidence_ids)
            ]
            references: list[dict[str, Any]] = []
            seen_references: set[str] = set()
            for fact in used_facts:
                if fact.citation.source_ref in seen_references:
                    continue
                seen_references.add(fact.citation.source_ref)
                references.append(fact.public_reference())

            message = {
                "kind": "question",
                "actor": "coach",
                "question": display_question,
                "move": san,
                "move_uci": move.uci() if move else None,
                "summary": text.summary,
                "details": text.details,
                "source": text.source,
                "model": text.model,
                "attempt": None,
                "engine": asdict(analysis) if analysis else None,
                "explanation_sections": explanation_sections,
                "analysis_mode": "deep" if deep else "standard",
                "references": references,
                "knowledge": {
                    "status": knowledge_status,
                    "reason": knowledge_reason,
                    "evidence_count": len(book_evidence.facts),
                    "perspective_filtered_count": perspective_filtered,
                    "used_evidence_ids": list(used_evidence_ids),
                },
                "opening": asdict(opening) if opening else None,
            }
            self._prepare_message(message, board.fen())
            session.message_history.append(message)
            return {"message": message, "message_history": session.message_history}

    def rate_explanation(
        self,
        session_id: str,
        message_id: str,
        rating: str,
        note: str = "",
    ) -> dict[str, Any]:
        """Persist the learner's judgment and the exact explanation context."""

        if rating not in {"helpful", "unclear", "wrong"}:
            raise ValueError("Unbekannte Erklärungsbewertung")
        session = self._session(session_id)
        with session.lock:
            message = next(
                (
                    candidate
                    for candidate in session.message_history
                    if candidate.get("message_id") == message_id
                ),
                None,
            )
            if message is None:
                raise KeyError("Diese Erklärung gehört nicht mehr zur aktiven Sitzung")

            opening = message.get("opening")
            if not isinstance(opening, dict):
                opening = asdict(session.opening) if session.opening else {}
            stored = self.store.record_explanation_feedback(
                {
                    "session_id": session.session_id,
                    "message_id": message_id,
                    "rating": rating,
                    "note": note.strip(),
                    "position_fen": message.get("position_fen") or session.board.fen(),
                    "opening_eco": opening.get("eco"),
                    "opening_name": opening.get("name"),
                    "message_kind": message.get("kind", "move"),
                    "actor": message.get("actor", "coach"),
                    "question": message.get("question"),
                    "move_uci": message.get("move_uci"),
                    "move_san": message.get("move"),
                    "summary_snapshot": message.get("summary", ""),
                    "details_snapshot": message.get("details", ""),
                    "explanation_sections_payload": json.dumps(
                        message.get("explanation_sections") or [], ensure_ascii=False
                    ),
                    "source": message.get("source", "unknown"),
                    "llm_model": message.get("model"),
                    "engine_payload": _json_payload(message.get("engine")),
                    "references_payload": json.dumps(
                        message.get("references") or [], ensure_ascii=False
                    ),
                    "knowledge_payload": _json_payload(message.get("knowledge")),
                }
            )
            receipt = _feedback_receipt(stored)
            message["feedback"] = receipt
            return receipt

    def explanation_feedback(
        self, *, rating: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Expose locally stored feedback as fixture-ready structured records."""

        if rating is not None and rating not in {"helpful", "unclear", "wrong"}:
            raise ValueError("Unbekannte Erklärungsbewertung")
        rows = self.store.explanation_feedback(rating=rating, limit=limit)
        return [_decode_feedback_row(row) for row in rows]

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
    def _mentioned_legal_moves(board: chess.Board, question: str) -> list[chess.Move]:
        matches: list[tuple[int, chess.Move]] = []
        matches.extend(_described_coordinate_moves(board, question))
        for move in board.legal_moves:
            san = board.san(move).rstrip("+#")
            if match := re.search(
                rf"(?<![A-Za-z0-9]){re.escape(san)}(?![A-Za-z0-9])", question, re.I
            ):
                matches.append((match.start(), move))
            if (uci_position := question.lower().find(move.uci().lower())) >= 0:
                matches.append((uci_position, move))
        ordered: list[chess.Move] = []
        for _, move in sorted(matches, key=lambda item: item[0]):
            if move not in ordered:
                ordered.append(move)
        return ordered

    @staticmethod
    def _move_notation_clarification(
        board: chess.Board, question: str
    ) -> MoveNotationClarification | None:
        """Ask before resolving contradictory piece letters from coordinates."""

        for match in _MOVE_DESCRIPTION_PATTERN.finditer(question):
            from_square = chess.parse_square(match.group("from_square").lower())
            to_square = chess.parse_square(match.group("to_square").lower())
            candidates = [
                move
                for move in board.legal_moves
                if move.from_square == from_square and move.to_square == to_square
            ]
            if len(candidates) != 1:
                continue
            move = candidates[0]
            moving_piece = board.piece_at(from_square)
            target_piece = board.piece_at(to_square)
            if moving_piece is None:
                continue
            from_designator = match.group("from_piece")
            to_designator = match.group("to_piece")
            from_mismatch = bool(
                from_designator
                and _piece_type_for_designator(from_designator) != moving_piece.piece_type
            )
            to_mismatch = bool(
                to_designator
                and target_piece
                and _piece_type_for_designator(to_designator) != target_piece.piece_type
            )
            if not from_mismatch and not to_mismatch:
                continue

            san = board.san(move)
            mover = _piece_name_singular(moving_piece)
            target = (
                _piece_name_singular(target_piece) if target_piece else "Figur"
            )
            corrected = f"{question[:match.start()]}{san}{question[match.end():]}"
            return MoveNotationClarification(
                original_question=question,
                corrected_question=corrected,
                move_uci=move.uci(),
                move_san=san,
                fen=board.fen(),
                prompt=(
                    f"Meinst du {san} – also, dass dein {mover} von "
                    f"{match.group('from_square').lower()} den {target} auf "
                    f"{match.group('to_square').lower()} schlägt?"
                ),
                explanation=(
                    "In der internationalen Notation steht K für King (König) und N für "
                    "Knight (Springer). Antworte einfach mit „ja“, wenn ich diesen Zug prüfen soll."
                ),
            )
        return None

    @staticmethod
    def _mentioned_legal_move(board: chess.Board, question: str) -> chess.Move | None:
        moves = CoachService._mentioned_legal_moves(board, question)
        return moves[0] if moves else None

    def _historical_learner_focus(
        self, session: GameSession, question: str
    ) -> HistoricalMoveContext | None:
        """Resolve questions about an already played learner move.

        The live board is normally two plies beyond the learner's move because the
        coach has already replied. A SAN token such as ``b3`` is therefore no
        longer legal on the live board. Replaying the verified transition messages
        lets the question be analysed in the position where the move was actually
        made instead of silently falling back to an unrelated current suggestion.
        """

        replay = chess.Board()
        opening: OpeningIdentity | None = None
        phase = "opening"
        explicit_matches: list[tuple[int, HistoricalMoveContext]] = []
        last_learner: HistoricalMoveContext | None = None
        for message in session.message_history:
            if (
                message.get("kind") == "phase"
                and "Mittelspiel" in str(message.get("summary") or "")
            ):
                phase = "middlegame"
            move_uci = message.get("move_uci")
            fen_after = message.get("fen_after")
            if not move_uci or not fen_after:
                continue
            try:
                move = chess.Move.from_uci(str(move_uci))
            except (chess.InvalidMoveError, ValueError):
                continue
            if move not in replay.legal_moves:
                # Sessions normally start from the initial position. If a future
                # training mode starts from a custom FEN, fail closed instead of
                # associating the question with the wrong historical position.
                continue
            before = replay.copy(stack=False)
            context = HistoricalMoveContext(before, move, opening, phase)
            if message.get("actor") == "learner":
                last_learner = context
                labels = {
                    str(message.get("move") or "").rstrip("+#"),
                    move.uci(),
                    before.san(move).rstrip("+#"),
                }
                for label in labels - {""}:
                    match = re.search(
                        rf"(?<![A-Za-z0-9]){re.escape(label)}(?![A-Za-z0-9])",
                        question,
                        re.I,
                    )
                    if match:
                        explicit_matches.append((match.start(), context))
                        break
            replay.push(move)
            opening = self.openings.identify(replay, opening)

        if explicit_matches:
            return min(explicit_matches, key=lambda item: item[0])[1]

        return last_learner if self._refers_to_own_past_move(question) else None

    @staticmethod
    def _refers_to_own_past_move(question: str) -> bool:
        return bool(
            re.search(
            r"\b(?:mein(?:e|en|em|er)?\s+(?:(?:letzte|letzten|letzter|vorige|vorigen|"
            r"voriger)\s+)?zug|(?:letzte|letzten|letzter|vorige|vorigen|voriger)\s+zug|"
            r"warum\s+war\b|ungena[uü]igkeit|mein(?:e|en)?\s+fehler)\b",
            question,
            re.I,
            )
        )

    @staticmethod
    def _recent_unaccepted_learner_move(session: GameSession) -> chess.Move | None:
        """Return the latest legal retry move while the board is still unchanged."""

        for message in reversed(session.message_history):
            if message.get("actor") != "learner":
                continue
            if message.get("fen_after"):
                return None
            san = str(message.get("move") or "")
            if not san:
                continue
            try:
                move = session.board.parse_san(san)
            except (
                chess.IllegalMoveError,
                chess.InvalidMoveError,
                chess.AmbiguousMoveError,
                ValueError,
            ):
                continue
            return move if move in session.board.legal_moves else None
        return None

    def _question_fallback(
        self,
        board: chess.Board,
        san: str,
        move: chess.Move,
        theory_match: bool,
        analysis: MoveAnalysis,
        comparison: MoveComparison,
        opening: OpeningIdentity | None,
        *,
        plan_analysis: MovePlanAnalysis | None = None,
        preferred_alternative: chess.Move | None = None,
        deep: bool = False,
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
        response_text = _move_response_context(board, move)
        immediate_tactic_text = _newly_exposed_valuable_piece_context(board, move)
        defender_pressure_text = _defender_pressure_context(board, move)
        development_text = _development_context(board, move)
        concept_text = _useful_move_concept(
            board,
            move,
            analysis,
            defender_pressure_text=defender_pressure_text,
        )
        heuristic_text = _heuristic_context(board, move)
        board_changes_text = _concrete_board_changes(board, move)
        continuation_text = _continuation_context(board, move, analysis)
        contrast_text = _tactical_contrast(board, move, analysis)
        plan_text = _strategic_plan_text(board, move, comparison)
        if analysis.loss_pawns is not None and analysis.loss_pawns >= 0.15:
            # A recovery line after an inferior move is not evidence that the
            # move itself serves that plan. Keep the explanation on the loss and
            # the comparison instead of reverse-engineering a justification.
            plan_text = ""
        recurring_text = (
            _cross_branch_plan_text(board, move, plan_analysis)
            if deep and plan_analysis
            else _recurring_plan_text(board, comparison)
        )
        comparison_text = _candidate_comparison_text(
            board,
            move,
            analysis,
            comparison,
            preferred_alternative=preferred_alternative,
        )
        engine_lines_text = _candidate_lines_text(move, analysis, comparison)
        pv_moves = " ".join(analysis.played_pv_san[:4])
        pv_text = f"Eine kurze Stockfish-Prüfvariante beginnt mit: {pv_moves}." if pv_moves else ""
        if (
            analysis.available
            and analysis.loss_pawns is not None
            and analysis.loss_pawns >= 0.15
            and analysis.best_move_san
        ):
            verdict_text = (
                f"{san} ist in dieser Analyse nicht der beste Zug; Stockfish bevorzugt "
                f"{analysis.best_move_san}."
            )
        elif (
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
        elif (
            analysis.available
            and analysis.loss_pawns is not None
            and analysis.loss_pawns < 0.15
            and analysis.best_move_san
        ):
            verdict_text = (
                f"Stockfish bewertet {san} praktisch gleichwertig mit "
                f"{analysis.best_move_san}."
            )
        else:
            verdict_text = f"{san} ist hier eine legale Alternative."

        fact_values = (
            ("focus", f"Ich beziehe deine Frage auf {san}.", False),
            ("verdict", verdict_text, False),
            ("immediate_material_tactic", immediate_tactic_text, True),
            ("plan", plan_text, True),
            ("recurring_plan", recurring_text, deep),
            ("concept", concept_text, not plan_text),
            ("direct_threat", response_text, True),
            ("defender_pressure", defender_pressure_text, True),
            ("heuristic", heuristic_text, True),
            ("development", development_text, True),
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
            {
                "id": fact_id,
                "text": text,
                "required": required,
                "summary_eligible": fact_id
                in {
                    "verdict",
                    "immediate_material_tactic",
                    "plan",
                    "direct_threat",
                    "heuristic",
                    "development",
                },
            }
            for fact_id, text, required in fact_values
            if text
        ]
        fallback = TutorText(
            summary=(
                immediate_tactic_text
                or f"Ich beziehe deine Frage auf {san}. {verdict_text}"
            ),
            details=" ".join(
                part
                for part in (
                    immediate_tactic_text,
                    response_text,
                    defender_pressure_text,
                    heuristic_text,
                    development_text,
                    plan_text,
                    recurring_text,
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
                immediate_tactic_text,
                response_text,
                defender_pressure_text,
                heuristic_text,
                development_text,
                concept_text,
                board_changes_text,
                continuation_text,
                contrast_text,
            )
            if part
        )
        plan_section = plan_text or development_text or (
            "Aus den geprüften Varianten lässt sich kein einzelner stabiler Langzeitplan "
            "belegen. Ich beschränke mich deshalb auf die konkreten Folgen unten."
        )
        if immediate_tactic_text:
            explanation_sections = [
                {"title": "Sofortige taktische Folge", "text": immediate_tactic_text}
            ]
        else:
            explanation_sections = [
                {"title": "Mittel- und langfristiger Plan", "text": plan_section},
            ]
        if deep:
            explanation_sections.append(
                {
                    "title": "Was gegen mehrere Antworten stabil bleibt",
                    "text": recurring_text
                    or "Die geprüften Antworten führen zu unterschiedlichen Plänen. "
                    "Stockfish zeigt hier kein wiederkehrendes Motiv, das eine sichere "
                    "Langzeitbegründung tragen würde.",
                }
            )
        if concrete_text:
            explanation_sections.append(
                {"title": "Konkrete Wirkung in der Stellung", "text": concrete_text}
            )
        explanation_sections.extend(
            [
                {
                    "title": "Vergleich mit der besten Alternative",
                    "text": comparison_text
                    or "Für einen belastbaren Alternativenvergleich fehlen Engine-Kandidaten.",
                },
                {
                    "title": "Stockfish-Rechenwege",
                    "text": (
                        _plan_branch_lines_text(plan_analysis)
                        if deep and plan_analysis and plan_analysis.available
                        else engine_lines_text or pv_text or quality_text
                    ),
                },
            ]
        )
        return fallback, answer_facts, explanation_sections

    def _play_coach_move(self, session: GameSession) -> dict[str, Any]:
        board = session.board
        fen_before = board.fen()
        theory_moves = () if session.phase == "middlegame" else self.openings.theory_moves(board)
        analysis: MoveAnalysis | None = None
        if session.phase == "middlegame":
            move, analysis = self.engine.get_best_move(board)
        else:
            move = self._weighted_theory_move(theory_moves)
        if move is None:
            legal = list(board.legal_moves)
            move = self.rng.choice(legal)
        analysis = analysis or self.engine.analyze_move(board, move)
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
        opening = opening_after.name if opening_after else None
        if session.phase == "middlegame":
            summary = (
                f"Ich spiele {san}. Stockfish bevorzugt diesen Zug in der Mittelspielstellung."
                if analysis.available
                else f"Ich spiele {san}. Wir setzen die Stellung als Mittelspiel fort."
            )
        else:
            opening_changed = bool(
                opening and (session.opening is None or opening != session.opening.name)
            )
            if opening_changed and len(session.move_history) <= 1:
                summary = f"Ich spiele {san}. Mit diesem Zug beginnt die Eröffnung „{opening}“."
            elif opening_changed:
                summary = f"Ich spiele {san}. Damit geht die Partie in „{opening}“ über."
            elif opening:
                summary = f"Ich spiele {san}. Der Zug führt die Eröffnung „{opening}“ weiter."
            else:
                summary = f"Ich spiele {san}. Das ist ein solider Eröffnungszug."
        fallback = TutorText(
            summary=summary,
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
            "kind": "move",
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
            "kind": "move",
            "actor": actor,
            "move": san,
            "summary": text.summary,
            "details": text.details,
            "source": text.source,
            "model": text.model,
            "attempt": None,
            "engine": facts["engine"],
            "opening": facts.get("opening"),
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
            "task": (
                "Erkläre den gerade gespielten Mittelspielzug."
                if session.phase == "middlegame"
                else "Erkläre den gerade gespielten Eröffnungszug."
            ),
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
        response_text = _move_response_context(board, move)
        defender_pressure_text = _defender_pressure_context(board, move)
        development_text = _development_context(board, move)
        return " ".join(
            part
            for part in (
                response_text,
                defender_pressure_text,
                _heuristic_context(board, move),
                development_text,
                _single_line_plan_context(board, move, analysis),
                _useful_move_concept(
                    board,
                    move,
                    analysis,
                    defender_pressure_text=defender_pressure_text,
                ),
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
        self._prepare_message(message, fen_before)
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

    @staticmethod
    def _prepare_message(message: dict[str, Any], position_fen: str) -> None:
        message.setdefault("message_id", str(uuid.uuid4()))
        message.setdefault("position_fen", position_fen)
        message.setdefault("feedback", None)

    def _save_turn_snapshot(self, session: GameSession) -> None:
        session.undo_stack.append(
            TurnSnapshot(
                fen=session.board.fen(),
                opening=session.opening,
                move_history_length=len(session.move_history),
                message_history_length=len(session.message_history),
                interaction_id=self.store.latest_interaction_id(session.session_id),
                phase=session.phase,
                opening_end=session.opening_end,
            )
        )

    def _response(
        self,
        session: GameSession,
        *,
        messages: list[dict[str, Any]],
        correction: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        completed_turn = any(
            message.get("actor") == "coach" and message.get("move_uci") for message in messages
        )
        should_check_phase = completed_turn or (
            session.board.is_game_over() and any(message.get("move_uci") for message in messages)
        )
        if session.phase == "opening" and correction is None and should_check_phase:
            evidence = self._opening_end_evidence(session)
            if evidence.likely:
                session.phase = "transition"
                session.opening_end = evidence
                messages.append(self._opening_end_message(evidence))
        for message in messages:
            self._prepare_message(message, session.board.fen())
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
            "phase": session.phase,
            "opening_end": asdict(session.opening_end)
            if session.phase == "transition" and session.opening_end
            else None,
            "opening_summary": session.opening_summary,
        }

    def _opening_end_evidence(self, session: GameSession) -> OpeningEndEvidence:
        board = session.board
        plies = len(session.move_history)
        theory_exhausted = not self.openings.theory_moves(board)
        developed_minors = _minor_pieces_off_starting_squares(board)
        castled = any(move["san"].startswith("O-O") for move in session.move_history)
        center_pawns_moved = _center_pawns_off_starting_squares(board)
        enough_history = plies >= 12
        extended_history = plies >= 20

        signals = (
            {
                "id": "theory",
                "label": (
                    "Die lokale Eröffnungstheorie enthält hier keine Fortsetzung mehr."
                    if theory_exhausted
                    else "Die Stellung liegt noch in einer bekannten lokalen Eröffnungslinie."
                ),
                "met": theory_exhausted,
            },
            {
                "id": "development",
                "label": (
                    f"{developed_minors} von 8 leichten Figuren stehen nicht mehr auf ihrem "
                    "Ausgangsfeld."
                ),
                "met": developed_minors >= 5,
            },
            {
                "id": "king_safety",
                "label": (
                    "Mindestens eine Seite hat rochiert."
                    if castled
                    else "Noch keine Seite hat rochiert."
                ),
                "met": castled,
            },
            {
                "id": "center",
                "label": (
                    f"{center_pawns_moved} von 4 d- und e-Bauern haben ihr Ausgangsfeld verlassen."
                ),
                "met": center_pawns_moved >= 3,
            },
            {
                "id": "move_count",
                "label": f"Die Partie umfasst inzwischen {plies} Halbzüge.",
                "met": enough_history,
            },
        )
        score = (
            (2 if theory_exhausted else 0)
            + (1 if developed_minors >= 5 else 0)
            + (1 if castled else 0)
            + (1 if center_pawns_moved >= 3 else 0)
            + (1 if plies >= 18 else 0)
        )
        game_over = board.is_game_over()
        likely = (
            game_over or (enough_history and score >= 4) or (extended_history and theory_exhausted)
        )
        if game_over:
            headline = "Die Partie ist beendet – Zeit für die Eröffnungsauswertung."
            explanation = (
                "Unabhängig von der üblichen Phasengrenze können wir jetzt festhalten, was du "
                "aus den ersten Zügen mitnehmen solltest."
            )
        elif likely:
            headline = "Die Eröffnungsphase ist wahrscheinlich vorbei."
            met_labels = [signal["label"] for signal in signals if signal["met"]][:3]
            explanation = " ".join(met_labels) + (
                " Die Grenze ist fließend; deshalb entscheidest du, ob wir weiterspielen oder "
                "jetzt auswerten."
            )
        else:
            headline = "Die Stellung befindet sich wahrscheinlich noch in der Eröffnungsphase."
            explanation = "Für einen Phasenwechsel reichen die beobachteten Signale noch nicht."
        return OpeningEndEvidence(
            likely=likely,
            headline=headline,
            explanation=explanation,
            signals=signals,
            can_continue=not game_over,
        )

    @staticmethod
    def _opening_end_message(evidence: OpeningEndEvidence) -> dict[str, Any]:
        return {
            "kind": "phase",
            "actor": "coach",
            "move": None,
            "summary": evidence.headline,
            "details": evidence.explanation,
            "source": "verified-phase-heuristic",
            "model": None,
            "attempt": None,
            "engine": None,
        }

    def _build_opening_summary(self, session: GameSession) -> dict[str, Any]:
        interactions = self.store.session_interactions(session.session_id)
        learner_rows = [row for row in interactions if row["actor"] == "learner"]
        accepted_rows = [row for row in learner_rows if row["accepted"]]
        correction_rows = [row for row in learner_rows if not row["accepted"]]
        theory_rows = [row for row in accepted_rows if row["theory_match"] == 1]
        sound_rows = [
            row
            for row in accepted_rows
            if row["engine_loss"] is not None and float(row["engine_loss"]) < 0.15
        ]
        learner_is_white = session.learner_color == chess.WHITE
        learner_moves = [move for move in session.move_history if move["actor"] == "learner"]
        learner_developed = _learner_minor_development(interactions, session.learner_color)
        learner_castled = any(move["san"].startswith("O-O") for move in learner_moves)
        learner_center_pawns = _learner_center_pawns_off_start(session.board, session.learner_color)

        concepts = [
            (
                "Zentrum: "
                + (
                    "Beide eigenen d- und e-Bauern haben ihre Ausgangsfelder verlassen."
                    if learner_center_pawns == 2
                    else f"{learner_center_pawns} von 2 eigenen d- und e-Bauern hat sein "
                    "Ausgangsfeld verlassen."
                )
            ),
            (
                f"Entwicklung: {learner_developed} von 4 eigenen Springern und Läufern wurden "
                "mindestens einmal von ihrem Ausgangsfeld gezogen."
            ),
            (
                "Königssicherheit: Du hast in der Eröffnungsphase rochiert."
                if learner_castled
                else "Königssicherheit: Du hast in der Eröffnungsphase noch nicht rochiert."
            ),
        ]

        strengths: list[str] = []
        if theory_rows:
            strengths.append(
                f"{len(theory_rows)} von {len(accepted_rows)} übernommenen Zügen gehörten zu "
                "den lokalen Eröffnungslinien."
            )
        if sound_rows:
            strengths.append(
                f"{len(sound_rows)} übernommene Züge lagen laut Stockfish praktisch auf "
                "Augenhöhe mit dem besten Zug."
            )
        if not correction_rows:
            strengths.append("Du brauchtest in dieser Eröffnungsphase keine Korrekturschleife.")
        if not strengths:
            strengths.append("Du hast die Stellung bis zur Auswertung aktiv weitergespielt.")

        review_points: list[str] = []
        seen_problem_positions: set[tuple[str, str | None]] = set()
        for row in correction_rows:
            key = (row["fen_before"], row["move_san"])
            if key in seen_problem_positions:
                continue
            seen_problem_positions.add(key)
            if not row["legal"]:
                review_points.append(
                    "Ein Zugversuch war nicht legal; prüfe vor dem Loslassen Zielfeld und "
                    "Königssicherheit."
                )
            elif row["move_san"] and row["engine_loss"] is not None:
                loss = f"{float(row['engine_loss']):.2f}".replace(".", ",")
                review_points.append(
                    f"{row['move_san']} musste korrigiert werden; der gemessene Abstand zum "
                    f"besten Zug betrug etwa {loss} Bauerneinheiten."
                )
            elif row["move_san"]:
                review_points.append(f"{row['move_san']} brauchte einen weiteren Versuch.")
            if len(review_points) == 3:
                break

        if not review_points:
            unusual_rows = [
                row
                for row in accepted_rows
                if row["theory_match"] == 0
                and row["engine_loss"] is not None
                and float(row["engine_loss"]) >= 0.15
            ]
            for row in unusual_rows[:2]:
                loss = f"{float(row['engine_loss']):.2f}".replace(".", ",")
                review_points.append(
                    f"{row['move_san']} wich von der lokalen Theorie ab und lag etwa {loss} "
                    "Bauerneinheiten hinter dem besten Engine-Zug."
                )

        recommendation = None
        if correction_rows:
            first_problem = correction_rows[0]
            move_label = first_problem["move_san"] or "dem problematischen Zugversuch"
            recommendation = {
                "title": f"Stellung vor {move_label} noch einmal üben",
                "reason": (
                    "Hier war mindestens ein Korrekturhinweis nötig. Die Wiederholung wird nur "
                    "vorgeschlagen und nicht automatisch gestartet."
                ),
                "fen": first_problem["fen_before"],
            }

        if correction_rows:
            takeaway = (
                "Merksatz: Prüfe vor jedem Eröffnungszug zuerst direkte Drohungen, dann "
                "Entwicklung, Zentrum und Königssicherheit."
            )
        elif not learner_castled:
            takeaway = (
                "Merksatz: Plane nach Zentrum und Figurenentwicklung bewusst die "
                "Königssicherheit ein."
            )
        elif learner_developed < 3:
            takeaway = (
                "Merksatz: Aktiviere mehrere leichte Figuren, bevor du dieselbe Figur "
                "wiederholt ziehst."
            )
        else:
            takeaway = (
                "Merksatz: Eine solide Eröffnung verbindet Zentrum, Entwicklung und "
                "Königssicherheit – nicht nur eine auswendig gelernte Zugfolge."
            )

        return {
            "opening": asdict(session.opening) if session.opening else None,
            "learner_color": "white" if learner_is_white else "black",
            "moves_played": len(session.move_history),
            "learner_moves": len(learner_moves),
            "concepts": concepts,
            "strengths": strengths[:3],
            "review_points": review_points,
            "takeaway": takeaway,
            "recommendation": recommendation,
            "source": "verified-session-data",
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


_MOVE_DESCRIPTION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<from_piece>[KQRBNPSTLD])?\s*"
    r"(?P<from_square>[a-h][1-8])\s*"
    r"(?:x|×|->|→|–|-|nach|auf|schl[aä]gt|nimmt)\s*"
    r"(?P<to_piece>[KQRBNPSTLD])?\s*"
    r"(?P<to_square>[a-h][1-8])"
    r"(?![A-Za-z0-9])",
    re.I,
)


def _piece_type_for_designator(designator: str) -> int | None:
    return {
        "K": chess.KING,
        "Q": chess.QUEEN,
        "D": chess.QUEEN,
        "R": chess.ROOK,
        "T": chess.ROOK,
        "B": chess.BISHOP,
        "L": chess.BISHOP,
        "N": chess.KNIGHT,
        "S": chess.KNIGHT,
        "P": chess.PAWN,
    }.get(designator.upper())


def _described_coordinate_moves(
    board: chess.Board, question: str
) -> list[tuple[int, chess.Move]]:
    """Resolve verbose source/target descriptions only through current legality."""

    described: list[tuple[int, chess.Move]] = []
    for match in _MOVE_DESCRIPTION_PATTERN.finditer(question):
        from_square = chess.parse_square(match.group("from_square").lower())
        to_square = chess.parse_square(match.group("to_square").lower())
        candidates = [
            move
            for move in board.legal_moves
            if move.from_square == from_square and move.to_square == to_square
        ]
        if len(candidates) == 1:
            described.append((match.start(), candidates[0]))
    return described


def _is_affirmative_answer(text: str) -> bool:
    return bool(
        re.fullmatch(
            r"\s*(?:ja|jep|jo|genau|richtig|korrekt|das meine ich|ja bitte)[.!]?\s*",
            text,
            re.I,
        )
    )


def _json_payload(value: Any) -> str | None:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _feedback_receipt(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rating": row["rating"],
        "note": row["note"],
        "updated_at": row["updated_at"],
    }


def _decode_feedback_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    payload_fields = {
        "explanation_sections_payload": "explanation_sections",
        "engine_payload": "engine",
        "references_payload": "references",
        "knowledge_payload": "knowledge",
    }
    for stored_name, public_name in payload_fields.items():
        payload = result.pop(stored_name)
        result[public_name] = json.loads(payload) if payload else None
    return result


def _relevant_book_facts(
    facts: tuple[BookFact, ...],
    *,
    board: chess.Board,
    focus_move: chess.Move | None,
    question: str,
) -> tuple[BookFact, ...]:
    """Drop generic opponent plans that cannot explain the focused side's move."""

    relevant: list[BookFact] = []
    focus_tokens: tuple[str, ...] = ()
    if focus_move and focus_move in board.legal_moves:
        focus_tokens = (board.san(focus_move).rstrip("+#"), focus_move.uci())
    asks_for_focus_rationale = bool(focus_tokens) and (
        any(_contains_chess_token(question, token) for token in focus_tokens)
        or bool(
            re.search(
                r"\bwarum\b.*\b(?:zug|gut|sinnvoll|stark|schlecht|problematisch)\w*\b",
                question,
                re.I,
            )
        )
    )
    for fact in facts:
        if fact.claim_type != "plan":
            relevant.append(fact)
            continue
        if any(_contains_chess_token(fact.text, token) for token in focus_tokens):
            relevant.append(fact)
            continue
        actor = _explicit_plan_actor(fact.text)
        if actor is None:
            if asks_for_focus_rationale and fact.match_kind not in {
                "position",
                "position_after_move",
            }:
                # A generic opening plan with no named side and no focus move
                # cannot answer why this side's concrete move is useful.
                continue
            relevant.append(fact)
            continue
        if actor == board.turn:
            relevant.append(fact)
            continue
        if _question_requests_side(question, actor, focus_side=board.turn):
            relevant.append(fact)
    return tuple(relevant)


def _contains_chess_token(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", text, re.I))


def _explicit_plan_actor(text: str) -> chess.Color | None:
    normalized = text.casefold().replace("’", "'")
    subject_patterns = (
        r"\b(white|black)\s+(?:immediately\s+)?(?:can|could|should|must|aims?|tries|"
        r"intends?|seeks?|plans?|uses?|creates?|plays?|gains?|keeps?|develops?|"
        r"controls?|attacks?|defends?|wants?|has)\b",
        r"\b(wei(?:ß|ss)|schwarz)(?:e|er|en|em)?\s+(?:kann|könnte|sollte|muss|will|"
        r"versucht|plant|spielt|gewinnt|behält|entwickelt|kontrolliert|greift|"
        r"verteidigt|hat)\b",
    )
    for pattern in subject_patterns:
        if match := re.search(pattern, normalized):
            return _named_chess_color(match.group(1))
    context_patterns = (
        r"\b(?:playing|played|starting|started)\s+(?:second\s+)?as\s+(white|black)\b",
        r"\b(?:for|by)\s+(white|black)\b",
        r"\b(white|black)'s\s+(?:plan|strategy|idea|aim)\b",
        r"\b(?:für|von)\s+(wei(?:ß|ss)|schwarz)(?:e|er|en|em)?\b",
        r"\b(wei(?:ß|ss)|schwarz)(?:e|er|en|em)?\s+(?:plan|strategie|idee|ziel)\b",
    )
    for pattern in context_patterns:
        if match := re.search(pattern, normalized):
            return _named_chess_color(match.group(1))
    return None


def _named_chess_color(name: str) -> chess.Color:
    return chess.WHITE if name.startswith(("white", "wei")) else chess.BLACK


def _question_requests_side(
    question: str, side: chess.Color, *, focus_side: chess.Color
) -> bool:
    normalized = question.casefold()
    if side != focus_side and re.search(r"\b(?:gegner|gegnerin|opponent)\w*\b", normalized):
        return True
    pattern = (
        r"\b(?:white|wei(?:ß|ss))\w*\b"
        if side == chess.WHITE
        else r"\b(?:black|schwarz)\w*\b"
    )
    return bool(re.search(pattern, normalized))


def _move_concept(board: chess.Board, move: chess.Move) -> str:
    piece = board.piece_at(move.from_square)
    if piece is None:
        return "Der Zug verändert die Figurenkoordination."
    target = chess.square_name(move.to_square)
    if board.is_castling(move):
        return "Die Rochade bringt den König in Sicherheit und verbindet die Türme."
    if piece.piece_type == chess.PAWN:
        projected = board.copy(stack=False)
        projected.push(move)
        after = _square_list(projected.attacks(move.to_square))
        center = (
            " und besetzt selbst ein Zentrumsfeld"
            if move.to_square in chess.SquareSet(chess.BB_CENTER)
            else ""
        )
        return f"Mit {board.san(move)} kontrolliert der Bauer nun {after}{center}."
    if piece.piece_type == chess.KNIGHT:
        projected = board.copy(stack=False)
        projected.push(move)
        controlled = projected.attacks(move.to_square)
        central = controlled & chess.SquareSet(chess.BB_CENTER)
        occupies_center = move.to_square in chess.SquareSet(chess.BB_CENTER)
        center_text = (
            f" Er steht damit selbst auf dem Zentrumsfeld {target}."
            if occupies_center
            else
            f" Davon {'ist' if len(central) == 1 else 'sind'} {_square_list(central)} "
            f"{'ein Zentrumsfeld' if len(central) == 1 else 'Zentrumsfelder'}."
            if central
            else ""
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
    center_text = (
        f" Von dort kontrolliert {pronoun} direkt {_square_list(central)} im Zentrum."
        if central
        else ""
    )
    attacked_pieces = _attacked_piece_list(projected, move.to_square, board.turn)
    attack_text = f" Außerdem greift {pronoun} {attacked_pieces} an." if attacked_pieces else ""
    return f"Der {piece_name} zieht nach {target}.{center_text}{attack_text}"


def _development_context(board: chess.Board, move: chess.Move) -> str:
    """Explain pawn support and newly freed bishop development from board facts."""

    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type != chess.PAWN:
        return ""
    projected = board.copy(stack=False)
    projected.push(move)
    san = board.san(move)
    supported_pawns = [
        chess.square_name(square)
        for square in projected.attacks(move.to_square)
        if projected.piece_at(square) == chess.Piece(chess.PAWN, board.turn)
    ]
    sentences: list[str] = []
    if supported_pawns:
        pawns = _join_descriptions(
            [f"den eigenen Bauern auf {square}" for square in supported_pawns]
        )
        sentences.append(f"{san} stützt {pawns}.")

    opened_bishops: list[str] = []
    for square in board.pieces(chess.BISHOP, board.turn):
        before = board.attacks(square)
        after = projected.attacks(square)
        newly_reached = after - before - chess.SquareSet([move.from_square])
        useful = [target for target in newly_reached if projected.piece_at(target) is None]
        if useful:
            opened_bishops.append(chess.square_name(square))
    if opened_bishops:
        bishops = _join_descriptions(
            [f"dem Läufer auf {square}" for square in opened_bishops]
        )
        sentences.append(f"Der Zug öffnet {bishops} neue Entwicklungsfelder.")
    return " ".join(sentences)


def _useful_move_concept(
    board: chess.Board,
    move: chess.Move,
    analysis: MoveAnalysis,
    *,
    defender_pressure_text: str,
) -> str:
    """Keep generic geometry only when it adds information that survives the reply."""

    piece = board.piece_at(move.from_square)
    if piece is None:
        return ""
    if _first_reply_captures_focus_piece(board, move, analysis.played_pv_san):
        # A transient square-control list is actively misleading when the main
        # line removes the moved piece immediately. The capture/recapture belongs
        # in the concrete and comparison layers instead.
        return ""
    if defender_pressure_text and piece.piece_type != chess.KNIGHT:
        # The defender-pressure explanation already states the attacked piece
        # and, unlike a generic move description, explains why that attack matters.
        return ""
    return _move_concept(board, move)


def _first_reply_captures_focus_piece(
    board: chess.Board, move: chess.Move, pv_san: tuple[str, ...]
) -> bool:
    if len(pv_san) < 2:
        return False
    replay = board.copy(stack=False)
    try:
        first = replay.parse_san(pv_san[0])
        if first != move:
            return False
        replay.push(first)
        reply = replay.parse_san(pv_san[1])
    except (
        chess.IllegalMoveError,
        chess.InvalidMoveError,
        chess.AmbiguousMoveError,
        ValueError,
    ):
        return False
    if not replay.is_capture(reply):
        return False
    capture_square = reply.to_square
    if replay.is_en_passant(reply):
        capture_square += -8 if replay.turn == chess.WHITE else 8
    return capture_square == move.to_square


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
            moving_color = board.turn
            before = board.attacks(square) - chess.SquareSet(board.occupied_co[moving_color])
            same_piece = projected.piece_at(square)
            if same_piece != chess.Piece(piece_type, board.turn):
                continue
            after = projected.attacks(square) - chess.SquareSet(
                projected.occupied_co[moving_color]
            )
            newly_reached = after - before
            meaningful = chess.SquareSet(
                target
                for target in newly_reached
                if target in chess.SquareSet(chess.BB_CENTER)
                or (
                    (target_piece := projected.piece_at(target)) is not None
                    and target_piece.color != moving_color
                )
            )
            if meaningful:
                opened_lines.append(
                    f"{label} auf {chess.square_name(square)} bis "
                    f"{_limited_square_list(meaningful)}"
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


def _strategic_plan_text(
    board: chess.Board, focus_move: chess.Move, comparison: MoveComparison
) -> str:
    """Turn verified board and PV patterns into a cautious plan-level explanation."""
    if not comparison.available:
        return ""
    focus = next(
        (
            candidate
            for candidate in comparison.candidates
            if candidate.move_uci == focus_move.uci()
        ),
        None,
    )
    if focus is None:
        return ""

    san = board.san(focus_move)
    piece = board.piece_at(focus_move.from_square)
    if piece is None:
        return ""
    projected = board.copy(stack=False)
    projected.push(focus_move)
    reasons: list[str] = []

    if _first_reply_captures_focus_piece(board, focus_move, focus.pv_san):
        reasons.append(
            f"Stockfish rechnet unmittelbar mit {focus.pv_san[0]} {focus.pv_san[1]}; "
            "die gezogene Figur wird dabei sofort geschlagen. Der Nutzen des Zuges muss "
            "deshalb in der entstehenden Stellung liegen, nicht in einer dauerhaften "
            f"Wirkung vom Feld {chess.square_name(focus_move.to_square)}."
        )
        return " ".join(reasons)

    if piece.piece_type == chess.PAWN:
        controlled = projected.attacks(focus_move.to_square)
        restrained_pushes: list[str] = []
        for reply in projected.legal_moves:
            reply_piece = projected.piece_at(reply.from_square)
            if (
                reply_piece
                and reply_piece.piece_type == chess.PAWN
                and reply.to_square in controlled
                and not projected.is_capture(reply)
            ):
                restrained_pushes.append(projected.san(reply))
        if restrained_pushes:
            pushes = _join_descriptions(restrained_pushes[:2])
            reasons.append(
                f"{san} erschwert den gegnerischen Bauernvorstoß {pushes}: Nach diesem "
                "Vorstoß könnte dein Bauer den vorgerückten Bauern schlagen."
            )
        if focus_move.to_square in chess.SquareSet(chess.BB_CENTER):
            reasons.append(
                f"Der Bauer besetzt mit {san} selbst das Zentrum und kann dort Raum für die "
                "Figuren hinter ihm sichern."
            )

    if piece.piece_type == chess.KNIGHT and focus_move.to_square in chess.SquareSet(
        chess.BB_CENTER
    ):
        target = chess.square_name(focus_move.to_square)
        pawn_attackers = [
            square
            for square in projected.attackers(not piece.color, focus_move.to_square)
            if (attacker := projected.piece_at(square))
            and attacker.piece_type == chess.PAWN
        ]
        stability = (
            "Kein gegnerischer Bauer kann ihn dort unmittelbar vertreiben."
            if not pawn_attackers
            else "Der Gegner kann diesen Posten mit einem Bauern infrage stellen."
        )
        reasons.append(
            f"{san} stellt den Springer auf den zentralen Posten {target}. {stability}"
        )

    parsed = _parsed_candidate_line(board, focus)
    if len(parsed) >= 3:
        first_move = parsed[0][1]
        reply_board, reply_move = parsed[1][0], parsed[1][1]
        continuation_board, continuation_move = parsed[2][0], parsed[2][1]
        if (
            reply_board.is_capture(reply_move)
            and reply_move.to_square == first_move.to_square
            and continuation_board.is_capture(continuation_move)
            and continuation_move.to_square == first_move.to_square
        ):
            reasons.append(
                f"Stockfish rechnet mit dem klärenden Abtausch {focus.pv_san[1]} "
                f"{focus.pv_san[2]}; danach übernimmt eine andere eigene Figur den Posten "
                f"{chess.square_name(first_move.to_square)}."
            )

    all_focus_followups = list(dict.fromkeys(focus.pv_san[2::2]))
    focus_followups = list(
        dict.fromkeys(
            focus.pv_san[index]
            for index, (position, pv_move) in enumerate(parsed)
            if index >= 2 and index % 2 == 0 and not position.is_capture(pv_move)
        )
    )
    for alternative in comparison.candidates:
        if alternative.move_uci == focus.move_uci:
            continue
        alternative_followups = list(dict.fromkeys(alternative.pv_san[2::2]))
        if (
            alternative.move_san in all_focus_followups
            and focus.move_san in alternative_followups
        ):
            reasons.append(
                f"Die Varianten behandeln {focus.move_san} und {alternative.move_san} als "
                "flexible Zugreihenfolge: Jeder der beiden Züge folgt in der Berechnung auf "
                "den anderen. Es geht daher eher um den gemeinsamen Aufbau als um einen "
                "einzigen zwingenden Moment."
            )
            break

    if focus_followups:
        followups = _join_descriptions(focus_followups[:3])
        side = "Weiß" if board.turn == chess.WHITE else "Schwarz"
        reasons.append(
            f"In der geprüften Fortsetzung baut {side} danach mit {followups} weiter auf. "
            "Das ist ein Modellplan und keine erzwungene Zugfolge."
        )
    return " ".join(reasons)


def _single_line_plan_context(
    board: chess.Board, move: chess.Move, analysis: MoveAnalysis
) -> str:
    if not analysis.available or not analysis.played_pv_san:
        return ""
    candidate = CandidateAnalysis(
        move_uci=move.uci(),
        move_san=board.san(move),
        evaluation=analysis.evaluation_played or 0.0,
        mate=analysis.mate_played,
        loss_pawns=analysis.loss_pawns or 0.0,
        pv_san=analysis.played_pv_san,
    )
    comparison = MoveComparison(
        available=True,
        engine_name=analysis.engine_name,
        candidates=(candidate,),
    )
    return _strategic_plan_text(board, move, comparison)


def _recurring_plan_text(board: chess.Board, comparison: MoveComparison) -> str:
    """Report future moves recurring across independent candidate lines."""
    if not comparison.available or len(comparison.candidates) < 2:
        return ""
    candidates = comparison.candidates
    occurrences: Counter[str] = Counter()
    for candidate in candidates:
        occurrences.update(set(candidate.pv_san[2::2]))
    recurring = [
        (move, count)
        for move, count in occurrences.most_common()
        if count >= 2 and "x" not in move and "+" not in move
    ][:3]
    if not recurring:
        return ""
    side = "Weiß" if board.turn == chess.WHITE else "Schwarz"
    motifs = _join_descriptions(
        [f"{move} in {count} von {len(candidates)} Varianten" for move, count in recurring]
    )
    return (
        f"Mehrere unabhängig berechnete Kandidaten führen für {side} später zu {motifs}. "
        "Solche Wiederholungen sind ein belastbareres Indiz für den geplanten Aufbau als "
        "eine einzelne lange Engine-Variante."
    )


def _cross_branch_plan_text(
    board: chess.Board,
    focus_move: chess.Move,
    plan: MovePlanAnalysis,
) -> str:
    """Explain motifs that survive several plausible replies to the focus move."""
    if not plan.available or len(plan.branches) < 2:
        return ""
    branch_count = len(plan.branches)
    recurring_moves: Counter[str] = Counter()
    focus_piece_relocations = 0
    moving_piece = board.piece_at(focus_move.from_square)
    for branch in plan.branches:
        own_followups = set(branch.pv_san[2::2])
        recurring_moves.update(
            san for san in own_followups if "x" not in san and "+" not in san
        )
        if moving_piece and _focus_piece_moves_again(board, focus_move, branch.pv_san):
            focus_piece_relocations += 1

    stable = [
        (san, count)
        for san, count in recurring_moves.most_common()
        if count >= 2
    ][:3]
    sentences = [
        f"Stockfish hat nach {board.san(focus_move)} {branch_count} plausible gegnerische "
        "Antworten getrennt geprüft."
    ]
    if stable:
        descriptions = _join_descriptions(
            [f"{san} in {count} von {branch_count} Varianten" for san, count in stable]
        )
        sentences.append(
            f"Für deine Seite kehrt danach {descriptions} wieder. Das ist ein vorsichtiger "
            "Hinweis auf einen robusten Folgeplan, keine erzwungene Zugfolge."
        )
    if focus_piece_relocations >= 2:
        sentences.append(
            f"In {focus_piece_relocations} von {branch_count} Varianten zieht dieselbe Figur "
            "später noch einmal weiter; das Zielfeld ist daher eher eine Zwischenstation als "
            "der endgültige Posten."
        )
    if len(sentences) == 1:
        return ""
    return " ".join(sentences)


def _focus_piece_moves_again(
    board: chess.Board, focus_move: chess.Move, pv_san: tuple[str, ...]
) -> bool:
    if not pv_san:
        return False
    replay = board.copy(stack=False)
    tracked_square = focus_move.from_square
    for index, san in enumerate(pv_san):
        try:
            move = replay.parse_san(san)
        except (
            chess.IllegalMoveError,
            chess.InvalidMoveError,
            chess.AmbiguousMoveError,
            ValueError,
        ):
            return False
        if index == 0:
            if move != focus_move:
                return False
            tracked_square = move.to_square
        elif replay.turn == board.turn and move.from_square == tracked_square:
            return True
        if move.to_square == tracked_square and replay.is_capture(move):
            return False
        replay.push(move)
    return False


def _plan_branch_lines_text(plan: MovePlanAnalysis) -> str:
    if not plan.available or not plan.branches:
        return plan.reason or "Keine vertieften Antwortvarianten verfügbar."
    lines = []
    for branch in plan.branches:
        evaluation = _format_evaluation(branch.evaluation, branch.mate)
        pv = " ".join(branch.pv_san[:8])
        lines.append(f"Nach {branch.reply_san} ({evaluation}): {pv}.")
    return (
        "Bewertungen aus weißer Sicht; + bedeutet Vorteil für Weiß. "
        + " ".join(lines)
    )


def _parsed_candidate_line(
    board: chess.Board, candidate: CandidateAnalysis
) -> list[tuple[chess.Board, chess.Move]]:
    replay = board.copy(stack=False)
    parsed: list[tuple[chess.Board, chess.Move]] = []
    for san in candidate.pv_san:
        try:
            move = replay.parse_san(san)
        except (
            chess.IllegalMoveError,
            chess.InvalidMoveError,
            chess.AmbiguousMoveError,
            ValueError,
        ):
            break
        parsed.append((replay.copy(stack=False), move))
        replay.push(move)
    return parsed


def _candidate_comparison_text(
    board: chess.Board,
    focus_move: chess.Move,
    focus_analysis: MoveAnalysis,
    comparison: MoveComparison,
    *,
    preferred_alternative: chess.Move | None = None,
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
    explicitly_requested = next(
        (
            candidate
            for candidate in candidates
            if preferred_alternative
            and candidate.move_uci == preferred_alternative.uci()
            and candidate.move_uci != focus.move_uci
        ),
        None,
    )
    if explicitly_requested is not None:
        alternative = explicitly_requested
        raw_gap = (
            alternative.evaluation - focus.evaluation
            if board.turn == chess.WHITE
            else focus.evaluation - alternative.evaluation
        )
        gap = abs(round(raw_gap, 2))
        relation = "stärker" if raw_gap > 0 else "schwächer" if raw_gap < 0 else "gleich"
        comparison_intro = (
            f"Der ausdrücklich genannte Vergleichszug {alternative.move_san} wird von "
            f"Stockfish um {_format_pawns(gap)} Bauerneinheiten {relation} bewertet als "
            f"{focus.move_san}."
        )
    elif focus.move_uci == best.move_uci:
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
    if _first_reply_captures_focus_piece(board, focus_move, focus.pv_san):
        focus_effects["new_targets"] = ""
        focus_effects["central_squares"] = ""
    try:
        alternative_move = chess.Move.from_uci(alternative.move_uci)
    except (chess.InvalidMoveError, ValueError):
        alternative_move = None
    alternative_effects = (
        _move_effects(board, alternative_move)
        if alternative_move is not None and alternative_move in board.legal_moves
        else None
    )
    if (
        alternative_effects is not None
        and alternative_move is not None
        and _first_reply_captures_focus_piece(board, alternative_move, alternative.pv_san)
    ):
        alternative_effects["new_targets"] = ""
        alternative_effects["central_squares"] = ""

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


def _newly_exposed_valuable_piece_context(board: chess.Board, move: chess.Move) -> str:
    """Explain an immediate legal queen/rook capture created by vacating a line."""

    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return ""
    mover = board.turn
    opponent = not mover
    projected = board.copy(stack=False)
    projected.push(move)
    san = board.san(move)

    for piece_type in (chess.QUEEN, chess.ROOK):
        for target_square in board.pieces(piece_type, mover):
            if board.is_attacked_by(opponent, target_square):
                continue
            if not projected.is_attacked_by(opponent, target_square):
                continue
            captures = [
                reply
                for reply in projected.generate_legal_captures()
                if reply.to_square == target_square
            ]
            if not captures:
                continue
            reply = captures[0]
            attacker = projected.piece_at(reply.from_square)
            between = chess.between(reply.from_square, target_square)
            vacated_line = bool(between & chess.BB_SQUARES[move.from_square])
            if attacker is None or not vacated_line:
                continue

            reply_san = projected.san(reply)
            opponent_name = "Schwarz" if opponent == chess.BLACK else "Weiß"
            target_name = "deine Dame" if piece_type == chess.QUEEN else "deinen Turm"
            moved_name = _piece_name_singular(moving_piece)
            line = _line_square_names(reply.from_square, target_square)
            line_kind = "Diagonale" if attacker.piece_type == chess.BISHOP else "Linie"
            return (
                f"Nach {san} kann {opponent_name} sofort mit {reply_san} {target_name} "
                f"schlagen. Dein {moved_name} auf {chess.square_name(move.from_square)} hatte "
                f"bis dahin die {line_kind} {line} blockiert."
            )
    return ""


def _line_square_names(from_square: chess.Square, to_square: chess.Square) -> str:
    from_file = chess.square_file(from_square)
    from_rank = chess.square_rank(from_square)
    to_file = chess.square_file(to_square)
    to_rank = chess.square_rank(to_square)
    file_step = (to_file > from_file) - (to_file < from_file)
    rank_step = (to_rank > from_rank) - (to_rank < from_rank)
    file_index = from_file
    rank_index = from_rank
    squares: list[str] = []
    while True:
        squares.append(chess.square_name(chess.square(file_index, rank_index)))
        if file_index == to_file and rank_index == to_rank:
            break
        file_index += file_step
        rank_index += rank_step
    return "–".join(squares)


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


def _deduplicate_explanation_sections(
    summary: str, sections: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Keep expanded sections from repeating the summary or one another."""

    seen_sentences = {
        _normalized_explanation_sentence(sentence)
        for sentence in _explanation_sentences(summary)
        if sentence.strip()
    }
    result: list[dict[str, str]] = []
    for section in sections:
        section_text = section.get("text", "").strip()
        unique_sentences: list[str] = []
        for sentence in _explanation_sentences(section_text):
            normalized = _normalized_explanation_sentence(sentence)
            if not normalized or normalized in seen_sentences:
                continue
            seen_sentences.add(normalized)
            unique_sentences.append(sentence.strip())
        if unique_sentences:
            result.append({**section, "text": " ".join(unique_sentences)})
    return result


def _explanation_sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text.strip()) if text.strip() else []


def _normalized_explanation_sentence(text: str) -> str:
    normalized = text.casefold()
    for word, digit in {
        "eins": "1",
        "zwei": "2",
        "drei": "3",
        "vier": "4",
    }.items():
        normalized = re.sub(rf"\b{word}\b", digit, normalized)
    return " ".join(re.sub(r"[^a-z0-9äöüß]+", " ", normalized).split())


def _has_supported_explanation(
    answer_facts: list[dict[str, Any]], sections: list[dict[str, str]]
) -> bool:
    has_plan = any(
        section.get("title") in {"Mittel- und langfristiger Plan", "Buchgestützter Plan"}
        and bool(section.get("text"))
        and not section["text"].startswith(
            (
                "Die berechneten Varianten zeigen keinen einzelnen stabilen Langzeitplan",
                "Aus den geprüften Varianten lässt sich kein einzelner stabiler Langzeitplan",
            )
        )
        for section in sections
    )
    if has_plan:
        return True
    causal_ids = {
        "direct_threat",
        "defender_pressure",
        "heuristic",
        "development",
        "continuation",
        "contrast",
    }
    return any(fact.get("id") in causal_ids and fact.get("text") for fact in answer_facts)


def _book_synthesis_facts(answer_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the source synthesizer focused on causal, board-grounded evidence."""
    useful_ids = {
        "plan",
        "recurring_plan",
        "concept",
        "direct_threat",
        "defender_pressure",
        "heuristic",
        "development",
        "board_changes",
        "continuation",
        "contrast",
    }
    return [fact for fact in answer_facts if fact.get("id") in useful_ids]


def _defender_pressure_context(board: chess.Board, move: chess.Move) -> str:
    """Explain when a move attacks the defender of a central pawn."""
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        return ""
    projected = board.copy(stack=False)
    projected.push(move)
    for target_square in projected.attacks(move.to_square):
        target_piece = projected.piece_at(target_square)
        if target_piece is None or target_piece.color == moving_piece.color:
            continue
        defended_pawns = [
            square
            for square in projected.attacks(target_square)
            if square in chess.SquareSet(chess.BB_CENTER)
            and projected.piece_at(square) == chess.Piece(chess.PAWN, target_piece.color)
        ]
        if not defended_pawns:
            continue
        pawn_square = defended_pawns[0]
        target_name = {
            chess.PAWN: "den gegnerischen Bauern",
            chess.KNIGHT: "den gegnerischen Springer",
            chess.BISHOP: "den gegnerischen Läufer",
            chess.ROOK: "den gegnerischen Turm",
            chess.QUEEN: "die gegnerische Dame",
            chess.KING: "den gegnerischen König",
        }[target_piece.piece_type]
        san = board.san(move)
        return (
            f"{san} greift {target_name} auf "
            f"{chess.square_name(target_square)} an. Diese Figur deckt zugleich den Bauern auf "
            f"{chess.square_name(pawn_square)}. Der Zug stellt damit einen Verteidiger dieses "
            "zentralen Bauern infrage, gewinnt ihn aber nicht automatisch."
        )
    return ""


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


def _minor_pieces_off_starting_squares(board: chess.Board) -> int:
    starting_pieces = (
        (chess.B1, chess.Piece(chess.KNIGHT, chess.WHITE)),
        (chess.G1, chess.Piece(chess.KNIGHT, chess.WHITE)),
        (chess.C1, chess.Piece(chess.BISHOP, chess.WHITE)),
        (chess.F1, chess.Piece(chess.BISHOP, chess.WHITE)),
        (chess.B8, chess.Piece(chess.KNIGHT, chess.BLACK)),
        (chess.G8, chess.Piece(chess.KNIGHT, chess.BLACK)),
        (chess.C8, chess.Piece(chess.BISHOP, chess.BLACK)),
        (chess.F8, chess.Piece(chess.BISHOP, chess.BLACK)),
    )
    return sum(board.piece_at(square) != piece for square, piece in starting_pieces)


def _center_pawns_off_starting_squares(board: chess.Board) -> int:
    starting_pawns = (
        (chess.D2, chess.Piece(chess.PAWN, chess.WHITE)),
        (chess.E2, chess.Piece(chess.PAWN, chess.WHITE)),
        (chess.D7, chess.Piece(chess.PAWN, chess.BLACK)),
        (chess.E7, chess.Piece(chess.PAWN, chess.BLACK)),
    )
    return sum(board.piece_at(square) != piece for square, piece in starting_pawns)


def _learner_center_pawns_off_start(board: chess.Board, color: chess.Color) -> int:
    squares = (chess.D2, chess.E2) if color == chess.WHITE else (chess.D7, chess.E7)
    pawn = chess.Piece(chess.PAWN, color)
    return sum(board.piece_at(square) != pawn for square in squares)


def _learner_minor_development(interactions: list[dict[str, Any]], color: chess.Color) -> int:
    starting_squares = (
        {"b1", "g1", "c1", "f1"} if color == chess.WHITE else {"b8", "g8", "c8", "f8"}
    )
    return len(
        {
            str(row["move_uci"])[:2]
            for row in interactions
            if row["actor"] == "learner"
            and row["accepted"]
            and row["move_uci"]
            and str(row["move_uci"])[:2] in starting_squares
        }
    )
