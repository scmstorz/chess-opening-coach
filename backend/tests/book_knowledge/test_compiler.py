import sqlite3
from pathlib import Path

import chess
from chess_coach.book_knowledge import compiler
from chess_coach.book_knowledge.models import (
    ExtractedPage,
    PDFExtraction,
    PDFMetadata,
    TextBlock,
)
from chess_coach.book_knowledge.retrieval import BookKnowledgeBase
from chess_coach.book_knowledge.schema import connect_writable, initialize, integrity_report
from chess_coach.openings import OpeningIdentity


def _extraction(title: str = "Test Openings") -> PDFExtraction:
    return PDFExtraction(
        metadata=PDFMetadata(title, "Test Author", 2026, 3, 10, {"Title": title}),
        pages=(
            ExtractedPage(1, 612, 792, (TextBlock(1, 0, title, 72, 72, 300, 100),)),
            ExtractedPage(
                2,
                612,
                792,
                (
                    TextBlock(2, 0, "Ruy Lopez", 72, 80, 220, 105),
                    TextBlock(
                        2,
                        1,
                        (
                            "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6. "
                            "The main plan is to control the center. This line wins 63% of games. "
                            "Move the kingside bishop to b5. The line is "
                            "3. Bb5 a6."
                        ),
                        72,
                        120,
                        540,
                        240,
                    ),
                ),
            ),
            ExtractedPage(3, 612, 792, (TextBlock(3, 0, "x", 72, 80, 80, 90),)),
        ),
        images=(),
    )


