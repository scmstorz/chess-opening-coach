import chess
import pytest
from chess_coach.engine import StockfishService, classify_loss


def test_loss_classification_preserves_small_difference_tolerance() -> None:
    assert classify_loss(0.14) == "practically_equal"
    assert classify_loss(0.15) == "slight_inaccuracy"
    assert classify_loss(0.40) == "inaccuracy"
    assert classify_loss(0.75) == "mistake"
    assert classify_loss(1.51) == "serious_mistake"


def test_local_stockfish_adapter_when_engine_is_installed() -> None:
    engine = StockfishService(time_seconds=0.01, multipv=2)
    if not engine.available:
        pytest.skip("Stockfish is not installed")
    try:
        board = chess.Board()
        analysis = engine.analyze_move(board, chess.Move.from_uci("e2e4"))
    finally:
        engine.close()

    assert analysis.available is True
    assert analysis.best_move_uci is not None
    assert analysis.evaluation_played is not None
