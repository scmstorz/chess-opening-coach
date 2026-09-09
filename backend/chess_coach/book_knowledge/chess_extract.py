from __future__ import annotations

import re
from dataclasses import dataclass

import chess

from chess_coach.openings import position_key

SAN_PATTERN = (
    r"(?:O-O-O|O-O|[KQRBN](?:[a-h1-8]{0,2})x?[a-h][1-8](?:=[QRBN])?[+#]?|"
    r"[a-h](?:x[a-h])?[1-8](?:=[QRBN])?[+#]?)[!?]*"
)
SAN_TOKEN_RE = re.compile(rf"(?<![A-Za-z0-9])(?P<san>{SAN_PATTERN})(?![A-Za-z0-9])")
MOVE_NUMBER_RE = re.compile(r"(?<!\w)(?P<number>\d+)\.(?P<black>\.\.)?")
SEQUENCE_TOKEN_RE = re.compile(
    rf"\s*(?:(?P<number>\d+)\.(?P<black>\.\.)?|(?P<san>{SAN_PATTERN})|"
    r"(?P<result>1-0|0-1|1/2-1/2|\*))"
)
NATURAL_MOVE_RE = re.compile(
    r"\b(?:king'?s?\s+|queen'?s?\s+|kingside\s+|queenside\s+)?"
    r"(?:pawn|knight|bishop|rook|queen|king)\s+(?:to|on|onto)\s+[a-h][1-8]\b",
    re.IGNORECASE,
)
TABLE_MOVE_NUMBER_RE = re.compile(
    rf"(?<![\w.])(?P<number>\d{{1,3}})\s+(?=(?:{SAN_PATTERN})(?![A-Za-z0-9]))"
)


@dataclass(frozen=True, slots=True)
class PGNCandidate:
    raw_text: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class PositionState:
    ply: int
    fen: str
    position_key: str
    incoming_san: str | None
    incoming_uci: str | None


@dataclass(frozen=True, slots=True)
class ValidatedLine:
    raw_text: str
    normalized_pgn: str | None
    start_fen: str | None
    end_fen: str | None
    san_moves: tuple[str, ...]
    uci_moves: tuple[str, ...]
    positions: tuple[PositionState, ...]
    status: str
    error: str | None


def _normalize_castling(text: str) -> str:
    normalized = (
        text.replace("0-0-0", "O-O-O")
        .replace("0-0", "O-O")
        .replace("–", "-")
        .replace("—", "-")
    )
    return TABLE_MOVE_NUMBER_RE.sub(
        lambda match: f"{match.group('number')}. ", normalized
    )


def find_pgn_candidates(text: str) -> tuple[PGNCandidate, ...]:
    normalized = _normalize_castling(text)
    candidates: list[PGNCandidate] = []
    covered_until = -1
    for start_match in MOVE_NUMBER_RE.finditer(normalized):
        if start_match.start() < covered_until:
            continue
        position = start_match.start()
        move_count = 0
        last_end = position
        while position < len(normalized):
            token_match = SEQUENCE_TOKEN_RE.match(normalized, position)
            if not token_match or token_match.end() == position:
                break
            position = token_match.end()
            last_end = position
            if token_match.group("san"):
                move_count += 1
            if token_match.group("result"):
                break
        if move_count >= 2:
            candidates.append(
                PGNCandidate(
                    raw_text=normalized[start_match.start() : last_end].strip(),
                    start_offset=start_match.start(),
                    end_offset=last_end,
                )
            )
            covered_until = last_end
    return tuple(candidates)


def find_natural_move_mentions(text: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in NATURAL_MOVE_RE.finditer(text))


def find_san_mentions(text: str) -> tuple[str, ...]:
    """Find concrete SAN-like anchors without assuming a board position."""
    return tuple(match.group("san") for match in SAN_TOKEN_RE.finditer(_normalize_castling(text)))


def _state(
    board: chess.Board,
    ply: int,
    incoming_san: str | None,
    incoming_uci: str | None,
) -> PositionState:
    return PositionState(
        ply=ply,
        fen=board.fen(en_passant="legal"),
        position_key=position_key(board),
        incoming_san=incoming_san,
        incoming_uci=incoming_uci,
    )


def validate_pgn_candidate(candidate: PGNCandidate) -> ValidatedLine:
    first_number = MOVE_NUMBER_RE.search(candidate.raw_text)
    if first_number is None:
        return _invalid(candidate, "invalid", "No move number found")
    if int(first_number.group("number")) != 1 or first_number.group("black"):
        return _invalid(
            candidate,
            "requires_start_position",
            "The line does not start from White's first move",
        )

    board = chess.Board()
    start_fen = board.fen(en_passant="legal")
    positions = [_state(board, 0, None, None)]
    san_moves: list[str] = []
    uci_moves: list[str] = []
    for token_match in SAN_TOKEN_RE.finditer(candidate.raw_text):
        san = token_match.group("san").rstrip("!?")
        try:
            move = board.parse_san(san)
        except ValueError as exc:
            return ValidatedLine(
                candidate.raw_text,
                None,
                start_fen,
                board.fen(en_passant="legal"),
                tuple(san_moves),
                tuple(uci_moves),
                tuple(positions),
                "invalid",
                f"Illegal or ambiguous SAN '{san}': {exc}",
            )
        canonical_san = board.san(move)
        uci = move.uci()
        board.push(move)
        san_moves.append(canonical_san)
        uci_moves.append(uci)
        positions.append(_state(board, len(san_moves), canonical_san, uci))

    if len(san_moves) < 2:
        return ValidatedLine(
            candidate.raw_text,
            None,
            start_fen,
            board.fen(en_passant="legal"),
            tuple(san_moves),
            tuple(uci_moves),
            tuple(positions),
            "invalid",
            "Fewer than two legal half-moves were found",
        )
    normalized_parts = []
    for index in range(0, len(san_moves), 2):
        normalized_parts.append(f"{index // 2 + 1}. {' '.join(san_moves[index:index + 2])}")
    return ValidatedLine(
        candidate.raw_text,
        " ".join(normalized_parts) + " *",
        start_fen,
        board.fen(en_passant="legal"),
        tuple(san_moves),
        tuple(uci_moves),
        tuple(positions),
        "valid",
        None,
    )


def _invalid(candidate: PGNCandidate, status: str, error: str) -> ValidatedLine:
    return ValidatedLine(
        candidate.raw_text,
        None,
        None,
        None,
        (),
        (),
        (),
        status,
        error,
    )