def test_full_import_is_idempotent_and_quarantines_unsafe_claims(
    tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "Test Author - Test Openings (2026).pdf"
    pdf.write_bytes(b"fake-pdf")
    database = tmp_path / "knowledge.db"
    monkeypatch.setattr(compiler, "extract_pdf", lambda _: _extraction())

    first = compiler.compile_pdf(pdf, database)
    second = compiler.compile_pdf(pdf, database)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    statuses = [
        tuple(row)
        for row in connection.execute(
            "SELECT claim_type, validation_status, page_number FROM claims ORDER BY id"
        )
    ]
    assert first.book_id == second.book_id
    assert connection.execute("SELECT count(*) FROM books").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM chunks").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0] == 1
    assert ("plan", "source_only", 2) in statuses
    assert ("statistic", "unverified", 2) in statuses
    assert connection.execute(
        "SELECT count(*) FROM issues WHERE issue_type = 'sparse_page_text'"
    ).fetchone()[0] == 1
    assert connection.execute(
        "SELECT count(*) FROM book_position_evidence"
    ).fetchone()[0] == 1
    connection.close()


def test_integrity_report_confirms_fts_and_real_query_indexes(tmp_path: Path) -> None:
    connection = connect_writable(tmp_path / "knowledge.db")
    initialize(connection)
    report = integrity_report(connection)
    connection.close()

    assert report["integrity"] == "ok"
    assert report["fts_in_sync"] is True
    assert report["position_query_uses_index"] is True
    assert report["issue_query_uses_index"] is True


def test_claim_extraction_keeps_safe_plan_prefix_and_quarantines_move_tail() -> None:
    claims = compiler.extract_claims(
        "This opening has two main purposes – disrupting the pawn structure and taking "
        "over the central territory – If your opening is with Knight to f3 and pawn to e4."
    )

    assert any(status == "source_only" and "Knight" not in text for _, text, _, status in claims)
    assert any(status == "unverified" and "Knight to f3" in text for _, text, _, status in claims)


def test_claim_extraction_quarantines_unpositioned_san_and_matches_whole_words() -> None:
    san_claims = compiler.extract_claims(
        "White should play Bb5 to increase the pressure on e5."
    )
    false_warning = compiler.extract_claims(
        "Nevertheless, this quiet continuation remains popular."
    )

    assert any(status == "unverified" for _, _, _, status in san_claims)
    assert false_warning == ()


def test_compiler_resolves_one_unambiguous_local_variation_fragment(
    tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "Context Book.pdf"
    pdf.write_bytes(b"fake-pdf")
    database = tmp_path / "knowledge.db"
    extraction = PDFExtraction(
        metadata=PDFMetadata("Context Book", "Author", 2026, 2, 8, {}),
        pages=(
            ExtractedPage(
                1,
                612,
                792,
                (TextBlock(1, 0, "Context Book", 72, 80, 220, 105),),
            ),
            ExtractedPage(
                2,
                612,
                792,
                (
                    TextBlock(2, 0, "Ruy Lopez", 72, 80, 220, 105),
                    TextBlock(
                        2,
                        1,
                        "1. e4 e5 2. Nf3 Nc6 3. Bb5. 3...a6 4. Ba4.",
                        72,
                        120,
                        540,
                        180,
                    ),
                ),
            ),
        ),
        images=(),
    )
    monkeypatch.setattr(compiler, "extract_pdf", lambda _: extraction)

    compiler.compile_pdf(pdf, database)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    lines = connection.execute(
        """SELECT id, validation_status, context_method, context_parent_line_id,
                  absolute_start_ply, absolute_end_ply
           FROM book_lines ORDER BY id"""
    ).fetchall()
    assert [row["validation_status"] for row in lines] == ["valid", "context_resolved"]
    assert lines[1]["context_parent_line_id"] == lines[0]["id"]
    assert lines[1]["context_method"] == "same_chunk_verified_parent"
    assert (lines[1]["absolute_start_ply"], lines[1]["absolute_end_ply"]) == (5, 7)
    assert connection.execute(
        """SELECT count(*) FROM issues
           WHERE issue_type = 'invalid_or_contextual_book_line' AND status = 'open'"""
    ).fetchone()[0] == 0
    connection.close()


def test_compiler_positions_progressive_annotated_moves_and_only_their_claims(
    tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "Progressive Book.pdf"
    pdf.write_bytes(b"fake-pdf")
    database = tmp_path / "knowledge.db"
    extraction = PDFExtraction(
        metadata=PDFMetadata("Progressive Book", "Author", 2026, 2, 8, {}),
        pages=(
            ExtractedPage(
                1,
                612,
                792,
                (TextBlock(1, 0, "Progressive Book", 72, 80, 220, 105),),
            ),
            ExtractedPage(
                2,
                612,
                792,
                (
                    TextBlock(2, 0, "Ruy Lopez", 72, 80, 220, 105),
                    TextBlock(
                        2,
                        1,
                        (
                            "1 e4 e5 2 Nf3. White develops a piece. "
                            "2 ... Nc6. The point of Nc6 is to guard e5. "
                            "3 Bb5. The point of Bb5 is seen if Black reinforces with ... "
                            "3 ... d6."
                        ),
                        72,
                        120,
                        540,
                        220,
                    ),
                    TextBlock(
                        2,
                        2,
                        (
                            "The knight on c6 is then pinned to the king. "
                            "The point of d6 is to reinforce e5."
                        ),
                        72,
                        230,
                        540,
                        270,
                    ),
                    TextBlock(
                        2,
                        3,
                        "Conclusion: the plan is an unrelated general lesson.",
                        72,
                        280,
                        540,
                        310,
                    ),
                ),
            ),
        ),
        images=(),
    )
    monkeypatch.setattr(compiler, "extract_pdf", lambda _: extraction)

    compiler.compile_pdf(pdf, database)

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    progressive = connection.execute(
        """
        SELECT san_line, context_method FROM book_lines
        WHERE context_method = 'progressive_annotated_move' ORDER BY id
        """
    ).fetchall()
    assert [row["san_line"] for row in progressive] == ["Nc6", "Bb5", "d6"]
    positioned_claims = connection.execute(
        """
        SELECT text, validation_status, focus_move_uci, position_key
        FROM claims WHERE position_key IS NOT NULL ORDER BY id
        """
    ).fetchall()
    assert len(positioned_claims) == 3
    assert [row["validation_status"] for row in positioned_claims] == [
        "legality_checked",
        "legality_checked",
        "legality_checked",
    ]
    assert {row["focus_move_uci"] for row in positioned_claims} == {
        "b8c6",
        "f1b5",
        "d7d6",
    }
    assert all("unrelated general lesson" not in row["text"] for row in positioned_claims)
    connection.close()

    board = chess.Board()
    for san in ("e4", "e5", "Nf3", "Nc6"):
        board.push_san(san)
    evidence = BookKnowledgeBase(database).retrieve(
        question="Warum ist Bb5 sinnvoll?",
        board=board,
        opening=OpeningIdentity("C60", "Ruy Lopez"),
        focus_move=board.parse_san("Bb5"),
    )
    assert [fact.text for fact in evidence.facts] == [
        "The point of Bb5 is seen if Black reinforces with 3 ... d6. "
        "The knight on c6 is then pinned to the king."
    ]


def test_compiler_rejects_equal_progressive_variations_instead_of_guessing(
    tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "Ambiguous Book.pdf"
    pdf.write_bytes(b"fake-pdf")
    database = tmp_path / "knowledge.db"
    extraction = PDFExtraction(
        metadata=PDFMetadata("Ambiguous Book", "Author", 2026, 2, 8, {}),
        pages=(
            ExtractedPage(
                1,
                612,
                792,
                (TextBlock(1, 0, "Ambiguous Book", 72, 80, 220, 105),),
            ),
            ExtractedPage(
                2,
                612,
                792,
                (
                    TextBlock(2, 0, "Ruy Lopez", 72, 80, 220, 105),
                    TextBlock(
                        2,
                        1,
                        (
                            "1 e4 e5 2 Nf3. One branch follows. "
                            "2 ... Nc6. A normal reply. 3 Bb5. "
                            "Another branch follows. 2 ... Nf6. A counterattack. 3 Nxe5."
                        ),
                        72,
                        120,
                        540,
                        260,
                    ),
                ),
            ),
        ),
        images=(),
    )
    monkeypatch.setattr(compiler, "extract_pdf", lambda _: extraction)

    compiler.compile_pdf(pdf, database)

    connection = sqlite3.connect(database)
    assert connection.execute(
        """SELECT count(*) FROM book_lines
           WHERE context_method = 'progressive_annotated_move'"""
    ).fetchone()[0] == 0
    assert connection.execute(
        """SELECT count(*) FROM issues
           WHERE issue_type = 'ambiguous_progressive_annotated_moves'"""
    ).fetchone()[0] == 1
    connection.close()
