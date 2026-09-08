from __future__ import annotations

import json
import os
import shutil
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import chess
import chess.engine

from chess_coach.openings import position_key


class Cache(Protocol):
    def get_analysis(self, cache_key: str) -> str | None: ...

    def put_analysis(self, cache_key: str, payload: str) -> None: ...


@dataclass(frozen=True, slots=True)
class MoveAnalysis:
    available: bool
    engine_name: str | None
    best_move_uci: str | None
    best_move_san: str | None
    evaluation_before: float | None
    evaluation_played: float | None
    mate_before: int | None
    mate_played: int | None
    loss_pawns: float | None
    classification: str
    best_pv_san: tuple[str, ...]
    played_pv_san: tuple[str, ...]
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateAnalysis:
    move_uci: str
    move_san: str
    evaluation: float
    mate: int | None
    loss_pawns: float
    pv_san: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MoveComparison:
    available: bool
    engine_name: str | None
    candidates: tuple[CandidateAnalysis, ...]
    reason: str | None = None


class StockfishService:
    def __init__(
        self,
        executable: str | None = None,
        *,
        time_seconds: float = 0.12,
        explanation_time_seconds: float = 0.8,
        selection_time_seconds: float = 2.0,
        deep_time_seconds: float = 5.0,
        multipv: int = 3,
        cache: Cache | None = None,
    ) -> None:
        self.executable = executable or self.locate()
        self.time_seconds = time_seconds
        self.explanation_time_seconds = explanation_time_seconds
        self.selection_time_seconds = selection_time_seconds
        self.deep_time_seconds = deep_time_seconds
        self.multipv = multipv
        self.cache = cache
        self._engine: chess.engine.SimpleEngine | None = None
        self._name: str | None = None
        self._lock = threading.Lock()

    @staticmethod
    def locate() -> str | None:
        configured = os.environ.get("STOCKFISH_PATH")
        for candidate in (
            configured,
            shutil.which("stockfish"),
            "/opt/homebrew/bin/stockfish",
            "/usr/local/bin/stockfish",
            "/opt/homebrew/opt/stockfish/bin/stockfish",
        ):
            if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return None

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def available(self) -> bool:
        return self.executable is not None

    def _start(self) -> chess.engine.SimpleEngine:
        if self._engine is not None:
            return self._engine
        if not self.executable:
            raise FileNotFoundError("Stockfish wurde nicht gefunden")
        self._engine = chess.engine.SimpleEngine.popen_uci(self.executable)
        self._name = self._engine.id.get("name", "Stockfish")
        return self._engine

    def analyze_move(self, board: chess.Board, move: chess.Move) -> MoveAnalysis:
        with self._lock:
            if not self.executable:
                return unavailable_analysis("Stockfish wurde nicht gefunden")
            try:
                engine = self._start()
                cache_key = json.dumps(
                    {
                        "fen": position_key(board),
                        "move": move.uci(),
                        "engine": self._name,
                        "time": self.time_seconds,
                        "multipv": self.multipv,
                    },
                    sort_keys=True,
                )
                if self.cache and (cached := self.cache.get_analysis(cache_key)):
                    return analysis_from_json(cached)

                limit = chess.engine.Limit(time=self.time_seconds)
                raw_infos = engine.analyse(board, limit, multipv=self.multipv)
                infos = raw_infos if isinstance(raw_infos, list) else [raw_infos]
                best_info = infos[0]
                played_info = next(
                    (info for info in infos if info.get("pv") and info["pv"][0] == move),
                    None,
                )
                if played_info is None:
                    played_info = engine.analyse(board, limit, root_moves=[move])

                best_eval, best_mate = _white_score(best_info)
                played_eval, played_mate = _white_score(played_info)
                best_move = best_info["pv"][0]
                loss = _loss_for_turn(board.turn, best_eval, played_eval)
                analysis = MoveAnalysis(
                    available=True,
                    engine_name=self._name,
                    best_move_uci=best_move.uci(),
                    best_move_san=board.san(best_move),
                    evaluation_before=best_eval,
                    evaluation_played=played_eval,
                    mate_before=best_mate,
                    mate_played=played_mate,
                    loss_pawns=loss,
                    classification=classify_loss(loss),
                    best_pv_san=_pv_san(board, best_info.get("pv", [])),
                    played_pv_san=_pv_san(board, played_info.get("pv", [])),
                )
                if self.cache:
                    self.cache.put_analysis(cache_key, json.dumps(asdict(analysis)))
                return analysis
            except (OSError, chess.engine.EngineError, KeyError) as exc:
                return unavailable_analysis(str(exc))

    def get_best_move(self, board: chess.Board) -> tuple[chess.Move | None, MoveAnalysis]:
        """Return a move selected with the more stable coach-move budget."""
        comparison = self.compare_moves(board, stable=True)
        if not comparison.available or not comparison.candidates:
            return None, unavailable_analysis(
                comparison.reason or "Stockfish lieferte keinen Zugvorschlag"
            )
        candidate = comparison.candidates[0]
        try:
            best_move = chess.Move.from_uci(candidate.move_uci)
        except (chess.InvalidMoveError, ValueError):
            return None, unavailable_analysis("Stockfish lieferte keinen gültigen besten Zug")
        if best_move not in board.legal_moves:
            return None, unavailable_analysis("Stockfish lieferte einen illegalen besten Zug")
        return best_move, self.analysis_from_comparison(board, best_move, comparison)

    def compare_moves(
        self,
        board: chess.Board,
        *,
        count: int = 3,
        focus_move: chess.Move | None = None,
        stable: bool = False,
        deep: bool = False,
    ) -> MoveComparison:
        """Analyze candidates; deep mode rechecks one common root set consistently."""
        with self._lock:
            if not self.executable:
                return unavailable_comparison("Stockfish wurde nicht gefunden")
            legal_count = board.legal_moves.count()
            if legal_count == 0:
                return unavailable_comparison("Die Partie enthält keinen legalen Zug mehr")
            requested_count = max(1, min(count, legal_count))
            try:
                engine = self._start()
                mode = "deep" if deep else "stable" if stable else "explanation"
                time_seconds = (
                    self.deep_time_seconds
                    if deep
                    else self.selection_time_seconds
                    if stable
                    else self.explanation_time_seconds
                )
                depth = 24 if deep else 20 if stable else 18
                cache_key = json.dumps(
                    {
                        "kind": "move_comparison",
                        "mode": mode,
                        "fen": position_key(board),
                        "engine": self._name,
                        "time": time_seconds,
                        "depth": depth,
                        "multipv": requested_count,
                        "focus_move": focus_move.uci() if focus_move else None,
                    },
                    sort_keys=True,
                )
                if self.cache and (cached := self.cache.get_analysis(cache_key)):
                    return comparison_from_json(cached)

                limit = chess.engine.Limit(time=time_seconds, depth=depth)
                raw_infos = engine.analyse(board, limit, multipv=requested_count)
                infos = raw_infos if isinstance(raw_infos, list) else [raw_infos]
                if not infos or not infos[0].get("pv"):
                    return unavailable_comparison("Stockfish lieferte keine Kandidaten")

                if deep:
                    root_moves = [info["pv"][0] for info in infos if info.get("pv")]
                    if focus_move and focus_move not in root_moves:
                        root_moves.append(focus_move)
                    raw_infos = engine.analyse(
                        board,
                        limit,
                        multipv=len(root_moves),
                        root_moves=root_moves,
                    )
                    infos = raw_infos if isinstance(raw_infos, list) else [raw_infos]
                    if not infos or not infos[0].get("pv"):
                        return unavailable_comparison("Stockfish lieferte keine vertiefte Analyse")

                best_evaluation, _ = _white_score(infos[0])
                candidates: list[CandidateAnalysis] = []
                for info in infos:
                    pv = info.get("pv", [])
                    if not pv:
                        continue
                    evaluation, mate = _white_score(info)
                    move = pv[0]
                    candidates.append(
                        CandidateAnalysis(
                            move_uci=move.uci(),
                            move_san=board.san(move),
                            evaluation=evaluation,
                            mate=mate,
                            loss_pawns=_loss_for_turn(board.turn, best_evaluation, evaluation),
                            pv_san=_pv_san(board, pv),
                        )
                    )
                if not deep and focus_move and all(
                    candidate.move_uci != focus_move.uci() for candidate in candidates
                ):
                    focus_info = engine.analyse(
                        board,
                        limit,
                        root_moves=[focus_move],
                    )
                    focus_evaluation, focus_mate = _white_score(focus_info)
                    candidates.append(
                        CandidateAnalysis(
                            move_uci=focus_move.uci(),
                            move_san=board.san(focus_move),
                            evaluation=focus_evaluation,
                            mate=focus_mate,
                            loss_pawns=_loss_for_turn(
                                board.turn, best_evaluation, focus_evaluation
                            ),
                            pv_san=_pv_san(board, focus_info.get("pv", [])),
                        )
                    )
                comparison = MoveComparison(
                    available=bool(candidates),
                    engine_name=self._name,
                    candidates=tuple(candidates),
                    reason=None if candidates else "Stockfish lieferte keine Kandidaten",
                )
                if self.cache:
                    self.cache.put_analysis(cache_key, json.dumps(asdict(comparison)))
                return comparison
            except (OSError, chess.engine.EngineError, KeyError) as exc:
                return unavailable_comparison(str(exc))

    @staticmethod
    def analysis_from_comparison(
        board: chess.Board, move: chess.Move, comparison: MoveComparison
    ) -> MoveAnalysis:
        """Build move feedback from one internally consistent MultiPV snapshot."""
        if not comparison.available or not comparison.candidates:
            return unavailable_analysis(comparison.reason or "Stockfish lieferte keine Analyse")
        best = comparison.candidates[0]
        played = next(
            (candidate for candidate in comparison.candidates if candidate.move_uci == move.uci()),
            None,
        )
        if played is None:
            return unavailable_analysis("Der untersuchte Zug fehlt in der Engine-Analyse")
        return MoveAnalysis(
            available=True,
            engine_name=comparison.engine_name,
            best_move_uci=best.move_uci,
            best_move_san=best.move_san,
            evaluation_before=best.evaluation,
            evaluation_played=played.evaluation,
            mate_before=best.mate,
            mate_played=played.mate,
            loss_pawns=played.loss_pawns,
            classification=classify_loss(played.loss_pawns),
            best_pv_san=best.pv_san,
            played_pv_san=played.pv_san,
        )

    def close(self) -> None:
        with self._lock:
            if self._engine:
                try:
                    self._engine.quit()
                except chess.engine.EngineTerminatedError:
                    pass
                self._engine = None


