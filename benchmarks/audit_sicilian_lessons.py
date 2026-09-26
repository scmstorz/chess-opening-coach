"""Compare the three authored Sicilian lines with local Stockfish."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import chess
import chess.engine
import chess.pgn

DEFAULT_PGN = Path(__file__).resolve().parents[1] / "data/repertoires/sicilian-white.pgn"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default=shutil.which("stockfish"))
    parser.add_argument("--pgn", type=Path, default=DEFAULT_PGN)
    parser.add_argument("--seconds", type=float, default=0.35)
    args = parser.parse_args()
    if not args.engine:
        parser.error("Stockfish wurde nicht gefunden; --engine angeben")
    if args.seconds <= 0:
        parser.error("--seconds muss positiv sein")

    engine = chess.engine.SimpleEngine.popen_uci(args.engine)
    try:
        engine.configure({"Threads": 2, "Hash": 64})
        with args.pgn.open(encoding="utf-8") as stream:
            while game := chess.pgn.read_game(stream):
                board = game.board()
                losses: dict[chess.Color, list[float]] = {chess.WHITE: [], chess.BLACK: []}
                for move in game.mainline_moves():
                    perspective = board.turn
                    limit = chess.engine.Limit(time=args.seconds)
                    best = engine.analyse(board, limit)["score"].pov(perspective).score(
                        mate_score=10000
                    )
                    chosen = engine.analyse(board, limit, root_moves=[move])[
                        "score"
                    ].pov(perspective).score(mate_score=10000)
                    if best is None or chosen is None:
                        raise RuntimeError("Stockfish lieferte keine auswertbare Stellung")
                    losses[perspective].append(max(0, best - chosen) / 100)
                    board.push(move)
                print(
                    f"{game.headers['LessonId']}: "
                    f"White max {max(losses[chess.WHITE]):.2f}, "
                    f"Black max {max(losses[chess.BLACK]):.2f} pawns"
                )
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
