from pathlib import Path
from typing import Any

from chess_coach.book_knowledge.models import BookCitation, BookEvidence, BookFact
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import SourceSynthesis, TutorText
from test_service import FakeEngine


class FakeBookKnowledge:
    def status(self) -> dict[str, Any]:
        return {"available": True, "book_count": 1, "chunk_count": 1, "reason": None}

    def retrieve(self, **_: Any) -> BookEvidence:
        citation = BookCitation(
            "book_test",
            "Test Book",
            "Test Author",
            2026,
            Path("/private/library/test.pdf"),
            18,
            20,
            "book_test:p18-p20:c0001",
        )
        return BookEvidence(
            (
                BookFact(
                    "book:1",
                    "The plan is pressure on the center.",
                    "plan",
                    "source_only",
                    citation,
                    (),
                    "opening",
                ),
            ),
            "fixture",
            False,
        )


class FakeGroundedBookTutor:
    model = "local-test"

    def status(self) -> dict[str, Any]:
        return {"available": True, "model": self.model, "reason": None}

    def explain(self, facts: dict[str, Any], fallback: TutorText) -> TutorText:
        del facts
        return fallback

    def answer_question(self, facts: dict[str, Any], fallback: TutorText) -> TutorText:
        del facts
        return fallback

    def synthesize_book_explanation(self, **values: Any) -> SourceSynthesis:
        if not values.get("book_facts"):
            return SourceSynthesis(None, "insufficient_evidence", "no_safe_book_facts", ())
        return SourceSynthesis(
            TutorText(
                "Die Buchquelle beschreibt Druck auf das Zentrum als langfristige Idee.",
                "Die vorhandenen Brett- und Enginefakten bleiben davon getrennt.",
                "ollama-book-grounded",
                self.model,
            ),
            "grounded",
            None,
            ("book:1",),
        )


def test_question_adds_german_book_synthesis_and_path_free_reference() -> None:
    coach = CoachService(
        OpeningBook(),
        FakeEngine(),
        FakeGroundedBookTutor(),
        SQLiteStore(":memory:"),
        book_knowledge=FakeBookKnowledge(),
    )
    session = coach.create_session("white")

    message = coach.answer_question(
        session["session_id"], "Warum ist e4 langfristig sinnvoll?", "e2e4"
    )["message"]

    assert message["source"] == "ollama-book-grounded"
    assert message["summary"].startswith("Die Buchquelle beschreibt")
    assert message["knowledge"]["status"] == "grounded"
    assert message["references"] == [
        {
            "kind": "book",
            "book_id": "book_test",
            "title": "Test Book",
            "author": "Test Author",
            "year": 2026,
            "pdf_page_start": 18,
            "pdf_page_end": 20,
            "source_ref": "book_test:p18-p20:c0001",
            "status": "source_only",
            "warnings": [],
            "match_kind": "opening",
        }
    ]
    assert "/private/" not in str(message)
    assert message["explanation_sections"][0]["title"] == "Buchgestützter Plan"


def test_question_states_knowledge_boundary_when_no_causal_reason_is_supported() -> None:
    coach = CoachService(
        OpeningBook(),
        FakeEngine(),
        FakeGroundedBookTutor(),
        SQLiteStore(":memory:"),
    )
    session = coach.create_session("white")

    message = coach.answer_question(
        session["session_id"], "Warum ist Nh3 langfristig gut?", "g1h3"
    )["message"]

    assert message["knowledge"]["status"] == "insufficient_evidence"
    assert "keine ausreichend belegte Erklärung" in message["summary"]
    assert all(
        section["title"] != "Wissensgrenze"
        for section in message["explanation_sections"]
    )
