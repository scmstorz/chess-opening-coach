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


class StockfishService:
    def __init__(
        self,
        executable: str | None = None,
        *,
        time_seconds: float = 0.12,
        multipv: int = 3,
        cache: Cache | None = None,
    ) -> None:
        self.executable = executable or self.locate()
        self.time_seconds = time_seconds
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
        """Return Stockfish's preferred move and its verified move analysis."""
        probe_move = next(iter(board.legal_moves), None)
        if probe_move is None:
            return None, unavailable_analysis("Die Partie enthält keinen legalen Zug mehr")

        probe = self.analyze_move(board, probe_move)
        if not probe.available or not probe.best_move_uci:
            return None, probe
        try:
            best_move = chess.Move.from_uci(probe.best_move_uci)
        except (chess.InvalidMoveError, ValueError):
            return None, unavailable_analysis("Stockfish lieferte keinen gültigen besten Zug")
        if best_move not in board.legal_moves:
            return None, unavailable_analysis("Stockfish lieferte einen illegalen besten Zug")
        if best_move == probe_move:
            return best_move, probe
        return best_move, self.analyze_move(board, best_move)

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


def analysis_from_json(payload: str) -> MoveAnalysis:
    data = json.loads(payload)
    data["best_pv_san"] = tuple(data["best_pv_san"])
    data["played_pv_san"] = tuple(data["played_pv_san"])
    return MoveAnalysis(**data)


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
