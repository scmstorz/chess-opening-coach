from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import chess
import chess.pgn

from chess_coach.openings import position_key

ITALIAN_WHITE_LESSON_ID = "italian-white-pianissimo"
_HINT_PATTERN = re.compile(r"\[%hint(?P<number>[12])\s+(?P<text>[^\]]+)\]")


@dataclass(frozen=True, slots=True)
class GuidedMove:
    ply: int
    position_key: str
    color: chess.Color
    move_uci: str
    move_san: str
    explanation: str
    hints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GuidedLesson:
    lesson_id: str
    title: str
    opening_name: str
    eco: str
    goal: str
    learner_color: chess.Color
    moves: tuple[GuidedMove, ...]

    @property
    def learner_move_count(self) -> int:
        return sum(move.color == self.learner_color for move in self.moves)

    def move_at(self, ply: int) -> GuidedMove | None:
        return self.moves[ply] if 0 <= ply < len(self.moves) else None

    def find_move(self, board: chess.Board, move: chess.Move) -> GuidedMove | None:
        key = position_key(board)
        return next(
            (
                item
                for item in self.moves
                if item.position_key == key and item.move_uci == move.uci()
            ),
            None,
        )


class GuidedLessonBook:
    """Load authored guided lessons while keeping PGN as the move source of truth."""

    def __init__(self, data_path: str | Path | None = None) -> None:
        self.lessons: dict[str, GuidedLesson] = {}
        if data_path is None:
            return
        path = Path(data_path)
        if not path.exists():
            return
        files = sorted(path.glob("*.pgn")) if path.is_dir() else [path]
        for source in files:
            with source.open(encoding="utf-8") as handle:
                self._load_stream(handle)

    def get(self, lesson_id: str | None = None) -> GuidedLesson:
        selected_id = lesson_id or ITALIAN_WHITE_LESSON_ID
        try:
            return self.lessons[selected_id]
        except KeyError as exc:
            raise ValueError(f"Unbekannte Trainingslektion: {selected_id}") from exc

    def _load_stream(self, stream: TextIO) -> None:
        while game := chess.pgn.read_game(stream):
            lesson = _parse_lesson(game)
            if lesson.lesson_id in self.lessons:
                raise ValueError(f"Doppelte Trainingslektion: {lesson.lesson_id}")
            self.lessons[lesson.lesson_id] = lesson


def _parse_lesson(game: chess.pgn.Game) -> GuidedLesson:
    lesson_id = game.headers.get("LessonId", "").strip()
    title = game.headers.get("LessonTitle", "").strip()
    opening_name = game.headers.get("Opening", "").strip()
    eco = game.headers.get("ECO", "").strip()
    goal = game.headers.get("LessonGoal", "").strip()
    training_side = game.headers.get("TrainingSide", "").strip().casefold()
    if not all((lesson_id, title, opening_name, eco, goal)):
        raise ValueError(
            "Trainings-PGN benötigt LessonId, LessonTitle, Opening, ECO und LessonGoal"
        )
    if training_side not in {"white", "black"}:
        raise ValueError("TrainingSide muss White oder Black sein")

    board = game.board()
    moves: list[GuidedMove] = []
    node = game
    while node.variations:
        if len(node.variations) != 1:
            raise ValueError(
                f"Trainingslektion {lesson_id} darf zunächst nur eine Hauptlinie haben"
            )
        child = node.variation(0)
        move = child.move
        if move not in board.legal_moves:
            raise ValueError(f"Illegaler Zug in Trainingslektion {lesson_id}: {move.uci()}")
        explanation, hints = _parse_comment(child.comment)
        if not explanation:
            raise ValueError(f"Zug {board.san(move)} in {lesson_id} benötigt eine Erklärung")
        moves.append(
            GuidedMove(
                ply=len(moves),
                position_key=position_key(board),
                color=board.turn,
                move_uci=move.uci(),
                move_san=board.san(move),
                explanation=explanation,
                hints=hints,
            )
        )
        board.push(move)
        node = child
    if not moves:
        raise ValueError(f"Trainingslektion {lesson_id} enthält keine Züge")

    return GuidedLesson(
        lesson_id=lesson_id,
        title=title,
        opening_name=opening_name,
        eco=eco,
        goal=goal,
        learner_color=chess.WHITE if training_side == "white" else chess.BLACK,
        moves=tuple(moves),
    )


def _parse_comment(comment: str) -> tuple[str, tuple[str, ...]]:
    numbered_hints = {
        int(match.group("number")): match.group("text").strip()
        for match in _HINT_PATTERN.finditer(comment)
    }
    explanation = _HINT_PATTERN.sub("", comment).strip()
    hints = tuple(numbered_hints[number] for number in (1, 2) if number in numbered_hints)
    return explanation, hints
