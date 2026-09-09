from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS knowledge_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author TEXT,
    publication_year INTEGER,
    source_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    extraction_version TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    page_type TEXT NOT NULL DEFAULT 'content',
    width REAL,
    height REAL,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    UNIQUE(book_id, page_number)
);

CREATE TABLE IF NOT EXISTS spans (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    x_min REAL,
    y_min REAL,
    x_max REAL,
    y_max REAL,
    UNIQUE(page_id, ordinal)
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    level INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
    ordinal INTEGER NOT NULL,
    title TEXT NOT NULL,
    section_path TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    token_estimate INTEGER NOT NULL,
    source_ref TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS chunk_spans (
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    span_id INTEGER NOT NULL REFERENCES spans(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY(chunk_id, span_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    title,
    section_path,
    text,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    span_id INTEGER REFERENCES spans(id) ON DELETE SET NULL,
    page_number INTEGER NOT NULL,
    claim_type TEXT NOT NULL CHECK(claim_type IN (
        'recommendation', 'warning', 'plan', 'definition', 'history', 'statistic'
    )),
    text TEXT NOT NULL,
    confidence REAL NOT NULL,
    extraction_method TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK(validation_status IN (
        'source_only', 'unverified', 'legality_checked', 'engine_checked', 'rejected'
    )),
    position_key TEXT,
    focus_move_uci TEXT,
    opening_name TEXT
);

CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunk_concepts (
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    confidence REAL NOT NULL,
    extraction_method TEXT NOT NULL,
    PRIMARY KEY(chunk_id, concept_id)
);

CREATE TABLE IF NOT EXISTS book_lines (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_pgn TEXT,
    start_fen TEXT,
    end_fen TEXT,
    san_line TEXT,
    uci_line TEXT,
    ply_count INTEGER NOT NULL DEFAULT 0,
    validation_status TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS book_position_evidence (
    id INTEGER PRIMARY KEY,
    position_key TEXT NOT NULL,
    line_id INTEGER NOT NULL REFERENCES book_lines(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    ply INTEGER NOT NULL,
    incoming_san TEXT,
    incoming_uci TEXT,
    UNIQUE(line_id, ply)
);

CREATE TABLE IF NOT EXISTS diagrams (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    image_number INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    encoding TEXT,
    likely_board INTEGER NOT NULL DEFAULT 0,
    orientation TEXT,
    fen TEXT,
    recognition_status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE(book_id, image_number)
);

CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    page_number INTEGER,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'error')),
    message TEXT NOT NULL,
    context TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'reviewed', 'dismissed'))
);

CREATE TABLE IF NOT EXISTS aliases (
    term TEXT PRIMARY KEY,
    normalized_term TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    language TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_book_page ON chunks(book_id, page_start);
CREATE INDEX IF NOT EXISTS idx_claims_chunk_status ON claims(chunk_id, validation_status);
CREATE INDEX IF NOT EXISTS idx_book_position_evidence_position
    ON book_position_evidence(position_key);
CREATE INDEX IF NOT EXISTS idx_issues_book_status_severity
    ON issues(book_id, status, severity);
"""


class IncompatibleKnowledgeDatabase(RuntimeError):
    pass


def connect_writable(path: str | Path) -> sqlite3.Connection:
    database = Path(path).expanduser().resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    database = Path(path).expanduser().resolve()
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA query_only = ON")
    assert_compatible(connection)
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    current = connection.execute(
        "SELECT value FROM knowledge_meta WHERE key = 'schema_version'"
    ).fetchone()
    if current and current["value"] != SCHEMA_VERSION:
        raise IncompatibleKnowledgeDatabase(
            f"Knowledge database schema {current['value']} is incompatible with {SCHEMA_VERSION}"
        )
    connection.execute(
        "INSERT OR REPLACE INTO knowledge_meta(key, value) VALUES('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    connection.commit()


def assert_compatible(connection: sqlite3.Connection) -> None:
    try:
        row = connection.execute(
            "SELECT value FROM knowledge_meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        raise IncompatibleKnowledgeDatabase("Knowledge database has no compatible schema") from exc
    if row is None or row["value"] != SCHEMA_VERSION:
        found = row["value"] if row else "missing"
        raise IncompatibleKnowledgeDatabase(
            f"Knowledge database schema {found} is incompatible with {SCHEMA_VERSION}"
        )


@contextlib.contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        connection.execute("BEGIN")
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def delete_book(connection: sqlite3.Connection, book_id: str) -> bool:
    chunk_ids = [
        row["id"]
        for row in connection.execute("SELECT id FROM chunks WHERE book_id = ?", (book_id,))
    ]
    connection.executemany(
        "DELETE FROM chunks_fts WHERE chunk_id = ?",
        ((chunk_id,) for chunk_id in chunk_ids),
    )
    cursor = connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
    return cursor.rowcount > 0


def integrity_report(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
    chunks = connection.execute("SELECT count(*) FROM chunks").fetchone()[0]
    fts_chunks = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    orphaned_positions = connection.execute(
        """
        SELECT count(*) FROM book_position_evidence pe
        LEFT JOIN chunks c ON c.id = pe.chunk_id
        WHERE c.id IS NULL
        """
    ).fetchone()[0]
    position_plan = [
        tuple(row)
        for row in connection.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM book_position_evidence WHERE position_key = ?",
            ("example",),
        )
    ]
    issue_plan = [
        tuple(row)
        for row in connection.execute(
            """
            EXPLAIN QUERY PLAN SELECT * FROM issues
            WHERE book_id = ? AND status = ? AND severity = ?
            """,
            ("example", "open", "warning"),
        )
    ]
    return {
        "integrity": integrity,
        "foreign_key_errors": foreign_keys,
        "chunks": chunks,
        "fts_chunks": fts_chunks,
        "fts_in_sync": chunks == fts_chunks,
        "orphaned_position_evidence": orphaned_positions,
        "position_query_uses_index": any("USING INDEX" in str(row[3]) for row in position_plan),
        "issue_query_uses_index": any("USING INDEX" in str(row[3]) for row in issue_plan),
    }

