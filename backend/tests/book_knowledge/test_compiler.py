import sqlite3
from pathlib import Path

from chess_coach.book_knowledge import compiler
from chess_coach.book_knowledge.models import (
    ExtractedPage,
    PDFExtraction,
    PDFMetadata,
    TextBlock,
)
from chess_coach.book_knowledge.schema import connect_writable, initialize, integrity_report


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
