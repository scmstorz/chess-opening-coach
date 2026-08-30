from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    fen_before TEXT NOT NULL,
                    actor TEXT NOT NULL CHECK(actor IN ('learner', 'coach')),
                    move_uci TEXT,
                    move_san TEXT,
                    legal INTEGER NOT NULL,
                    accepted INTEGER NOT NULL,
                    theory_match INTEGER,
                    opening_eco TEXT,
                    opening_name TEXT,
                    engine_evaluation REAL,
                    engine_loss REAL,
                    engine_classification TEXT,
                    attempt_number INTEGER NOT NULL,
                    feedback_summary TEXT NOT NULL,
                    llm_model TEXT
                );
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self.connection.execute("PRAGMA optimize")
            self.connection.commit()

    def record(self, values: dict[str, Any]) -> int:
        columns = (
            "created_at",
            "session_id",
            "fen_before",
            "actor",
            "move_uci",
            "move_san",
            "legal",
            "accepted",
            "theory_match",
            "opening_eco",
            "opening_name",
            "engine_evaluation",
            "engine_loss",
            "engine_classification",
            "attempt_number",
            "feedback_summary",
            "llm_model",
        )
        row = {"created_at": datetime.now(UTC).isoformat(), **values}
        placeholders = ", ".join("?" for _ in columns)
        with self._lock:
            cursor = self.connection.execute(
                f"INSERT INTO interactions ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(row.get(column) for column in columns),
            )
            self.connection.commit()
            return int(cursor.lastrowid)

    def latest_interaction_id(self, session_id: str) -> int | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT MAX(id) AS id FROM interactions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return int(row["id"]) if row and row["id"] is not None else None

    def delete_interactions_after(self, session_id: str, interaction_id: int | None) -> None:
        with self._lock:
            if interaction_id is None:
                self.connection.execute(
                    "DELETE FROM interactions WHERE session_id = ?", (session_id,)
                )
            else:
                self.connection.execute(
                    "DELETE FROM interactions WHERE session_id = ? AND id > ?",
                    (session_id, interaction_id),
                )
            self.connection.commit()

    def get_analysis(self, cache_key: str) -> str | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT payload FROM analysis_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
        return row["payload"] if row else None

    def put_analysis(self, cache_key: str, payload: str) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR REPLACE INTO analysis_cache VALUES (?, ?, ?)",
                (cache_key, payload, datetime.now(UTC).isoformat()),
            )
            self.connection.commit()

    def summary(self) -> dict[str, int]:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT COUNT(*) AS attempts,
                       COALESCE(SUM(actor = 'learner' AND accepted = 1), 0) AS accepted,
                       COALESCE(SUM(actor = 'learner' AND accepted = 0), 0) AS corrections
                FROM interactions
                """
            ).fetchone()
        return dict(row)

    def close(self) -> None:
        with self._lock:
            self.connection.close()
