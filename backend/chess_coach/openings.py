from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.pgn


def position_key(board: chess.Board) -> str:
    return " ".join(board.fen().split()[:4])


@dataclass(frozen=True, slots=True)
class OpeningIdentity:
    eco: str
    name: str


@dataclass(frozen=True, slots=True)
class TheoryMove:
    uci: str
    san: str
    weight: int


FALLBACK_LINES: tuple[tuple[str, str, str], ...] = (
    ("B00", "King's Pawn Game", "1. e4"),
    ("B20", "Sicilian Defense", "1. e4 c5"),
    ("B50", "Sicilian Defense: Modern Variations", "1. e4 c5 2. Nf3 d6"),
    (
        "B90",
        "Sicilian Defense: Najdorf Variation",
        "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6",
    ),
    ("C00", "French Defense", "1. e4 e6"),
    ("C10", "French Defense", "1. e4 e6 2. d4 d5 3. Nc3"),
    ("B10", "Caro-Kann Defense", "1. e4 c6"),
    ("B12", "Caro-Kann Defense: Advance Variation", "1. e4 c6 2. d4 d5 3. e5"),
    ("C20", "King's Pawn Game", "1. e4 e5"),
    ("C44", "Scotch Game", "1. e4 e5 2. Nf3 Nc6 3. d4"),
    ("C50", "Italian Game", "1. e4 e5 2. Nf3 Nc6 3. Bc4"),
    ("C54", "Italian Game: Classical Variation", "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4"),
    ("C60", "Ruy Lopez", "1. e4 e5 2. Nf3 Nc6 3. Bb5"),
    ("C70", "Ruy Lopez: Morphy Defense", "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6"),
    ("C25", "Vienna Game", "1. e4 e5 2. Nc3"),
    ("D00", "Queen's Pawn Game", "1. d4 d5"),
    ("D06", "Queen's Gambit", "1. d4 d5 2. c4"),
    ("D30", "Queen's Gambit Declined", "1. d4 d5 2. c4 e6"),
    ("D10", "Slav Defense", "1. d4 d5 2. c4 c6"),
    ("D02", "London System", "1. d4 d5 2. Nf3 Nf6 3. Bf4"),
    ("E60", "King's Indian Defense", "1. d4 Nf6 2. c4 g6 3. Nc3 Bg7"),
    ("E20", "Nimzo-Indian Defense", "1. d4 Nf6 2. c4 e6 3. Nc3 Bb4"),
    ("A10", "English Opening", "1. c4"),
    ("A04", "Zukertort Opening", "1. Nf3"),
)


class OpeningBook:
    def __init__(self, data_path: str | Path | None = None) -> None:
        self.identities: dict[str, OpeningIdentity] = {}
        self.moves: dict[str, Counter[str]] = defaultdict(Counter)
        self.move_san: dict[tuple[str, str], str] = {}
        self.entries_loaded = 0
        self.source = "built-in fallback"
        path = Path(data_path) if data_path else None
        if path and path.exists():
            self._load_path(path)
        if not self.entries_loaded:
            for eco, name, pgn in FALLBACK_LINES:
                self._add_line(eco, name, pgn)
            self.source = "built-in fallback"

    def _load_path(self, path: Path) -> None:
        files = sorted(path.glob("*.tsv")) if path.is_dir() else [path]
        for source_file in files:
            with source_file.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                for row in reader:
                    eco = row.get("eco", "").strip()
                    name = row.get("name", "").strip()
                    pgn = row.get("pgn", "").strip()
                    if eco and name and pgn:
                        self._add_line(eco, name, pgn)
        if self.entries_loaded:
            self.source = f"local Lichess dataset ({self.entries_loaded} entries)"

    def _add_line(self, eco: str, name: str, pgn_text: str) -> None:
        game = chess.pgn.read_game(io.StringIO(f"{pgn_text} *"))
        if game is None or game.errors:
            return
        board = game.board()
        for move in game.mainline_moves():
            key = position_key(board)
            self.moves[key][move.uci()] += 1
            self.move_san[(key, move.uci())] = board.san(move)
            board.push(move)
        self.identities[position_key(board)] = OpeningIdentity(eco=eco, name=name)
        self.entries_loaded += 1

    def identify(
        self, board: chess.Board, previous: OpeningIdentity | None = None
    ) -> OpeningIdentity | None:
        return self.identities.get(position_key(board), previous)

    def theory_moves(self, board: chess.Board) -> tuple[TheoryMove, ...]:
        key = position_key(board)
        candidates = self.moves.get(key, Counter())
        legal = {move.uci() for move in board.legal_moves}
        return tuple(
            TheoryMove(uci=uci, san=self.move_san[(key, uci)], weight=weight)
            for uci, weight in candidates.most_common()
            if uci in legal
        )
