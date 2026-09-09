from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from chess_coach.book_knowledge.chess_extract import (
    find_natural_move_mentions,
    find_pgn_candidates,
    find_san_mentions,
    validate_pgn_candidate,
)
from chess_coach.book_knowledge.models import CompileStats, ExtractedPage
from chess_coach.book_knowledge.pdf_extract import extract_pdf
from chess_coach.book_knowledge.schema import (
    connect_writable,
    delete_book,
    initialize,
    transaction,
)

EXTRACTION_VERSION = "coach-book-4/poppler-bbox-final-position-v4"

ALIASES: tuple[tuple[str, str, str], ...] = (
    ("ruy lopez", "Ruy Lopez", "en"),
    ("spanish game", "Ruy Lopez", "en"),
    ("spanische partie", "Ruy Lopez", "de"),
    ("italian game", "Italian Game", "en"),
    ("italienische partie", "Italian Game", "de"),
    ("queen's gambit", "Queen's Gambit", "en"),
    ("queens gambit", "Queen's Gambit", "en"),
    ("damengambit", "Queen's Gambit", "de"),
    ("sicilian defense", "Sicilian Defense", "en"),
    ("sicilian defence", "Sicilian Defense", "en"),
    ("sizilianische verteidigung", "Sicilian Defense", "de"),
    ("french defense", "French Defense", "en"),
    ("french defence", "French Defense", "en"),
    ("französische verteidigung", "French Defense", "de"),
    ("caro-kann defense", "Caro-Kann Defense", "en"),
    ("caro-kann verteidigung", "Caro-Kann Defense", "de"),
    ("king's indian defense", "King's Indian Defense", "en"),
    ("königsindische verteidigung", "King's Indian Defense", "de"),
    ("slav defense", "Slav Defense", "en"),
    ("slawische verteidigung", "Slav Defense", "de"),
    ("scotch game", "Scotch Game", "en"),
    ("schottische partie", "Scotch Game", "de"),
    ("london system", "London System", "en"),
    ("londoner system", "London System", "de"),
    ("english opening", "English Opening", "en"),
    ("englische eröffnung", "English Opening", "de"),
    ("pirc defense", "Pirc Defense", "en"),
    ("pirc-verteidigung", "Pirc Defense", "de"),
    ("king's pawn opening", "King's Pawn Opening", "en"),
    ("königsbauerneröffnung", "King's Pawn Opening", "de"),
)

CONCEPT_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "development": ("strategy", ("develop", "development", "entwickl")),
    "center_control": (
        "strategy",
        ("control the center", "central territory", "occupying the center", "zentrum"),
    ),
    "king_safety": (
        "strategy",
        ("king safety", "protect your king", "unprotected king", "königssicherheit"),
    ),
    "castling": ("technique", ("castling", "castle", "rochade", "rochieren")),
    "fianchetto": ("technique", ("fianchetto", "fianchett")),
    "initiative": ("strategy", ("initiative", "tempo", "take charge")),
    "space": ("strategy", ("space advantage", "territory", "raumvorteil")),
    "pawn_structure": (
        "structure",
        ("pawn structure", "pawn chain", "bauernstruktur", "bauernkette"),
    ),
    "attack": ("strategy", ("attack", "attacking", "angriff")),
    "defense": ("strategy", ("defense", "defence", "defending", "verteidigung")),
    "tactics": ("tactics", ("tactic", "combination", "fork", "pin", "taktik")),
    "transposition": ("opening", ("transposition", "transpose", "zugumstellung")),
}

