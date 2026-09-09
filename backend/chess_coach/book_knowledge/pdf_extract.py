from __future__ import annotations

import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from chess_coach.book_knowledge.models import (
    ExtractedPage,
    PDFExtraction,
    PDFImage,
    PDFMetadata,
    TextBlock,
)


class PDFExtractionError(RuntimeError):
    pass


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise PDFExtractionError(f"Required Poppler tool '{name}' was not found on PATH")
    return path


def _run(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise PDFExtractionError(detail) from exc
    return completed.stdout


def infer_filename_metadata(path: Path) -> tuple[str, str | None, int | None]:
    stem = path.stem.strip()
    year_match = re.search(r"\((?:19|20)\d{2}\)\s*$", stem)
    publication_year = int(year_match.group(0)[1:5]) if year_match else None
    if year_match:
        stem = stem[: year_match.start()].strip()
    author: str | None = None
    title = stem
    if " - " in stem:
        author_part, title_part = stem.split(" - ", 1)
        author = author_part.strip() or None
        title = title_part.strip() or stem
    return title, author, publication_year


def extract_metadata(path: Path) -> PDFMetadata:
    output = _run([_require_tool("pdfinfo"), str(path)])
    raw: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        raw[key.strip()] = value.strip()
    fallback_title, fallback_author, fallback_year = infer_filename_metadata(path)
    try:
        page_count = int(raw.get("Pages", "0"))
    except ValueError as exc:
        raise PDFExtractionError("pdfinfo did not return a valid page count") from exc
    return PDFMetadata(
        title=raw.get("Title") or fallback_title,
        author=raw.get("Author") or fallback_author,
        publication_year=fallback_year,
        page_count=page_count,
        file_size=path.stat().st_size,
        raw=raw,
    )


def _join_lines(lines: list[str]) -> str:
    if not lines:
        return ""
    result = lines[0].strip()
    for line in lines[1:]:
        clean = line.strip()
        if not clean:
            continue
        if result.endswith("-") and clean[:1].islower():
            result = result[:-1] + clean
        else:
            result += " " + clean
    return re.sub(r"\s+", " ", result).strip()


def parse_bbox_xml(xml_text: str) -> tuple[ExtractedPage, ...]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise PDFExtractionError(f"Could not parse pdftotext XHTML: {exc}") from exc
    namespace = "{http://www.w3.org/1999/xhtml}"
    pages: list[ExtractedPage] = []
    for page_number, page_element in enumerate(
        root.findall(f".//{namespace}page"), start=1
    ):
        blocks: list[TextBlock] = []
        for block_element in page_element.findall(f".//{namespace}block"):
            line_texts: list[str] = []
            for line_element in block_element.findall(f"./{namespace}line"):
                words = [
                    word.text or ""
                    for word in line_element.findall(f"./{namespace}word")
                ]
                line_text = " ".join(word for word in words if word).strip()
                if line_text:
                    line_texts.append(line_text)
            text = _join_lines(line_texts)
            if not text:
                continue
            blocks.append(
                TextBlock(
                    page_number=page_number,
                    ordinal=len(blocks),
                    text=text,
                    x_min=float(block_element.attrib.get("xMin", 0.0)),
                    y_min=float(block_element.attrib.get("yMin", 0.0)),
                    x_max=float(block_element.attrib.get("xMax", 0.0)),
                    y_max=float(block_element.attrib.get("yMax", 0.0)),
                )
            )
        pages.append(
            ExtractedPage(
                page_number=page_number,
                width=float(page_element.attrib.get("width", 0.0)),
                height=float(page_element.attrib.get("height", 0.0)),
                blocks=tuple(blocks),
            )
        )
    return tuple(pages)


def extract_pages(path: Path) -> tuple[ExtractedPage, ...]:
    xml_text = _run([_require_tool("pdftotext"), "-bbox-layout", str(path), "-"])
    return parse_bbox_xml(xml_text)


def infer_publication_year_from_pages(pages: tuple[ExtractedPage, ...]) -> int | None:
    """Use only explicit publication wording, not arbitrary front-matter dates."""
    frontmatter = " ".join(page.text for page in pages[:30])
    match = re.search(
        r"\b(?:was|first) published in ((?:19|20)\d{2})\b",
        frontmatter,
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


def extract_images(path: Path) -> tuple[PDFImage, ...]:
    output = _run([_require_tool("pdfimages"), "-list", str(path)])
    images: list[PDFImage] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 10 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        try:
            images.append(
                PDFImage(
                    page_number=int(parts[0]),
                    image_number=int(parts[1]),
                    image_type=parts[2],
                    width=int(parts[3]),
                    height=int(parts[4]),
                    encoding=parts[8],
                )
            )
        except (IndexError, ValueError):
            continue
    return tuple(images)


def extract_pdf(path: str | Path) -> PDFExtraction:
    pdf_path = Path(path).expanduser().resolve()
    if not pdf_path.is_file():
        raise PDFExtractionError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise PDFExtractionError(f"Expected a PDF file: {pdf_path}")
    metadata = extract_metadata(pdf_path)
    pages = extract_pages(pdf_path)
    if metadata.publication_year is None:
        metadata = replace(
            metadata,
            publication_year=infer_publication_year_from_pages(pages),
        )
    if metadata.page_count and len(pages) != metadata.page_count:
        raise PDFExtractionError(
            f"Page count mismatch: pdfinfo={metadata.page_count}, extracted={len(pages)}"
        )
    return PDFExtraction(metadata=metadata, pages=pages, images=extract_images(pdf_path))
