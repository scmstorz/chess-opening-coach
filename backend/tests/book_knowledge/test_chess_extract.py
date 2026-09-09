import chess
from chess_coach.book_knowledge.chess_extract import (
    PGNCandidate,
    find_natural_move_mentions,
    find_pgn_candidates,
    find_san_mentions,
    validate_pgn_candidate,
)
from chess_coach.openings import position_key


def test_legal_numbered_line_uses_the_coach_position_key() -> None:
    candidate = find_pgn_candidates(
        "The line is 1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 and White retreats."
    )[0]
    result = validate_pgn_candidate(candidate)

    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6", "Bb5", "a6"):
        board.push_san(san)
    assert result.status == "valid"
    assert result.positions[-1].position_key == position_key(board)
    assert result.uci_moves[-1] == "a7a6"


def test_illegal_and_contextual_lines_are_not_promoted_to_positions() -> None:
    illegal = validate_pgn_candidate(PGNCandidate("1. e4 e5 2. Ke3", 0, 15))
    fragment = validate_pgn_candidate(PGNCandidate("8... h3 Bh5 9. c4", 0, 18))

    assert illegal.status == "invalid"
    assert fragment.status == "requires_start_position"
    assert fragment.positions == ()


def test_natural_language_moves_are_detected_but_not_reconstructed() -> None:
    mentions = find_natural_move_mentions(
        "Move the king's pawn to e4 and the kingside knight to f3."
    )

    assert len(mentions) == 2


def test_typeset_move_table_is_normalized_and_validated_from_the_start() -> None:
    candidates = find_pgn_candidates("1\n\ne4\n\ne5\n\n2\n\nNf3\n\nNc6\n\n3\n\nBb5 (D)")

    assert len(candidates) == 1
    result = validate_pgn_candidate(candidates[0])
    assert result.status == "valid"
    assert result.san_moves == ("e4", "e5", "Nf3", "Nc6", "Bb5")


def test_san_mentions_are_detected_without_granting_them_a_position() -> None:
    assert find_san_mentions("After 3 Bb5, Black may consider 3...Nf6.") == (
        "Bb5",
        "Nf6",
    )
