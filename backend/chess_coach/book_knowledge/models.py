from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PDFMetadata:
    title: str
    author: str | None
    publication_year: int | None
    page_count: int
    file_size: int
    raw: dict[str, str]


@dataclass(frozen=True, slots=True)
class TextBlock:
    page_number: int
    ordinal: int
    text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    width: float
    height: float
    blocks: tuple[TextBlock, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.text)


@dataclass(frozen=True, slots=True)
class PDFImage:
    page_number: int
    image_number: int
    image_type: str
    width: int
    height: int
    encoding: str

    @property
    def likely_board(self) -> bool:
        if min(self.width, self.height) < 280:
            return False
        ratio = self.width / self.height
        return 0.82 <= ratio <= 1.18 and max(self.width, self.height) <= 1200


@dataclass(frozen=True, slots=True)
class PDFExtraction:
    metadata: PDFMetadata
    pages: tuple[ExtractedPage, ...]
    images: tuple[PDFImage, ...]


@dataclass(frozen=True, slots=True)
class CompileStats:
    book_id: str
    title: str
    pages: int
    spans: int
    sections: int
    chunks: int
    claims: int
    valid_book_lines: int
    flagged_book_lines: int
    position_evidence: int
    diagrams: int
    likely_board_diagrams: int
    issues: int
    database_path: str

    def as_dict(self) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class BookCitation:
    book_id: str
    title: str
    author: str | None
    publication_year: int | None
    source_path: Path
    page_start: int
    page_end: int
    source_ref: str

    def public_dict(self) -> dict[str, Any]:
        """Return browser-safe metadata without the local filesystem path."""
        return {
            "kind": "book",
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "year": self.publication_year,
            "pdf_page_start": self.page_start,
            "pdf_page_end": self.page_end,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BookFact:
    id: str
    text: str
    claim_type: str
    validation_status: str
    citation: BookCitation
    warnings: tuple[str, ...]
    match_kind: str

    def public_reference(self) -> dict[str, Any]:
        return {
            **self.citation.public_dict(),
            "status": self.validation_status,
            "warnings": list(self.warnings),
            "match_kind": self.match_kind,
        }


@dataclass(frozen=True, slots=True)
class BookEvidence:
    facts: tuple[BookFact, ...]
    query_method: str
    truncated: bool
    reason: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.facts)

    def public_references(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        references: list[dict[str, Any]] = []
        for fact in self.facts:
            if fact.citation.source_ref in seen:
                continue
            seen.add(fact.citation.source_ref)
            references.append(fact.public_reference())
        return references


@dataclass(frozen=True, slots=True)
class KnowledgeStatus:
    available: bool
    book_count: int
    chunk_count: int
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "book_count": self.book_count,
            "chunk_count": self.chunk_count,
            "reason": self.reason,
        }

