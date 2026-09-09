from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from chess_coach.book_knowledge.compiler import compile_pdf
from chess_coach.book_knowledge.retrieval import search_chunks
from chess_coach.book_knowledge.schema import (
    connect_writable,
    delete_book,
    initialize,
    integrity_report,
    transaction,
)
from chess_coach.config import PROJECT_ROOT


def _default_database() -> Path:
    return Path(
        os.environ.get(
            "CHESS_COACH_BOOK_DATABASE",
            PROJECT_ROOT / "data" / "book_knowledge.db",
        )
    ).expanduser()


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _connection(path: Path) -> sqlite3.Connection:
    connection = connect_writable(path)
    initialize(connection)
    return connection


def _ingest(args: argparse.Namespace) -> int:
    results = [compile_pdf(pdf, args.db, max_chunk_chars=args.max_chunk_chars) for pdf in args.pdf]
    if args.json:
        _json([result.as_dict() for result in results])
    else:
        for result in results:
            print(f"Imported: {result.title}")
            print(f"Book ID: {result.book_id}")
            print(
                f"{result.pages} pages, {result.sections} sections, {result.chunks} chunks, "
                f"{result.claims} claims, {result.issues} issues"
            )
    return 0


def _books(args: argparse.Namespace) -> int:
    connection = _connection(args.db)
    rows = [
        dict(row)
        for row in connection.execute(
            """
            SELECT id, title, author, publication_year, page_count, source_path,
                   sha256, extraction_version, imported_at
            FROM books ORDER BY title, id
            """
        )
    ]
    connection.close()
    if args.json:
        _json(rows)
    elif not rows:
        print("No books imported.")
    else:
        for row in rows:
            author = f" — {row['author']}" if row["author"] else ""
            print(f"{row['id']}  {row['title']}{author}  ({row['page_count']} pages)")
            print(f"  {row['source_path']}")
    return 0


def _search(args: argparse.Namespace) -> int:
    connection = _connection(args.db)
    rows = search_chunks(connection, args.query, limit=args.limit)
    connection.close()
    if args.json:
        _json(rows)
    elif not rows:
        print("No matching book passage found.")
    else:
        for index, row in enumerate(rows, start=1):
            pages = (
                str(row["page_start"])
                if row["page_start"] == row["page_end"]
                else f"{row['page_start']}-{row['page_end']}"
            )
            print(f"{index}. {row['section_path']} — PDF page {pages}")
            print(f"   {row['source_ref']}  score={row['score']:.4f}")
            print(f"   {str(row['text'])[:500]}")
    return 0


def _issues(args: argparse.Namespace) -> int:
    connection = _connection(args.db)
    where = ["i.status = 'open'"]
    values: list[Any] = []
    if args.book:
        where.append("i.book_id = ?")
        values.append(args.book)
    if args.severity:
        where.append("i.severity = ?")
        values.append(args.severity)
    values.append(args.limit)
    rows = [
        dict(row)
        for row in connection.execute(
            f"""
            SELECT i.id, i.book_id, b.title AS book_title, i.page_number,
                   i.issue_type, i.severity, i.message, i.context
            FROM issues i JOIN books b ON b.id = i.book_id
            WHERE {' AND '.join(where)}
            ORDER BY CASE i.severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                     i.page_number, i.id
            LIMIT ?
            """,
            values,
        )
    ]
    connection.close()
    if args.json:
        _json(rows)
    elif not rows:
        print("No open issues.")
    else:
        for row in rows:
            page = f" p.{row['page_number']}" if row["page_number"] else ""
            print(f"[{row['severity']}] {row['issue_type']}{page}: {row['message']}")
            if row["context"]:
                print(f"  {row['context'][:300]}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    connection = _connection(args.db)
    report = integrity_report(connection)
    connection.close()
    _json(report)
    valid = (
        report["integrity"] == "ok"
        and not report["foreign_key_errors"]
        and report["fts_in_sync"]
        and report["orphaned_position_evidence"] == 0
        and report["position_query_uses_index"]
        and report["issue_query_uses_index"]
    )
    return 0 if valid else 1


def _remove(args: argparse.Namespace) -> int:
    connection = _connection(args.db)
    with transaction(connection):
        removed = delete_book(connection, args.book_id)
    connection.execute("PRAGMA optimize")
    connection.commit()
    connection.close()
    if not removed:
        print(f"Book not found: {args.book_id}", file=sys.stderr)
        return 2
    print(f"Removed {args.book_id} and all derived knowledge.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chess-book-knowledge",
        description="Compile local chess books into a source-grounded SQLite database.",
    )
    parser.add_argument("--db", type=Path, default=_default_database())
    commands = parser.add_subparsers(dest="command", required=True)

    ingest = commands.add_parser("ingest", help="Import or refresh one or more PDFs")
    ingest.add_argument("pdf", type=Path, nargs="+")
    ingest.add_argument("--max-chunk-chars", type=int, default=1800)
    ingest.add_argument("--json", action="store_true")
    ingest.set_defaults(handler=_ingest)

    books = commands.add_parser("books", help="List imported books")
    books.add_argument("--json", action="store_true")
    books.set_defaults(handler=_books)

    search = commands.add_parser("search", help="Search the local book corpus")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--json", action="store_true")
    search.set_defaults(handler=_search)

    issues = commands.add_parser("issues", help="Show extraction and validation issues")
    issues.add_argument("--book")
    issues.add_argument("--severity", choices=("info", "warning", "error"))
    issues.add_argument("--limit", type=int, default=100)
    issues.add_argument("--json", action="store_true")
    issues.set_defaults(handler=_issues)

    verify = commands.add_parser("verify", help="Verify the knowledge database")
    verify.set_defaults(handler=_verify)

    remove = commands.add_parser("remove", help="Remove one book and all derived data")
    remove.add_argument("book_id")
    remove.set_defaults(handler=_remove)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        status = args.handler(args)
    except (OSError, RuntimeError, sqlite3.DatabaseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        status = 1
    raise SystemExit(status)


if __name__ == "__main__":
    main()

