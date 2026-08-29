import chess
from chess_coach.openings import OpeningBook


def test_fallback_recognizes_opening_progressively() -> None:
    book = OpeningBook()
    board = chess.Board()
    identity = None

    board.push_san("e4")
    identity = book.identify(board, identity)
    assert identity is not None
    assert identity.name == "King's Pawn Game"

    board.push_san("c5")
    identity = book.identify(board, identity)
    assert identity is not None
    assert identity.name == "Sicilian Defense"


def test_fallback_supplies_multiple_common_first_moves() -> None:
    moves = OpeningBook().theory_moves(chess.Board())

    assert {move.san for move in moves} >= {"e4", "d4", "c4", "Nf3"}