CLAIM_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("statistic", ("%", "percent", "probability", "win rate", "chance of winning")),
    (
        "warning",
        (
            "avoid",
            "do not",
            "don't",
            "never",
            "mistake",
            "mistakes",
            "flaw",
            "flaws",
            "drawback",
            "drawbacks",
        ),
    ),
    (
        "recommendation",
        (
            "should",
            "best move",
            "consider",
            "recommend",
            "recommends",
            "recommended",
            "need to",
            "make sure",
        ),
    ),
    (
        "plan",
        (
            "main goal",
            "purpose",
            "purposes",
            "plan",
            "plans",
            "strategy",
            "strategies",
            "aim",
            "aims",
            "aiming",
            "intend",
            "intends",
            "intending",
            "hope",
            "hopes",
            "hoping",
            "idea",
            "ideas",
            "control",
            "occupy",
        ),
    ),
    ("definition", ("known as", "referred to as", "means", "is called", "defined as")),
    ("history", ("century", "named after", "popularized", "historical", "history")),
)

HEADING_KEYWORDS = {
    "opening",
    "openings",
    "game",
    "games",
    "defense",
    "defence",
    "attack",
    "gambit",
    "system",
    "strategy",
    "castling",
    "fianchetto",
    "variations",
}


@dataclass(frozen=True, slots=True)
class StoredSpan:
    id: int
    page_number: int
    kind: str
    text: str


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text)
    value = value.replace("’", "'").replace("‘", "'")
    value = value.replace("“", '"').replace("”", '"')
    value = value.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", value).strip().lower()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repeated_block_texts(pages: tuple[ExtractedPage, ...]) -> set[str]:
    occurrences: Counter[str] = Counter()
    for page in pages:
        seen = {
            normalize_text(block.text)
            for block in page.blocks
            if 1 <= len(normalize_text(block.text)) <= 80
        }
        occurrences.update(seen)
    threshold = max(4, math.ceil(len(pages) * 0.20))
    return {text for text, count in occurrences.items() if count >= threshold}


def _page_types(pages: tuple[ExtractedPage, ...]) -> dict[int, str]:
    result = {page.page_number: "content" for page in pages}
    contents_page: int | None = None
    for page in pages:
        first_blocks = [normalize_text(block.text) for block in page.blocks[:4]]
        if any(text in {"contents", "table of contents"} for text in first_blocks):
            contents_page = page.page_number
            break
    introduction_page: int | None = None
    if contents_page:
        for page in pages:
            if page.page_number <= contents_page:
                continue
            first_blocks = [normalize_text(block.text) for block in page.blocks[:3]]
            if "introduction" in first_blocks and len(page.text) > 400:
                introduction_page = page.page_number
                break
    if contents_page and introduction_page:
        for page in pages:
            if page.page_number < contents_page:
                result[page.page_number] = "frontmatter"
            elif page.page_number < introduction_page:
                result[page.page_number] = "toc"
    elif contents_page:
        for page in pages:
            if page.page_number < contents_page:
                result[page.page_number] = "frontmatter"
        result[contents_page] = "toc"
    elif pages:
        result[pages[0].page_number] = "cover"
    return result


def heading_level(text: str) -> int | None:
    clean = re.sub(r"\s+", " ", text).strip(" -–—")
    normalized = normalize_text(clean)
    if not clean or len(clean) > 140 or clean.endswith((".", "?", "!", ",", ";")):
        return None
    if re.match(r"^chapter\s+\d+\b", normalized):
        return 1
    if normalized in {"introduction", "conclusion", "contents"}:
        return 1
    if clean.isupper() and 1 <= len(clean.split()) <= 16:
        return 1
    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", clean)
    if not words or len(words) > 12:
        return None
    significant = [word for word in words if len(word) > 2]
    ratio = (
        sum(word[:1].isupper() for word in significant) / len(significant)
        if significant
        else 0.0
    )
    alias_terms = {normalize_text(alias[0]) for alias in ALIASES}
    if (
        any(word.lower() in HEADING_KEYWORDS for word in words) or normalized in alias_terms
    ) and ratio >= 0.55:
        return 2
    return None


