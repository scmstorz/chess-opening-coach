from __future__ import annotations

import random
import threading
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import chess

from chess_coach.engine import MoveAnalysis, StockfishService
from chess_coach.openings import OpeningBook, OpeningIdentity, TheoryMove
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor, TutorText


@dataclass(slots=True)
class GameSession:
    session_id: str
    board: chess.Board
    learner_color: chess.Color
    opening: OpeningIdentity | None = None
    move_history: list[dict[str, str]] = field(default_factory=list)
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
            details=f"{_move_concept(session.board, move)} {self._engine_details(analysis)}",
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
            details=f"{_move_concept(session.board, move)} {self._engine_details(analysis)}",
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
        return f"Stockfish bewertet die entstehende Stellung mit {evaluation}.{best}"

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

    def _response(
        self,
        session: GameSession,
        *,
        messages: list[dict[str, Any]],
        correction: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        if target in {"e4", "d4", "e5", "d5"}:
            return "Der Bauernzug beansprucht Raum im Zentrum und öffnet Linien für Figuren."
        if target in {"e3", "e6"}:
            return "Der Zug stützt den späteren d-Bauernzug und öffnet die Diagonale des Läufers."
        if target in {"d3", "d6"}:
            return "Der Zug stabilisiert das Zentrum und öffnet die Diagonale des Läufers."
        if target in {"g3", "g6", "b3", "b6"}:
            return (
                "Der Bauernzug bereitet die Entwicklung des Läufers auf der langen Diagonale vor."
            )
        return "Der Bauernzug gewinnt Raum, legt aber zugleich neue Felder dauerhaft fest."
    if piece.piece_type == chess.KNIGHT:
        return "Der Springer wird entwickelt und nimmt Einfluss auf zentrale Felder."
    if piece.piece_type == chess.BISHOP:
        return "Der Läufer wird entwickelt und richtet sich auf eine aktive Diagonale."
    if piece.piece_type == chess.ROOK:
        return "Der Turm verbessert seine Aktivität auf einer wichtigen Linie."
    if piece.piece_type == chess.QUEEN:
        return "Die Dame wird aktiv; in der Eröffnung muss sie dabei gegnerische Tempi vermeiden."
    return "Der Königszug verändert Sicherheit und Figurenkoordination."
