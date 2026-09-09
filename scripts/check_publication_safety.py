#!/usr/bin/env python3
"""Fail when a public Git tree contains private chess-book material."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "book_knowledge.db"
ALLOWED_PRIVATE_PATHS = frozenset({"data/books/README.md"})
PRIVATE_PREFIXES = (
    "data/book_knowledge/",
    "data/private/",
    "data/books/",
)
PRIVATE_SUFFIXES = frozenset(
    {
        ".azw",
        ".azw3",
        ".db",
        ".epub",
        ".mobi",
        ".pdf",
        ".sqlite",
        ".sqlite3",
    }
)
DATABASE_TRAILERS = (".db-shm", ".db-wal", ".sqlite-shm", ".sqlite-wal")
OVERLAP_WORDS = 24


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    reason: str
    location: str


def _git(*arguments: str, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=text,
    )


def path_violation(path: str) -> str | None:
    """Describe why a Git path is unsafe for the public repository."""

    normalized = PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("./")
    if normalized in ALLOWED_PRIVATE_PATHS:
        return None
    lowered = normalized.lower()
    if any(lowered.startswith(prefix) for prefix in PRIVATE_PREFIXES):
        return "private book-source or derived-knowledge path"
    if PurePosixPath(lowered).suffix in PRIVATE_SUFFIXES or lowered.endswith(DATABASE_TRAILERS):
        return "private document, e-book, or database file type"
    return None


def tracked_paths() -> tuple[str, ...]:
    output = _git("ls-files", "-z", text=False).stdout
    return tuple(
        path.decode("utf-8", errors="surrogateescape")
        for path in output.split(b"\0")
        if path
    )


def historical_paths() -> tuple[str, ...]:
    output = _git("log", "--all", "--name-only", "--format=").stdout
    return tuple(line.strip() for line in output.splitlines() if line.strip())


def _normalized_words(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÖØ-öø-ÿ']+", text.casefold(), re.UNICODE)


def _digest(words: list[str]) -> bytes:
    return hashlib.blake2b(" ".join(words).encode("utf-8"), digest_size=16).digest()


def build_book_fingerprints(
    rows: Iterable[tuple[str, str]], *, width: int = OVERLAP_WORDS
) -> dict[bytes, str]:
    """Build non-reversible fingerprints for long source-text sequences."""

    fingerprints: dict[bytes, str] = {}
    for source_ref, text in rows:
        words = _normalized_words(text)
        for index in range(len(words) - width + 1):
            fingerprints.setdefault(_digest(words[index : index + width]), source_ref)
    return fingerprints


def text_overlap_source(
    text: str, fingerprints: dict[bytes, str], *, width: int = OVERLAP_WORDS
) -> str | None:
    words = _normalized_words(text)
    for index in range(len(words) - width + 1):
        source_ref = fingerprints.get(_digest(words[index : index + width]))
        if source_ref:
            return source_ref
    return None


def _index_bytes(path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _text_variants(path: str) -> tuple[str, ...]:
    variants: list[str] = []
    indexed = _index_bytes(path)
    if indexed is not None and b"\0" not in indexed:
        try:
            variants.append(indexed.decode("utf-8"))
        except UnicodeDecodeError:
            pass
    worktree_path = PROJECT_ROOT / path
    if worktree_path.is_file() and not worktree_path.is_symlink():
        try:
            payload = worktree_path.read_bytes()
        except OSError:
            payload = b""
        if payload and b"\0" not in payload and payload != indexed:
            try:
                variants.append(payload.decode("utf-8"))
            except UnicodeDecodeError:
                pass
    return tuple(variants)


def scan_book_overlap(database: Path, paths: tuple[str, ...]) -> tuple[list[Finding], int]:
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT source_ref, text FROM chunks").fetchall()
    finally:
        connection.close()
    fingerprints = build_book_fingerprints(rows)
    findings: list[Finding] = []
    scanned = 0
    for path in paths:
        for text in _text_variants(path):
            scanned += 1
            source_ref = text_overlap_source(text, fingerprints)
            if source_ref:
                findings.append(
                    Finding(
                        path,
                        f"contains a {OVERLAP_WORDS}-word sequence from {source_ref}",
                        "tracked text",
                    )
                )
                break
    return findings, scanned


def check_repository(
    database: Path, *, require_knowledge_scan: bool = False
) -> tuple[list[Finding], dict[str, object]]:
    tracked = tracked_paths()
    history = historical_paths()
    findings = [
        Finding(path, reason, "Git index")
        for path in tracked
        if (reason := path_violation(path))
    ]
    findings.extend(
        Finding(path, reason, "Git history")
        for path in sorted(set(history) - set(tracked))
        if (reason := path_violation(path))
    )

    overlap_scanned = False
    scanned_texts = 0
    if database.is_file():
        try:
            overlap_findings, scanned_texts = scan_book_overlap(database, tracked)
        except sqlite3.DatabaseError as exc:
            if require_knowledge_scan:
                findings.append(Finding(str(database), f"knowledge scan failed: {exc}", "local"))
        else:
            findings.extend(overlap_findings)
            overlap_scanned = True
    elif require_knowledge_scan:
        findings.append(
            Finding(
                str(database),
                "local knowledge database is required for the release overlap scan",
                "local",
            )
        )

    summary = {
        "tracked_paths": len(tracked),
        "historical_paths": len(set(history)),
        "knowledge_overlap_scanned": overlap_scanned,
        "tracked_text_variants_scanned": scanned_texts,
        "database": str(database),
    }
    return findings, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check that a public release contains no private chess-book material."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("CHESS_COACH_BOOK_DATABASE", DEFAULT_DATABASE)),
    )
    parser.add_argument(
        "--require-knowledge-scan",
        action="store_true",
        help="fail if the local corpus is unavailable for long-text overlap detection",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        findings, summary = check_repository(
            args.database.expanduser(), require_knowledge_scan=args.require_knowledge_scan
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Publication safety check could not run: {exc}", file=sys.stderr)
        return 2

    if findings:
        print("Publication safety check failed:", file=sys.stderr)
        for finding in findings:
            print(
                f"- {finding.path} ({finding.location}): {finding.reason}",
                file=sys.stderr,
            )
        return 1

    print("Publication safety check passed.")
    print(
        f"Checked {summary['tracked_paths']} tracked paths and "
        f"{summary['historical_paths']} historical paths."
    )
    if summary["knowledge_overlap_scanned"]:
        print(
            "Compared tracked text against the private local corpus "
            f"({summary['tracked_text_variants_scanned']} text variants)."
        )
    else:
        print("Skipped private-corpus overlap scan because no local database was available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
