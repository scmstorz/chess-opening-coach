import json
from dataclasses import asdict

import chess
import pytest
from chess_coach.engine import (
    CandidateAnalysis,
    MoveComparison,
    MovePlanAnalysis,
    PlanBranch,
    StockfishService,
    classify_loss,
    comparison_from_json,
    plan_from_json,
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


def test_plan_branch_cache_payload_round_trip() -> None:
    plan = MovePlanAnalysis(
        True,
        "Stockfish Test",
        "e2e4",
        "e4",
        (PlanBranch("c7c5", "c5", 0.2, None, ("e4", "c5", "Nf3")),),
    )

    assert plan_from_json(json.dumps(asdict(plan))) == plan


def test_local_stockfish_adapter_when_engine_is_installed() -> None:
    engine = StockfishService(
        time_seconds=0.01,
        explanation_time_seconds=0.01,
        deep_time_seconds=0.01,
        multipv=2,
    )
    if not engine.available:
        pytest.skip("Stockfish is not installed")
    try:
        board = chess.Board()
        analysis = engine.analyze_move(board, chess.Move.from_uci("e2e4"))
        focus_move = chess.Move.from_uci("f2f3")
        comparison = engine.compare_moves(board, count=3, focus_move=focus_move)
        plan = engine.analyze_plan_branches(board, chess.Move.from_uci("e2e4"), reply_count=2)
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
    assert plan.available is True
    assert len(plan.branches) == 2
    assert all(branch.pv_san[0] == "e4" for branch in plan.branches)
