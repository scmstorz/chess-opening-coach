import json
from pathlib import Path
from typing import Any

import chess
import pytest
from chess_coach.engine import CandidateAnalysis, MoveAnalysis, MoveComparison
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "explanation_cases.json").read_text(encoding="utf-8")
)


class FixtureEngine:
    available = True
    executable = "fixture-stockfish"
    name = "Fixture Stockfish"

    def __init__(self, case: dict[str, Any]) -> None:
        self.case = case

    def analyze_move(self, board: chess.Board, move: chess.Move) -> MoveAnalysis:
        data = self.case["analysis"]
        return MoveAnalysis(
            available=True,
            engine_name=self.name,
            best_move_uci=data["best_move_uci"],
            best_move_san=data["best_move_san"],
            evaluation_before=data["evaluation_before"],
            evaluation_played=data["evaluation_played"],
            mate_before=None,
            mate_played=None,
            loss_pawns=data["loss_pawns"],
            classification=data["classification"],
            best_pv_san=tuple(data["best_pv_san"]),
            played_pv_san=tuple(data["played_pv_san"]),
        )

    def compare_moves(
        self, board: chess.Board, *, count: int = 3, focus_move: chess.Move | None = None
    ) -> MoveComparison:
        candidates = tuple(
            CandidateAnalysis(
                move_uci=item[0],
                move_san=item[1],
                evaluation=item[2],
                mate=None,
                loss_pawns=item[3],
                pv_san=tuple(item[4]),
            )
            for item in self.case["candidates"]
        )
        return MoveComparison(True, self.name, candidates)

    def close(self) -> None:
        pass


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_real_explanation_regressions(case: dict[str, Any]) -> None:
    coach = CoachService(
        OpeningBook(),
        FixtureEngine(case),
        OllamaTutor("http://127.0.0.1:1", timeout=0.01),
        SQLiteStore(":memory:"),
    )
    session = coach.create_session("white")
    coach.sessions[session["session_id"]].board = chess.Board(case["fen"])

    message = coach.answer_question(session["session_id"], case["question"], case["focus_uci"])[
        "message"
    ]
    rendered = " ".join(
        [message["summary"]] + [section["text"] for section in message["explanation_sections"]]
    )

    assert message["move"] == chess.Board(case["fen"]).san(chess.Move.from_uci(case["focus_uci"]))
    assert len(message["explanation_sections"]) == 4
    for phrase in case["required_phrases"]:
        assert phrase in rendered
    for phrase in case["forbidden_phrases"]:
        assert phrase not in rendered
