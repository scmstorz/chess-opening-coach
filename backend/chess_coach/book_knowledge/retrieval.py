from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

import chess

from chess_coach.book_knowledge.compiler import normalize_text
from chess_coach.book_knowledge.models import (
    BookCitation,
    BookEvidence,
    BookFact,
    KnowledgeStatus,
)
from chess_coach.book_knowledge.schema import (
    IncompatibleKnowledgeDatabase,
    connect_readonly,
)
from chess_coach.openings import OpeningIdentity, position_key

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "der",
    "die",
    "das",
    "ein",
    "eine",
    "einer",
    "für",
    "good",
    "gut",
    "hier",
    "ist",
    "in",
    "of",
    "sagt",
    "the",
    "this",
    "to",
    "über",
    "und",
    "von",
    "warum",
    "was",
    "wie",
    "with",
    "zug",
    "move",
}


def _terms(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[\wÀ-ÖØ-öø-ÿ'-]+", normalize_text(text), re.UNICODE)
        if len(token) >= 2 and token not in STOPWORDS
    ]


def _expression(text: str, operator: str) -> str | None:
    tokens = _terms(text)
    if not tokens:
        return None
    escaped = [f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens]
    return f" {operator} ".join(escaped)


def _opening_family_name(name: str) -> str:
    """Return a spelling-normalized family name without a Lichess variation suffix."""

    family = normalize_text(name.split(":", 1)[0])
    return family.replace("defence", "defense")


def _matches_opening_family(row: dict[str, Any], family: str) -> bool:
    context = normalize_text(f"{row['title']} {row['section_path']}").replace(
        "defence", "defense"
    )
    return family in context


def query_expressions(connection: sqlite3.Connection, query: str) -> list[str]:
    normalized = normalize_text(query)
    expressions: list[str] = []
    canonicals = {
        row["canonical_name"]
        for row in connection.execute("SELECT normalized_term, canonical_name FROM aliases")
        if row["normalized_term"] in normalized
    }
    for canonical in sorted(canonicals):
        alternatives = [canonical]
        alternatives.extend(
            row["term"]
            for row in connection.execute(
                "SELECT term FROM aliases WHERE canonical_name = ? ORDER BY language, term",
                (canonical,),
            )
        )
        aliases = [expression for item in alternatives if (expression := _expression(item, "AND"))]
        if aliases:
            expressions.append(" OR ".join(f"({expression})" for expression in aliases))
    exact = _expression(query, "AND")
    broad = _expression(query, "OR")
    if exact:
        expressions.insert(0, exact)
    if broad:
        expressions.append(broad)
    return list(dict.fromkeys(expressions))


def search_chunks(
    connection: sqlite3.Connection,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    sql = """
        SELECT c.id AS chunk_id, c.source_ref, c.book_id, b.title AS book_title,
               b.author, b.publication_year, b.source_path, c.title,
               c.section_path, c.page_start, c.page_end, c.text,
               bm25(chunks_fts, 0.0, 5.0, 2.0, 1.0) AS score
        FROM chunks_fts
        JOIN chunks c ON c.id = CAST(chunks_fts.chunk_id AS INTEGER)
        JOIN books b ON b.id = c.book_id
        WHERE chunks_fts MATCH ?
        ORDER BY score, c.source_ref
        LIMIT ?
    """
    for expression in query_expressions(connection, query):
        try:
            rows = connection.execute(sql, (expression, limit)).fetchall()
        except sqlite3.OperationalError:
            continue
        if rows:
            return [dict(row) for row in rows]
    return []


class NullBookKnowledgeBase:
    def __init__(self, reason: str = "Keine lokale Buchdatenbank konfiguriert.") -> None:
        self.reason = reason

    def status(self) -> dict[str, Any]:
        return KnowledgeStatus(False, 0, 0, self.reason).as_dict()

    def retrieve(
        self,
        *,
        question: str,
        board: chess.Board,
        opening: OpeningIdentity | None,
        focus_move: chess.Move | None,
        limit: int = 3,
        max_chars: int = 2500,
    ) -> BookEvidence:
        del question, board, opening, focus_move, limit, max_chars
        return BookEvidence((), "none", False, self.reason)


class BookKnowledgeBase:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    def _connection(self) -> sqlite3.Connection:
        return connect_readonly(self.database_path)

    def status(self) -> dict[str, Any]:
        if not self.database_path.is_file():
            return KnowledgeStatus(False, 0, 0, "Die lokale Buchdatenbank fehlt.").as_dict()
        try:
            connection = self._connection()
            row = connection.execute(
                """
                SELECT (SELECT count(*) FROM books) AS books,
                       (SELECT count(*) FROM chunks) AS chunks
                """
            ).fetchone()
            connection.close()
        except (OSError, sqlite3.DatabaseError, IncompatibleKnowledgeDatabase) as exc:
            return KnowledgeStatus(False, 0, 0, str(exc)).as_dict()
        book_count = int(row["books"])
        return KnowledgeStatus(
            bool(book_count),
            book_count,
            int(row["chunks"]),
            None if book_count else "Die Buchdatenbank enthält noch kein Buch.",
        ).as_dict()

    def retrieve(
        self,
        *,
        question: str,
        board: chess.Board,
        opening: OpeningIdentity | None,
        focus_move: chess.Move | None,
        limit: int = 3,
        max_chars: int = 2500,
    ) -> BookEvidence:
        if not self.database_path.is_file():
            return BookEvidence((), "none", False, "Die lokale Buchdatenbank fehlt.")
        try:
            connection = self._connection()
        except (OSError, sqlite3.DatabaseError, IncompatibleKnowledgeDatabase) as exc:
            return BookEvidence((), "none", False, str(exc))
        try:
            ranked = self._ranked_chunks(
                connection,
                question=question,
                board=board,
                opening=opening,
                focus_move=focus_move,
                fetch_limit=max(limit * 4, 12),
            )
            exact_ranked = [row for row in ranked if row["rank"] <= 1]
            facts, truncated = self._facts(
                connection, exact_ranked, limit=limit, max_chars=max_chars
            )
            if not facts and not exact_ranked:
                facts, truncated = self._facts(
                    connection, ranked, limit=limit, max_chars=max_chars
                )
        finally:
            connection.close()
        return BookEvidence(tuple(facts), "position+opening+move+fts", truncated)

    @staticmethod
    def _ranked_chunks(
        connection: sqlite3.Connection,
        *,
        question: str,
        board: chess.Board,
        opening: OpeningIdentity | None,
        focus_move: chess.Move | None,
        fetch_limit: int,
    ) -> list[dict[str, Any]]:
        results: dict[int, dict[str, Any]] = {}

        def add(rows: list[dict[str, Any]], rank: int, kind: str) -> None:
            for position, row in enumerate(rows):
                chunk_id = int(row["chunk_id"])
                candidate = {**row, "rank": rank, "match_kind": kind, "position": position}
                current = results.get(chunk_id)
                if current is None or (rank, position) < (
                    current["rank"],
                    current["position"],
                ):
                    results[chunk_id] = candidate

        def exact_rows(position: chess.Board) -> list[dict[str, Any]]:
            return [
                dict(row)
                for row in connection.execute(
                """
                SELECT c.id AS chunk_id, c.source_ref, c.book_id,
                       b.title AS book_title, b.author, b.publication_year,
                       b.source_path, c.title, c.section_path, c.page_start,
                       c.page_end, c.text, 0.0 AS score,
                       pe.position_key AS matched_position_key,
                       max(CASE WHEN l.context_method = 'progressive_annotated_move'
                                THEN 1 ELSE 0 END) AS position_scoped
                FROM book_position_evidence pe
                JOIN book_lines l ON l.id = pe.line_id
                JOIN chunks c ON c.id = pe.chunk_id
                JOIN books b ON b.id = c.book_id
                WHERE pe.position_key = ?
                  AND l.validation_status IN ('valid', 'context_resolved')
                GROUP BY c.id, pe.position_key
                ORDER BY position_scoped DESC, c.source_ref
                LIMIT ?
                """,
                (position_key(position), fetch_limit),
            )
            ]

        if focus_move and focus_move in board.legal_moves:
            projected = board.copy(stack=False)
            projected.push(focus_move)
            add(exact_rows(projected), 0, "position_after_move")
        add(exact_rows(board), 1, "position")
        if opening:
            opening_rows = search_chunks(connection, opening.name, limit=fetch_limit)
            opening_family = _opening_family_name(opening.name)
            family_rows = [
                row
                for row in opening_rows
                if _matches_opening_family(row, opening_family)
            ]
            # An OR-expanded FTS query for a name such as "Dutch Defense:
            # Stonewall" can otherwise admit every chapter containing the
            # generic word "Defense". No family match is safer than silently
            # importing plans from a different opening.
            add(family_rows, 2, "opening")
        if focus_move and opening:
            san = board.san(focus_move).rstrip("+#")
            move_query = f"{opening.name} {san}"
            move_rows = search_chunks(connection, move_query, limit=fetch_limit)
            move_rows = [
                row
                for row in move_rows
                if _matches_opening_family(row, opening_family)
            ]
            add(move_rows, 3, "move")
        if opening:
            question_rows = search_chunks(connection, question, limit=fetch_limit)
            question_rows = [
                row
                for row in question_rows
                if _matches_opening_family(row, opening_family)
            ]
            add(question_rows, 4, "question")
        return sorted(
            results.values(),
            key=lambda row: (
                row["rank"],
                row["position"],
                float(row.get("score", 0.0)),
                row["source_ref"],
            ),
        )

    @staticmethod
    def _facts(
        connection: sqlite3.Connection,
        ranked: list[dict[str, Any]],
        *,
        limit: int,
        max_chars: int,
    ) -> tuple[list[BookFact], bool]:
        facts: list[BookFact] = []
        section_counts: dict[tuple[str, str], int] = {}
        section_claim_types: set[tuple[str, str, str]] = set()
        remaining = max_chars
        truncated = False
        for row in ranked:
            section_key = (row["book_id"], row["section_path"])
            if section_counts.get(section_key, 0) >= 2:
                continue
            exact_match = row["match_kind"] in {"position", "position_after_move"}
            if exact_match and int(row.get("position_scoped", 0)):
                position_filter = "AND position_key = ?"
                parameters: tuple[Any, ...] = (
                    row["chunk_id"],
                    row.get("matched_position_key"),
                )
            elif exact_match:
                position_filter = "AND (position_key IS NULL OR position_key = ?)"
                parameters = (row["chunk_id"], row.get("matched_position_key"))
            else:
                # Position-bound prose must never leak into another variation
                # merely because FTS matched an opening name or SAN token.
                position_filter = "AND position_key IS NULL"
                parameters = (row["chunk_id"],)
            claims = connection.execute(
                f"""
                SELECT id, claim_type, text, validation_status
                FROM claims
                WHERE chunk_id = ?
                  AND validation_status IN ('source_only', 'legality_checked', 'engine_checked')
                  AND claim_type != 'statistic'
                  AND claim_type IN ('plan', 'recommendation', 'warning')
                  {position_filter}
                ORDER BY CASE claim_type
                    WHEN 'plan' THEN 0
                    WHEN 'recommendation' THEN 1
                    WHEN 'warning' THEN 2
                    WHEN 'definition' THEN 3
                    ELSE 4 END,
                    confidence DESC, id
                LIMIT 3
                """,
                parameters,
            ).fetchall()
            if not claims:
                continue
            warnings = tuple(
                issue["issue_type"]
                for issue in connection.execute(
                    """
                    SELECT DISTINCT issue_type FROM issues
                    WHERE chunk_id = ? AND status = 'open' AND severity IN ('warning', 'error')
                    ORDER BY issue_type
                    """,
                    (row["chunk_id"],),
                )
            )
            citation = BookCitation(
                book_id=row["book_id"],
                title=row["book_title"],
                author=row["author"],
                publication_year=row["publication_year"],
                source_path=Path(row["source_path"]),
                page_start=int(row["page_start"]),
                page_end=int(row["page_end"]),
                source_ref=row["source_ref"],
            )
            for claim in claims:
                if section_counts.get(section_key, 0) >= 2:
                    break
                if row["match_kind"] not in {"position", "position_after_move"} and (
                    claim["claim_type"] != "plan"
                ):
                    # FTS matches for an opening name, SAN token, or question can
                    # come from a different sub-variation in the same section.
                    # Recommendations and warnings therefore require an exact
                    # reconstructed position. Only general plans survive broad
                    # contextual matches.
                    continue
                claim_key = (
                    (*section_key, f"{claim['claim_type']}:{claim['id']}")
                    if exact_match and int(row.get("position_scoped", 0))
                    else (*section_key, str(claim["claim_type"]))
                )
                if claim_key in section_claim_types:
                    continue
                selected_text = str(claim["text"])
                if len(selected_text) > remaining:
                    if remaining < 120:
                        truncated = True
                        break
                    selected_text = (
                        selected_text[:remaining].rsplit(" ", 1)[0].rstrip() + " …"
                    )
                    truncated = True
                facts.append(
                    BookFact(
                        id=f"book:claim:{claim['id']}",
                        text=selected_text,
                        claim_type=str(claim["claim_type"]),
                        validation_status=str(claim["validation_status"]),
                        citation=citation,
                        warnings=tuple(
                            warning
                            for warning in warnings
                            if not (
                                warning == "contextual_move_claim"
                                and claim["validation_status"]
                                in {"legality_checked", "engine_checked"}
                            )
                        ),
                        match_kind=row["match_kind"],
                    )
                )
                section_counts[section_key] = section_counts.get(section_key, 0) + 1
                section_claim_types.add(claim_key)
                remaining -= len(selected_text)
                if len(facts) >= limit:
                    truncated = truncated or len(ranked) > 1 or len(claims) > 1
                    break
            if len(facts) >= limit or remaining < 120:
                break
        return facts, truncated