def _is_caption(text: str) -> bool:
    clean = text.strip()
    return len(clean) <= 280 and (
        (clean.startswith(("-", "–", "—")) and clean.endswith(("-", "–", "—")))
        or clean.lower().startswith(("figure ", "diagram "))
    )


def _split_sentences(text: str) -> tuple[str, ...]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text.strip())
    return tuple(part.strip() for part in parts if 25 <= len(part.strip()) <= 700)


def _contains_marker(text: str, marker: str) -> bool:
    if re.fullmatch(r"[\w' -]+", marker):
        return bool(re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text))
    return marker in text


def extract_claims(text: str) -> tuple[tuple[str, str, float, str], ...]:
    claims: list[tuple[str, str, float, str]] = []
    for sentence in _split_sentences(text):
        normalized = normalize_text(sentence)
        natural_moves = find_natural_move_mentions(sentence)
        san_moves = find_san_mentions(sentence)
        for claim_type, markers in CLAIM_RULES:
            if any(_contains_marker(normalized, marker) for marker in markers):
                if natural_moves or san_moves:
                    safe_prefix = re.split(
                        r"\s+[–—-]\s+(?=if\b)",
                        sentence,
                        maxsplit=1,
                        flags=re.I,
                    )[0].strip()
                    if (
                        safe_prefix != sentence
                        and len(safe_prefix) >= 25
                        and not find_natural_move_mentions(safe_prefix)
                        and not find_san_mentions(safe_prefix)
                    ):
                        claims.append(
                            (
                                claim_type,
                                safe_prefix.rstrip(" -–—"),
                                0.68,
                                "source_only",
                            )
                        )
                unsafe = claim_type == "statistic" or bool(natural_moves) or bool(san_moves)
                claims.append(
                    (
                        claim_type,
                        sentence,
                        0.82 if claim_type in {"statistic", "warning"} else 0.72,
                        "unverified" if unsafe else "source_only",
                    )
                )
                break
    return tuple(claims)


def matched_concepts(text: str) -> dict[str, tuple[str, float]]:
    normalized = normalize_text(text)
    matches: dict[str, tuple[str, float]] = {}
    for canonical, (category, markers) in CONCEPT_RULES.items():
        if any(marker in normalized for marker in markers):
            matches[canonical] = (category, 0.70)
    for term, canonical, _language in ALIASES:
        if normalize_text(term) in normalized:
            matches[canonical] = ("opening", 0.92)
    return matches


