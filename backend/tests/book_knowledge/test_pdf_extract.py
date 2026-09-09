from pathlib import Path

from chess_coach.book_knowledge.models import ExtractedPage, TextBlock
from chess_coach.book_knowledge.pdf_extract import (
    infer_filename_metadata,
    infer_publication_year_from_pages,
    parse_bbox_xml,
)


def test_bbox_parser_keeps_page_order_coordinates_and_dehyphenates() -> None:
    fixture = Path(__file__).parent / "fixtures" / "bbox.xml"
    pages = parse_bbox_xml(fixture.read_text(encoding="utf-8"))

    assert len(pages) == 1
    assert pages[0].width == 612
    assert pages[0].blocks[0].text == "Ruy Lopez"
    assert pages[0].blocks[1].text == "Control the center with development."
    assert pages[0].blocks[1].x_min == 72


def test_filename_metadata_is_a_safe_fallback() -> None:
    title, author, year = infer_filename_metadata(
        Path("Stewart, Clyde - Chess Openings For Beginners (2021).pdf")
    )

    assert title == "Chess Openings For Beginners"
    assert author == "Stewart, Clyde"
    assert year == 2021


def test_publication_year_requires_explicit_frontmatter_wording() -> None:
    pages = (
        ExtractedPage(
            1,
            612,
            792,
            (
                TextBlock(1, 0, "Converted 2026-09-09", 0, 0, 100, 20),
                TextBlock(1, 1, "This work was published in 2009.", 0, 20, 200, 40),
            ),
        ),
    )

    assert infer_publication_year_from_pages(pages) == 2009
