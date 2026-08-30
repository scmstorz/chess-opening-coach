import json
from dataclasses import asdict

import chess
import pytest
from chess_coach.engine import (
    CandidateAnalysis,
    MoveComparison,
    StockfishService,
    classify_loss,
    comparison_from_json,
)


def test_loss_classification_preserves_small_difference_tolerance() -> None:
    assert classify_loss(0.14) == "practically_equal"
    assert classify_loss(0.15) == "slight_inaccuracy"
    assert classify_loss(0.40) == "inaccuracy"
    assert classify_loss(0.75) == "mistake"
    assert classify_loss(1.51) == "serious_mistake"


def test_candidate_comparison_cache_payload_round_trip() -> None:
    comparison = MoveComparison(
        True,
        "Stockfish Test",
        (CandidateAnalysis("c3a2", "Na2", 0.43, None, 0.0, ("Na2", "Bc5")),),
    )

    restored = comparison_from_json(json.dumps(asdict(comparison)))

    assert restored == comparison


def test_local_stockfish_adapter_when_engine_is_installed() -> None:
    engine = StockfishService(time_seconds=0.01, explanation_time_seconds=0.01, multipv=2)
    if not engine.available:
        pytest.skip("Stockfish is not installed")
    try:
        board = chess.Board()
        analysis = engine.analyze_move(board, chess.Move.from_uci("e2e4"))
        focus_move = chess.Move.from_uci("f2f3")
        comparison = engine.compare_moves(board, count=3, focus_move=focus_move)
        best_move, best_analysis = engine.get_best_move(board)
    finally:
        engine.close()

    assert analysis.available is True
    assert analysis.best_move_uci is not None
    assert analysis.evaluation_played is not None
    assert comparison.available is True
    assert 3 <= len(comparison.candidates) <= 4
    assert comparison.candidates[0].loss_pawns == 0.0
    assert any(candidate.move_uci == focus_move.uci() for candidate in comparison.candidates)
    assert all(
        candidate.move_uci in {move.uci() for move in board.legal_moves}
        for candidate in comparison.candidates
    )
    assert best_move is not None
    assert best_move in board.legal_moves
    assert best_analysis.available is True
    assert best_analysis.loss_pawns is not None
    assert best_analysis.loss_pawns < 0.15