def _insert_seeds(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT OR IGNORE INTO aliases(term, normalized_term, canonical_name, language)
        VALUES(?, ?, ?, ?)
        """,
        (
            (term, normalize_text(term), canonical, language)
            for term, canonical, language in ALIASES
        ),
    )
    for canonical, (category, _markers) in CONCEPT_RULES.items():
        connection.execute(
            "INSERT OR IGNORE INTO concepts(canonical_name, category) VALUES(?, ?)",
            (canonical, category),
        )


def compile_pdf(
    pdf_path: str | Path,
    database_path: str | Path,
    *,
    max_chunk_chars: int = 1800,
) -> CompileStats:
    source = Path(pdf_path).expanduser().resolve()
    extraction = extract_pdf(source)
    sha256 = _sha256_file(source)
    book_id = f"book_{sha256[:16]}"
    database = Path(database_path).expanduser().resolve()
    connection = connect_writable(database)
    initialize(connection)
    repeated = _repeated_block_texts(extraction.pages)
    page_types = _page_types(extraction.pages)
    likely_boards = sum(image.likely_board for image in extraction.images)

    with transaction(connection):
        delete_book(connection, book_id)
        _insert_seeds(connection)
        connection.execute(
            """
            INSERT INTO books(
                id, sha256, title, author, publication_year, source_path,
                file_size, page_count, metadata_json, extraction_version, imported_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                sha256,
                extraction.metadata.title,
                extraction.metadata.author,
                extraction.metadata.publication_year,
                str(source),
                extraction.metadata.file_size,
                extraction.metadata.page_count,
                json.dumps(extraction.metadata.raw, ensure_ascii=False),
                EXTRACTION_VERSION,
                datetime.now(UTC).isoformat(),
            ),
        )
        stored_spans: list[StoredSpan] = []
        span_levels: dict[int, int] = {}
        for page in extraction.pages:
            page_type = page_types[page.page_number]
            page_cursor = connection.execute(
                """
                INSERT INTO pages(
                    book_id, page_number, page_type, width, height, text,
                    text_sha256, word_count
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    page.page_number,
                    page_type,
                    page.width,
                    page.height,
                    page.text,
                    _sha256_text(page.text),
                    len(page.text.split()),
                ),
            )
            if page_type == "content" and len(page.text.strip()) < 120:
                connection.execute(
                    """
                    INSERT INTO issues(book_id, page_number, issue_type, severity, message)
                    VALUES(?, ?, 'sparse_page_text', 'warning', ?)
                    """,
                    (book_id, page.page_number, "Content page has little extractable text"),
                )
            for block in page.blocks:
                normalized = normalize_text(block.text)
                level = heading_level(block.text) if page_type == "content" else None
                if normalized in repeated:
                    kind = "header_footer"
                elif level:
                    kind = "heading"
                elif _is_caption(block.text):
                    kind = "caption"
                else:
                    kind = "body"
                cursor = connection.execute(
                    """
                    INSERT INTO spans(
                        book_id, page_id, page_number, ordinal, kind, text,
                        normalized_text, x_min, y_min, x_max, y_max
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        page_cursor.lastrowid,
                        page.page_number,
                        block.ordinal,
                        kind,
                        block.text,
                        normalized,
                        block.x_min,
                        block.y_min,
                        block.x_max,
                        block.y_max,
                    ),
                )
                span_id = int(cursor.lastrowid)
                if page_type == "content":
                    stored_spans.append(StoredSpan(span_id, page.page_number, kind, block.text))
                    if level:
                        span_levels[span_id] = level

        for image in extraction.images:
            connection.execute(
                """
                INSERT INTO diagrams(
                    book_id, page_number, image_number, width, height, encoding, likely_board
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    image.page_number,
                    image.image_number,
                    image.width,
                    image.height,
                    image.encoding,
                    int(image.likely_board),
                ),
            )

        _compile_chunks(
            connection,
            book_id,
            stored_spans,
            span_levels,
            max_chunk_chars=max_chunk_chars,
        )
    connection.execute("PRAGMA optimize")
    connection.commit()
    counts = _counts(connection, book_id)
    connection.close()
    return CompileStats(
        book_id=book_id,
        title=extraction.metadata.title,
        pages=extraction.metadata.page_count,
        spans=counts["spans"],
        sections=counts["sections"],
        chunks=counts["chunks"],
        claims=counts["claims"],
        valid_book_lines=counts["valid_lines"],
        flagged_book_lines=counts["flagged_lines"],
        position_evidence=counts["positions"],
        diagrams=len(extraction.images),
        likely_board_diagrams=likely_boards,
        issues=counts["issues"],
        database_path=str(database),
    )


def _compile_chunks(
    connection: sqlite3.Connection,
    book_id: str,
    spans: list[StoredSpan],
    span_levels: dict[int, int],
    *,
    max_chunk_chars: int,
) -> None:
    chapter_id: int | None = None
    chapter_title = "Book"
    section_id: int | None = None
    section_title = "Unsectioned"
    section_ordinal = 0
    chunk_ordinal = 0
    pending: list[StoredSpan] = []

    def flush() -> None:
        nonlocal chunk_ordinal, pending
        if not pending:
            return
        text = "\n\n".join(span.text for span in pending).strip()
        if not text:
            pending = []
            return
        chunk_ordinal += 1
        page_start = pending[0].page_number
        page_end = pending[-1].page_number
        path_parts = [chapter_title]
        if section_title not in {chapter_title, "Unsectioned"}:
            path_parts.append(section_title)
        section_path = " > ".join(path_parts)
        source_ref = f"{book_id}:p{page_start}-p{page_end}:c{chunk_ordinal:04d}"
        cursor = connection.execute(
            """
            INSERT INTO chunks(
                book_id, section_id, ordinal, title, section_path, page_start,
                page_end, text, text_sha256, char_count, token_estimate, source_ref
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                section_id,
                chunk_ordinal,
                section_title,
                section_path,
                page_start,
                page_end,
                text,
                _sha256_text(text),
                len(text),
                max(1, math.ceil(len(text) / 4)),
                source_ref,
            ),
        )
        chunk_id = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO chunks_fts(chunk_id, title, section_path, text) VALUES(?, ?, ?, ?)",
            (chunk_id, section_title, section_path, text),
        )
        connection.executemany(
            "INSERT INTO chunk_spans(chunk_id, span_id, ordinal) VALUES(?, ?, ?)",
            ((chunk_id, span.id, index) for index, span in enumerate(pending)),
        )
        for source_span in pending:
            for claim_type, claim_text, confidence, status in extract_claims(source_span.text):
                connection.execute(
                    """
                    INSERT INTO claims(
                        book_id, chunk_id, span_id, page_number, claim_type, text,
                        confidence, extraction_method, validation_status
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, 'keyword-rules-v1', ?)
                    """,
                    (
                        book_id,
                        chunk_id,
                        source_span.id,
                        source_span.page_number,
                        claim_type,
                        claim_text,
                        confidence,
                        status,
                    ),
                )
                if status == "unverified":
                    issue_type = (
                        "unverified_statistic"
                        if claim_type == "statistic"
                        else "contextual_move_claim"
                    )
                    connection.execute(
                        """
                        INSERT INTO issues(
                            book_id, chunk_id, page_number, issue_type,
                            severity, message, context
                        ) VALUES(?, ?, ?, ?, 'warning', ?, ?)
                        """,
                        (
                            book_id,
                            chunk_id,
                            source_span.page_number,
                            issue_type,
                            "Claim is retained as source material but excluded "
                            "from normal tutor facts",
                            claim_text,
                        ),
                    )
        for canonical, (category, confidence) in matched_concepts(text).items():
            connection.execute(
                "INSERT OR IGNORE INTO concepts(canonical_name, category) VALUES(?, ?)",
                (canonical, category),
            )
            concept_id = connection.execute(
                "SELECT id FROM concepts WHERE canonical_name = ?", (canonical,)
            ).fetchone()[0]
            connection.execute(
                """
                INSERT OR REPLACE INTO chunk_concepts(
                    chunk_id, concept_id, confidence, extraction_method
                ) VALUES(?, ?, ?, 'keyword-rules-v1')
                """,
                (chunk_id, concept_id, confidence),
            )
        _compile_lines(connection, book_id, chunk_id, page_start, text)
        pending = []

    for span in spans:
        if span.kind == "heading":
            flush()
            level = span_levels[span.id]
            title = re.sub(r"\s+", " ", span.text).strip(" -–—")
            section_ordinal += 1
            parent_id = chapter_id if level > 1 else None
            cursor = connection.execute(
                """
                INSERT INTO sections(
                    book_id, parent_id, title, normalized_title, level,
                    ordinal, page_start, page_end
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    parent_id,
                    title,
                    normalize_text(title),
                    level,
                    section_ordinal,
                    span.page_number,
                    span.page_number,
                ),
            )
            if level == 1:
                chapter_id = int(cursor.lastrowid)
                chapter_title = title
            section_id = int(cursor.lastrowid)
            section_title = title
            continue
        if span.kind not in {"body", "caption"}:
            continue
        current_chars = sum(len(item.text) for item in pending)
        if pending and current_chars + len(span.text) > max_chunk_chars:
            flush()
        pending.append(span)
        if section_id:
            connection.execute(
                "UPDATE sections SET page_end = max(page_end, ?) WHERE id = ?",
                (span.page_number, section_id),
            )
    flush()


def _compile_lines(
    connection: sqlite3.Connection,
    book_id: str,
    chunk_id: int,
    page_number: int,
    text: str,
) -> None:
    for candidate in find_pgn_candidates(text):
        line = validate_pgn_candidate(candidate)
        cursor = connection.execute(
            """
            INSERT INTO book_lines(
                book_id, chunk_id, page_number, raw_text, normalized_pgn,
                start_fen, end_fen, san_line, uci_line, ply_count,
                validation_status, error
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                chunk_id,
                page_number,
                line.raw_text,
                line.normalized_pgn,
                line.start_fen,
                line.end_fen,
                " ".join(line.san_moves) or None,
                " ".join(line.uci_moves) or None,
                len(line.san_moves),
                line.status,
                line.error,
            ),
        )
        line_id = int(cursor.lastrowid)
        if line.status == "valid":
            if candidate.start_offset <= 80:
                # The prose following a displayed line normally comments on the
                # final diagram position, not every prefix along the way. Embedded
                # comparison lines remain searchable but must not anchor the whole
                # surrounding chunk to an unrelated position.
                final_state = line.positions[-1]
                connection.execute(
                    """
                    INSERT INTO book_position_evidence(
                        position_key, line_id, book_id, chunk_id, page_number,
                        ply, incoming_san, incoming_uci
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        final_state.position_key,
                        line_id,
                        book_id,
                        chunk_id,
                        page_number,
                        final_state.ply,
                        final_state.incoming_san,
                        final_state.incoming_uci,
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO issues(
                        book_id, chunk_id, page_number, issue_type,
                        severity, message, context
                    ) VALUES(?, ?, ?, 'embedded_valid_line_not_position_anchor', 'info', ?, ?)
                    """,
                    (
                        book_id,
                        chunk_id,
                        page_number,
                        "Legal line retained for search but not used as a position anchor",
                        line.raw_text,
                    ),
                )
        else:
            connection.execute(
                """
                INSERT INTO issues(
                    book_id, chunk_id, page_number, issue_type, severity, message, context
                ) VALUES(?, ?, ?, 'invalid_or_contextual_book_line', 'warning', ?, ?)
                """,
                (book_id, chunk_id, page_number, line.error or line.status, line.raw_text),
            )
    mentions = sorted(set(find_natural_move_mentions(text)))
    if mentions:
        connection.execute(
            """
            INSERT INTO issues(
                book_id, chunk_id, page_number, issue_type, severity, message, context
            ) VALUES(?, ?, ?, 'natural_language_moves_unparsed', 'info', ?, ?)
            """,
            (
                book_id,
                chunk_id,
                page_number,
                f"{len(mentions)} natural-language move mentions require contextual review",
                "; ".join(mentions[:12]),
            ),
        )


def _counts(connection: sqlite3.Connection, book_id: str) -> dict[str, int]:
    tables = ("spans", "sections", "chunks", "claims", "issues")
    counts = {
        table: connection.execute(
            f"SELECT count(*) FROM {table} WHERE book_id = ?", (book_id,)
        ).fetchone()[0]
        for table in tables
    }
    counts["valid_lines"] = connection.execute(
        "SELECT count(*) FROM book_lines WHERE book_id = ? AND validation_status = 'valid'",
        (book_id,),
    ).fetchone()[0]
    counts["flagged_lines"] = connection.execute(
        "SELECT count(*) FROM book_lines WHERE book_id = ? AND validation_status != 'valid'",
        (book_id,),
    ).fetchone()[0]
    counts["positions"] = connection.execute(
        "SELECT count(*) FROM book_position_evidence WHERE book_id = ?", (book_id,)
    ).fetchone()[0]
    return counts