def classify_loss(loss: float | None) -> str:
    if loss is None:
        return "unavailable"
    if loss < 0.15:
        return "practically_equal"
    if loss < 0.40:
        return "slight_inaccuracy"
    if loss < 0.75:
        return "inaccuracy"
    if loss <= 1.50:
        return "mistake"
    return "serious_mistake"


def unavailable_analysis(reason: str) -> MoveAnalysis:
    return MoveAnalysis(
        available=False,
        engine_name=None,
        best_move_uci=None,
        best_move_san=None,
        evaluation_before=None,
        evaluation_played=None,
        mate_before=None,
        mate_played=None,
        loss_pawns=None,
        classification="unavailable",
        best_pv_san=(),
        played_pv_san=(),
        reason=reason,
    )


def unavailable_comparison(reason: str) -> MoveComparison:
    return MoveComparison(
        available=False,
        engine_name=None,
        candidates=(),
        reason=reason,
    )


def analysis_from_json(payload: str) -> MoveAnalysis:
    data = json.loads(payload)
    data["best_pv_san"] = tuple(data["best_pv_san"])
    data["played_pv_san"] = tuple(data["played_pv_san"])
    return MoveAnalysis(**data)


def comparison_from_json(payload: str) -> MoveComparison:
    data = json.loads(payload)
    data["candidates"] = tuple(
        CandidateAnalysis(
            **{
                **candidate,
                "pv_san": tuple(candidate["pv_san"]),
            }
        )
        for candidate in data.get("candidates", [])
    )
    return MoveComparison(**data)


def _white_score(info: chess.engine.InfoDict) -> tuple[float, int | None]:
    white = info["score"].white()
    mate = white.mate()
    score = white.score(mate_score=100_000)
    if score is None:
        raise chess.engine.EngineError("Stockfish lieferte keine Bewertung")
    return round(score / 100, 2), mate


def _loss_for_turn(turn: chess.Color, best: float, played: float) -> float:
    raw = best - played if turn == chess.WHITE else played - best
    return round(max(0.0, raw), 2)


def _pv_san(board: chess.Board, moves: list[chess.Move]) -> tuple[str, ...]:
    replay = board.copy(stack=False)
    result: list[str] = []
    for move in moves[:8]:
        if move not in replay.legal_moves:
            break
        result.append(replay.san(move))
        replay.push(move)
    return tuple(result)
