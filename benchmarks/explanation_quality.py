#!/usr/bin/env python3
"""Run the six learner-derived explanation cases through the real local stack."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import chess
from chess_coach.book_knowledge import BookKnowledgeBase
from chess_coach.config import PROJECT_ROOT, Settings
from chess_coach.engine import StockfishService
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor

CASES_PATH = Path(__file__).parent / "fixtures" / "explanation_quality_cases.json"


def _contains(text: str, phrase: str) -> bool:
    return phrase.casefold() in text.casefold()


def _score(
    case: dict[str, Any], message: dict[str, Any], *, opening_recognized: bool
) -> dict[str, Any]:
    sections = message.get("explanation_sections") or []
    rendered = " ".join(
        [message.get("summary", ""), message.get("details", "")]
        + [section.get("text", "") for section in sections]
    )
    required_missing = [
        phrase for phrase in case["required_phrases"] if not _contains(rendered, phrase)
    ]
    forbidden_found = [
        phrase for phrase in case["forbidden_phrases"] if _contains(rendered, phrase)
    ]
    section_texts = [
        " ".join(section.get("text", "").casefold().split()) for section in sections
    ]
    summary_text = " ".join(message.get("summary", "").casefold().split())
    engine = message.get("engine") or {}
    premise_corrected = True
    if "beste" in case["question"].casefold() and (engine.get("loss_pawns") or 0) >= 0.15:
        premise_corrected = any(
            marker in rendered.casefold()
            for marker in ("nicht der beste", "bevorzugt", "schwächer")
        )
    checks = {
        "deep_mode": message.get("analysis_mode") == "deep",
        "all_sections_nonempty": bool(sections) and all(section_texts),
        "expanded_information_is_not_duplicated": len(section_texts)
        == len(set(section_texts))
        and all(text != summary_text for text in section_texts),
        "required_facts_present": not required_missing,
        "forbidden_phrases_absent": not forbidden_found,
        "false_best_move_premise_corrected": premise_corrected,
        "engine_evidence_present": bool(engine.get("available")),
        "book_evidence_is_position_scoped_without_opening": opening_recognized
        or all(
            str(reference.get("match_kind", "")).startswith("position")
            for reference in message.get("references", [])
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "required_missing": required_missing,
        "forbidden_found": forbidden_found,
    }


def run_case(coach: CoachService, case: dict[str, Any]) -> dict[str, Any]:
    board = chess.Board(case["fen"])
    move = chess.Move.from_uci(case["focus_uci"])
    if move not in board.legal_moves:
        raise ValueError(f"{case['id']}: focus move is illegal")
    created = coach.create_session("white")
    session = coach.sessions[created["session_id"]]
    session.board = board
    session.learner_color = board.turn
    session.opening = coach.openings.identify(board)
    started = time.monotonic()
    message = coach.answer_question(
        session.session_id,
        case["question"],
        case["focus_uci"],
        deep=True,
    )["message"]
    elapsed = round(time.monotonic() - started, 2)
    return {
        "id": case["id"],
        "seconds": elapsed,
        "focus_move": message["move"],
        "summary": message["summary"],
        "sections": message["explanation_sections"],
        "engine": message["engine"],
        "knowledge": message["knowledge"],
        "references": message["references"],
        "tutor_diagnostics": {
            "error": coach.tutor.last_error,
            "synthesis_claims": list(coach.tutor.last_synthesis_claims),
            "critic": coach.tutor.last_critic_result,
        },
        "opening_recognized": session.opening is not None,
        "score": _score(
            case, message, opening_recognized=session.opening is not None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--deep-seconds", type=float, default=5.0)
    args = parser.parse_args()
    settings = Settings()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if args.case_ids:
        cases = [case for case in cases if case["id"] in set(args.case_ids)]

    # Reuse only the normal engine-analysis cache. Position questions do not
    # write learner interactions, so the benchmark remains outside learner state.
    store = SQLiteStore(settings.database_path)
    engine = StockfishService(
        settings.stockfish_path,
        explanation_time_seconds=settings.stockfish_explanation_time_seconds,
        deep_time_seconds=args.deep_seconds,
        multipv=4,
        cache=store,
    )
    coach = CoachService(
        OpeningBook(settings.opening_data_path),
        engine,
        OllamaTutor(settings.ollama_url, settings.ollama_model, timeout=90),
        store,
        book_knowledge=BookKnowledgeBase(settings.book_database_path),
    )
    try:
        results = [run_case(coach, case) for case in cases]
    finally:
        engine.close()
        store.close()
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stockfish": engine.name or engine.executable,
        "ollama_model": coach.tutor.model,
        "book_database": os.path.relpath(settings.book_database_path, PROJECT_ROOT),
        "passed": sum(result["score"]["passed"] for result in results),
        "total": len(results),
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
