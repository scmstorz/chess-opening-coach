from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import chess
import chess.pgn

from chess_coach.openings import position_key

ITALIAN_WHITE_LESSON_ID = "italian-white-pianissimo"
ITALIAN_WHITE_FAMILY = "italian-white"
GUIDED_STYLES = frozenset({"mainline", "branches", "realistic"})
OPPONENT_CATEGORIES = frozenset(
    {"established", "solid", "slow", "dubious", "trap", "mistake"}
)
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
    family: str
    title: str
    opening_name: str
    eco: str
    goal: str
    learner_color: chess.Color
    drill_start_ply: int
    realistic_weight: int
    opponent_category: str
    moves: tuple[GuidedMove, ...]

    @property
    def learner_move_count(self) -> int:
        return sum(move.color == self.learner_color for move in self.moves)

    def learner_move_count_from(self, ply: int) -> int:
        return sum(move.color == self.learner_color for move in self.moves[ply:])

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

    def position_at(self, ply: int) -> tuple[chess.Board, tuple[dict[str, str], ...]]:
        if not 0 <= ply <= len(self.moves):
            raise ValueError(f"Ungültiger Start-Halbzug für {self.lesson_id}: {ply}")
        board = chess.Board()
        history: list[dict[str, str]] = []
        for item in self.moves[:ply]:
            move = chess.Move.from_uci(item.move_uci)
            if move not in board.legal_moves:
                raise ValueError(f"Trainingslinie {self.lesson_id} ist nicht rekonstruierbar")
            history.append(
                {
                    "actor": "learner" if item.color == self.learner_color else "coach",
                    "san": item.move_san,
                }
            )
            board.push(move)
        return board, tuple(history)


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

    def select(
        self,
        style: str,
        rng: random.Random,
        lesson_id: str | None = None,
    ) -> GuidedLesson:
        if style not in GUIDED_STYLES:
            raise ValueError(f"Unbekannte Form des geführten Trainings: {style}")
        if lesson_id is not None:
            lesson = self.get(lesson_id)
            if lesson.family != ITALIAN_WHITE_FAMILY:
                raise ValueError("Die gewählte Lektion gehört nicht zum Italienisch-Training")
            if lesson.lesson_id != ITALIAN_WHITE_LESSON_ID:
                self.validate_scenario(lesson)
            return lesson
        if style == "mainline":
            return self.get(ITALIAN_WHITE_LESSON_ID)
        if style == "branches":
            candidates = sorted(
                (
                    lesson
                    for lesson in self.lessons.values()
                    if lesson.family == ITALIAN_WHITE_FAMILY and lesson.drill_start_ply > 0
                ),
                key=lambda lesson: lesson.lesson_id,
            )
            if not candidates:
                raise ValueError("Es sind keine Abweichungsübungen hinterlegt")
            for candidate in candidates:
                self.validate_scenario(candidate)
            return rng.choice(candidates)
        candidates = sorted(
            (
                lesson
                for lesson in self.lessons.values()
                if lesson.family == ITALIAN_WHITE_FAMILY and lesson.realistic_weight > 0
            ),
            key=lambda lesson: lesson.lesson_id,
        )
        if not candidates:
            raise ValueError("Es sind keine realistischen Gegnerlinien hinterlegt")
        for candidate in candidates:
            if candidate.lesson_id != ITALIAN_WHITE_LESSON_ID:
                self.validate_scenario(candidate)
        return rng.choices(
            candidates,
            weights=[lesson.realistic_weight for lesson in candidates],
            k=1,
        )[0]

    def first_divergence_ply(self, lesson: GuidedLesson) -> int | None:
        mainline = self.get(ITALIAN_WHITE_LESSON_ID)
        if lesson.lesson_id == mainline.lesson_id:
            return None
        for ply, step in enumerate(lesson.moves):
            mainline_step = mainline.move_at(ply)
            if mainline_step is None or step.move_uci != mainline_step.move_uci:
                return ply
        return len(lesson.moves) if len(lesson.moves) != len(mainline.moves) else None

    def validate_scenario(self, lesson: GuidedLesson) -> None:
        divergence_ply = self.first_divergence_ply(lesson)
        if divergence_ply is None or divergence_ply >= len(lesson.moves):
            raise ValueError(f"{lesson.lesson_id} weicht nicht von der Grundlinie ab")
        if divergence_ply != lesson.drill_start_ply - 1:
            raise ValueError(
                f"DrillStartPly von {lesson.lesson_id} muss direkt nach der Abweichung liegen"
            )
        if lesson.moves[divergence_ply].color == lesson.learner_color:
            raise ValueError(f"Die erste Abweichung von {lesson.lesson_id} muss vom Coach kommen")

    def _load_stream(self, stream: TextIO) -> None:
        while game := chess.pgn.read_game(stream):
            lesson = _parse_lesson(game)
            if lesson.lesson_id in self.lessons:
                raise ValueError(f"Doppelte Trainingslektion: {lesson.lesson_id}")
            self.lessons[lesson.lesson_id] = lesson


def _parse_lesson(game: chess.pgn.Game) -> GuidedLesson:
    lesson_id = game.headers.get("LessonId", "").strip()
    family = game.headers.get("LessonFamily", "").strip()
    title = game.headers.get("LessonTitle", "").strip()
    opening_name = game.headers.get("Opening", "").strip()
    eco = game.headers.get("ECO", "").strip()
    goal = game.headers.get("LessonGoal", "").strip()
    training_side = game.headers.get("TrainingSide", "").strip().casefold()
    if not all((lesson_id, family, title, opening_name, eco, goal)):
        raise ValueError(
            "Trainings-PGN benötigt LessonId, LessonFamily, LessonTitle, Opening, ECO "
            "und LessonGoal"
        )
    if training_side not in {"white", "black"}:
        raise ValueError("TrainingSide muss White oder Black sein")

    try:
        drill_start_ply = int(game.headers.get("DrillStartPly", "0"))
        realistic_weight = int(game.headers.get("RealisticWeight", "0"))
    except ValueError as exc:
        raise ValueError("DrillStartPly und RealisticWeight müssen ganze Zahlen sein") from exc
    if drill_start_ply < 0 or realistic_weight < 0:
        raise ValueError("DrillStartPly und RealisticWeight dürfen nicht negativ sein")
    opponent_category = game.headers.get("OpponentCategory", "established").strip()
    if opponent_category not in OPPONENT_CATEGORIES:
        choices = ", ".join(sorted(OPPONENT_CATEGORIES))
        raise ValueError(f"OpponentCategory muss eine dieser Kategorien sein: {choices}")

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
    learner_color = chess.WHITE if training_side == "white" else chess.BLACK
    if drill_start_ply >= len(moves):
        raise ValueError(f"DrillStartPly liegt hinter dem Ende von {lesson_id}")
    if moves[drill_start_ply].color != learner_color:
        raise ValueError(f"DrillStartPly von {lesson_id} muss den Lernenden ans Zug bringen")
    for item in moves[drill_start_ply:]:
        if item.color == learner_color and len(item.hints) != 2:
            raise ValueError(f"Lernzug {item.move_san} in {lesson_id} benötigt zwei Hinweise")

    return GuidedLesson(
        lesson_id=lesson_id,
        family=family,
        title=title,
        opening_name=opening_name,
        eco=eco,
        goal=goal,
        learner_color=learner_color,
        drill_start_ply=drill_start_ply,
        realistic_weight=realistic_weight,
        opponent_category=opponent_category,
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
