from __future__ import annotations

import json
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
                    training_mode TEXT NOT NULL DEFAULT 'free',
                    lesson_id TEXT,
                    lesson_style TEXT,
                    repertoire_match INTEGER,
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
                CREATE TABLE IF NOT EXISTS session_summaries (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    session_id TEXT NOT NULL UNIQUE,
                    opening_eco TEXT,
                    opening_name TEXT,
                    final_fen TEXT NOT NULL,
                    move_count INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS explanation_feedback (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    rating TEXT NOT NULL CHECK(rating IN ('helpful', 'unclear', 'wrong')),
                    note TEXT NOT NULL DEFAULT '',
                    position_fen TEXT NOT NULL,
                    opening_eco TEXT,
                    opening_name TEXT,
                    message_kind TEXT,
                    actor TEXT NOT NULL,
                    question TEXT,
                    move_uci TEXT,
                    move_san TEXT,
                    summary_snapshot TEXT NOT NULL,
                    details_snapshot TEXT NOT NULL,
                    explanation_sections_payload TEXT NOT NULL,
                    source TEXT NOT NULL,
                    llm_model TEXT,
                    engine_payload TEXT,
                    references_payload TEXT NOT NULL,
                    knowledge_payload TEXT,
                    UNIQUE(session_id, message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_explanation_feedback_rating_updated
                ON explanation_feedback(rating, updated_at DESC);
                """
            )
            self._ensure_columns(
                "interactions",
                {
                    "training_mode": "TEXT NOT NULL DEFAULT 'free'",
                    "lesson_id": "TEXT",
                    "lesson_style": "TEXT",
                    "repertoire_match": "INTEGER",
                },
            )
            self.connection.execute("PRAGMA optimize")
            self.connection.commit()

    def _ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        """Add forward-compatible columns to databases created by older builds."""

        existing = {
            str(row["name"])
            for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, declaration in columns.items():
            if name not in existing:
                self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

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
            "training_mode",
            "lesson_id",
            "lesson_style",
            "repertoire_match",
            "opening_eco",
            "opening_name",
            "engine_evaluation",
            "engine_loss",
            "engine_classification",
            "attempt_number",
            "feedback_summary",
            "llm_model",
        )
        row = {
            "created_at": datetime.now(UTC).isoformat(),
            "training_mode": "free",
            **values,
        }
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

    def session_interactions(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM interactions WHERE session_id = ? ORDER BY id", (session_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def record_session_summary(
        self,
        *,
        session_id: str,
        opening_eco: str | None,
        opening_name: str | None,
        final_fen: str,
        move_count: int,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        created_at = datetime.now(UTC).isoformat()
        stored_summary = {**summary, "created_at": created_at}
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO session_summaries (
                    created_at, session_id, opening_eco, opening_name,
                    final_fen, move_count, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    opening_eco = excluded.opening_eco,
                    opening_name = excluded.opening_name,
                    final_fen = excluded.final_fen,
                    move_count = excluded.move_count,
                    payload = excluded.payload
                """,
                (
                    created_at,
                    session_id,
                    opening_eco,
                    opening_name,
                    final_fen,
                    move_count,
                    json.dumps(stored_summary, ensure_ascii=False),
                ),
            )
            self.connection.commit()
        return stored_summary

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT payload FROM session_summaries WHERE session_id = ?", (session_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def delete_session_summary(self, session_id: str) -> None:
        with self._lock:
            self.connection.execute(
                "DELETE FROM session_summaries WHERE session_id = ?", (session_id,)
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

    def record_explanation_feedback(self, values: dict[str, Any]) -> dict[str, Any]:
        """Upsert one learner judgment together with its reproducible context."""

        now = datetime.now(UTC).isoformat()
        columns = (
            "created_at",
            "updated_at",
            "session_id",
            "message_id",
            "rating",
            "note",
            "position_fen",
            "opening_eco",
            "opening_name",
            "message_kind",
            "actor",
            "question",
            "move_uci",
            "move_san",
            "summary_snapshot",
            "details_snapshot",
            "explanation_sections_payload",
            "source",
            "llm_model",
            "engine_payload",
            "references_payload",
            "knowledge_payload",
        )
        row = {
            "created_at": now,
            "updated_at": now,
            "note": "",
            "explanation_sections_payload": "[]",
            "references_payload": "[]",
            **values,
        }
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{column} = excluded.{column}"
            for column in columns
            if column not in {"created_at", "session_id", "message_id"}
        )
        with self._lock:
            self.connection.execute(
                f"""
                INSERT INTO explanation_feedback ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(session_id, message_id) DO UPDATE SET {updates}
                """,
                tuple(row.get(column) for column in columns),
            )
            stored = self.connection.execute(
                """
                SELECT * FROM explanation_feedback
                WHERE session_id = ? AND message_id = ?
                """,
                (row["session_id"], row["message_id"]),
            ).fetchone()
            self.connection.commit()
        return dict(stored)

    def explanation_feedback(
        self, *, rating: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Return newest feedback snapshots for local review or fixture export."""

        with self._lock:
            if rating is None:
                rows = self.connection.execute(
                    """
                    SELECT * FROM explanation_feedback
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = self.connection.execute(
                    """
                    SELECT * FROM explanation_feedback
                    WHERE rating = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (rating, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, int]:
        with self._lock:
            row = self.connection.execute(
                """
                SELECT COUNT(*) AS attempts,
                       COALESCE(SUM(actor = 'learner' AND accepted = 1), 0) AS accepted,
                       COALESCE(SUM(actor = 'learner' AND accepted = 0), 0) AS corrections,
                       (SELECT COUNT(*) FROM session_summaries) AS sessions_reviewed,
                       (SELECT COUNT(*) FROM explanation_feedback) AS explanations_rated,
                       (SELECT COUNT(*) FROM explanation_feedback
                        WHERE rating = 'helpful') AS explanations_helpful,
                       (SELECT COUNT(*) FROM explanation_feedback
                        WHERE rating = 'unclear') AS explanations_unclear,
                       (SELECT COUNT(*) FROM explanation_feedback
                        WHERE rating = 'wrong') AS explanations_wrong
                FROM interactions
                """
            ).fetchone()
        return dict(row)

    def close(self) -> None:
        with self._lock:
            self.connection.close()
