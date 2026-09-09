#!/usr/bin/env python3
"""Export unclear or wrong coach explanations as local regression-case candidates."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "coach.db"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "explanation-feedback.json"
PAYLOAD_FIELDS = {
    "explanation_sections_payload": "explanation_sections",
    "engine_payload": "engine",
    "references_payload": "references",
    "knowledge_payload": "knowledge",
}


def feedback_rows(database: Path, ratings: tuple[str, ...]) -> list[dict[str, Any]]:
    placeholders = ", ".join("?" for _ in ratings)
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            f"""
            SELECT * FROM explanation_feedback
            WHERE rating IN ({placeholders})
            ORDER BY updated_at DESC
            """,
            ratings,
        ).fetchall()
    finally:
        connection.close()

    result: list[dict[str, Any]] = []
    for stored in rows:
        row = dict(stored)
        for stored_name, public_name in PAYLOAD_FIELDS.items():
            payload = row.pop(stored_name)
            row[public_name] = json.loads(payload) if payload else None
        result.append(row)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export learner-marked explanations for local review and fixture authoring."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--rating",
        action="append",
        choices=("helpful", "unclear", "wrong"),
        dest="ratings",
        help="Rating to include; repeat for several. Defaults to unclear and wrong.",
    )
    arguments = parser.parse_args()
    ratings = tuple(dict.fromkeys(arguments.ratings or ("unclear", "wrong")))
    rows = feedback_rows(arguments.database, ratings)
    payload = {
        "schema_version": 1,
        "purpose": "Human-reviewed candidates; not automatically accepted as test truth.",
        "ratings": ratings,
        "cases": rows,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(rows)} feedback cases to {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
