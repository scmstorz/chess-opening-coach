from typing import Any

from chess_coach.tutor import OllamaTutor, TutorText, _is_grounded_rewrite, _parse_model_json


class SelectionTutor(OllamaTutor):
    def __init__(self, response: str) -> None:
        super().__init__("http://127.0.0.1:1", "test-model")
        self.response = response

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"message": {"content": self.response}}


class QueuedTutor(OllamaTutor):
    def __init__(self, responses: list[str]) -> None:
        super().__init__("http://127.0.0.1:1", "test-model")
        self.responses = responses

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        del path, payload
        return {"message": {"content": self.responses.pop(0)}}


def test_parses_markdown_wrapped_model_json() -> None:
    parsed = _parse_model_json('json\n```json\n{"summary":"Gut.","details":["Ein", "Detail"]}\n```')

    assert parsed["summary"] == "Gut."
    assert parsed["details"] == ["Ein", "Detail"]


def test_grounding_rejects_new_opening_claims_and_numbers() -> None:
    fallback = TutorText(
        summary="e4 ist objektiv stark.",
        details="Stockfish bewertet den Zug mit +0,46.",
        source="deterministic",
        model=None,
    )
    safe = TutorText(
        summary="e4 ist ein starker Zug.",
        details="Die Bewertung von Stockfish liegt bei +0,46.",
        source="ollama",
        model="test",
    )
    invented = TutorText(
        summary="e4 führt zur Sizilianischen Verteidigung.",
        details="Die Bewertung liegt bei +0,80.",
        source="ollama",
        model="test",
    )

    assert _is_grounded_rewrite(safe, fallback) is True
    assert _is_grounded_rewrite(invented, fallback) is False


def test_grounding_keeps_concrete_explanation_in_details() -> None:
    fallback = TutorText(
        summary="c3 ist eine kleine Ungenauigkeit.",
        details="c3 kontrolliert b4 und d4. Stockfish bevorzugt Ba4.",
        source="deterministic",
        model=None,
    )
    misplaced = TutorText(
        summary="c3 kontrolliert b4 und d4; besser ist Ba4.",
        details="Der Bauernzug verändert die Stellung.",
        source="ollama",
        model="test",
    )

    assert _is_grounded_rewrite(misplaced, fallback) is False


def test_question_tutor_can_only_select_verified_fact_text() -> None:
    fallback = TutorText("Sicher.", "Geprüft.", "deterministic", None)
    facts = {
        "user_question": "Warum?",
        "answer_facts": [
            {"id": "concept", "text": "Der Zug kontrolliert das Zentrum."},
            {"id": "engine", "text": "Stockfish bewertet ihn als stark."},
        ],
    }
    tutor = SelectionTutor('{"summary_fact_ids":["concept"],"detail_fact_ids":["engine"]}')

    result = tutor.answer_question(facts, fallback)

    assert result.summary == "Der Zug kontrolliert das Zentrum."
    assert result.details == "Stockfish bewertet ihn als stark."
    assert result.source == "ollama-selection"


def test_question_tutor_rejects_unknown_fact_ids() -> None:
    fallback = TutorText("Sicher.", "Geprüft.", "deterministic", None)
    facts = {
        "user_question": "Warum?",
        "answer_facts": [
            {"id": "concept", "text": "Der Zug kontrolliert das Zentrum."},
            {"id": "engine", "text": "Stockfish bewertet ihn als stark."},
        ],
    }
    tutor = SelectionTutor('{"summary_fact_ids":["invented"],"detail_fact_ids":["engine"]}')

    result = tutor.answer_question(facts, fallback)

    assert result == fallback
    assert "invalid" in (tutor.last_error or "")


def test_question_tutor_appends_required_verified_facts() -> None:
    fallback = TutorText("Sicher.", "Geprüft.", "deterministic", None)
    facts = {
        "user_question": "Warum?",
        "answer_facts": [
            {"id": "engine", "text": "Stockfish bevorzugt Na2."},
            {"id": "concept", "text": "Na2 kontrolliert kein Zentrumsfeld."},
            {
                "id": "threat",
                "text": "Der Springer auf c3 ist angegriffen.",
                "required": True,
            },
        ],
    }
    tutor = SelectionTutor('{"summary_fact_ids":["engine"],"detail_fact_ids":["concept"]}')

    result = tutor.answer_question(facts, fallback)

    assert result.summary == "Stockfish bevorzugt Na2."
    assert result.details == (
        "Na2 kontrolliert kein Zentrumsfeld. Der Springer auf c3 ist angegriffen."
    )


def test_book_synthesis_requires_evidence_ids_and_a_supporting_critic() -> None:
    tutor = QueuedTutor(
        [
            (
                '{"summary":{"text":"Die Buchquelle nennt Druck auf das Zentrum als Plan.",'
                '"evidence_ids":["book:1"]},"details":[]}'
            ),
            '{"supported":true,"unsupported_claim_indexes":[]}',
        ]
    )

    result = tutor.synthesize_book_explanation(
        question="Was ist der Plan?",
        verified_facts=[],
        book_facts=[
            {
                "id": "book:1",
                "text": "The plan is pressure on the center.",
                "claim_type": "plan",
                "validation_status": "source_only",
            }
        ],
    )

    assert result.status == "grounded"
    assert result.text is not None
    assert result.text.summary == "Die Buchquelle nennt Druck auf das Zentrum als Plan."
    assert result.evidence_ids == ("book:1",)


def test_book_synthesis_rejects_new_move_anchors_before_rendering() -> None:
    tutor = QueuedTutor(
        [
            (
                '{"summary":{"text":"Der Plan beginnt zwingend mit Ra6.",'
                '"evidence_ids":["book:1"]},"details":[]}'
            )
        ]
    )

    result = tutor.synthesize_book_explanation(
        question="Was ist der Plan?",
        verified_facts=[],
        book_facts=[
            {
                "id": "book:1",
                "text": "The plan is pressure on the center.",
                "claim_type": "plan",
                "validation_status": "source_only",
            }
        ],
    )

    assert result.status == "rejected"
    assert result.text is None


def test_book_synthesis_keeps_opening_claim_separate_and_drops_repetition() -> None:
    tutor = QueuedTutor(
        [
            (
                '{"summary":{"text":"Das Buch beschreibt Druck auf das Zentrum als Plan.",'
                '"evidence_ids":["book:1"]},"details":['
                '{"text":"Der Autor beschreibt Druck auf das Zentrum.",'
                '"evidence_ids":["book:1"]},'
                '{"text":"Bb5 greift den Springer auf c6 an.",'
                '"evidence_ids":["verified:1"]}]}'
            ),
            '{"supported":true,"unsupported_claim_indexes":[]}',
        ]
    )

    result = tutor.synthesize_book_explanation(
        question="Was ist der Plan von Bb5?",
        verified_facts=[
            {"id": "defender", "text": "Bb5 greift den Springer auf c6 an."}
        ],
        book_facts=[
            {
                "id": "book:1",
                "text": "The plan is pressure on the center.",
                "claim_type": "plan",
                "validation_status": "source_only",
                "match_kind": "opening",
            }
        ],
    )

    assert result.status == "grounded"
    assert result.text is not None
    assert result.text.summary == "Das Buch beschreibt Druck auf das Zentrum als Plan."
    assert result.text.details == "Bb5 greift den Springer auf c6 an."
    assert result.evidence_ids == ("book:1", "verified:1")


def test_book_synthesis_rejects_move_level_overstatement_of_opening_claim() -> None:
    tutor = QueuedTutor(
        [
            (
                '{"summary":{"text":"Das Buch beschreibt, dass Bb5 die Struktur stört.",'
                '"evidence_ids":["book:1","verified:1"]},"details":[]}'
            )
        ]
    )

    result = tutor.synthesize_book_explanation(
        question="Was ist der Plan von Bb5?",
        verified_facts=[{"id": "move", "text": "Bb5 ist legal."}],
        book_facts=[
            {
                "id": "book:1",
                "text": "The opening aims to disrupt the pawn structure.",
                "claim_type": "plan",
                "validation_status": "source_only",
                "match_kind": "opening",
            }
        ],
    )

    assert result.status == "rejected"
    assert "opening-level" in (tutor.last_error or "")


def test_book_synthesis_rejects_unattributed_source_only_prose() -> None:
    tutor = QueuedTutor(
        [
            (
                '{"summary":{"text":"Die Eröffnung übt Druck auf das Zentrum aus.",'
                '"evidence_ids":["book:1"]},"details":[]}'
            )
        ]
    )

    result = tutor.synthesize_book_explanation(
        question="Was ist der Plan?",
        verified_facts=[],
        book_facts=[
            {
                "id": "book:1",
                "text": "The plan is pressure on the center.",
                "claim_type": "plan",
                "validation_status": "source_only",
            }
        ],
    )

    assert result.status == "rejected"
    assert "attribution" in (tutor.last_error or "")


def test_book_synthesis_regenerates_once_after_critic_rejection() -> None:
    tutor = QueuedTutor(
        [
            (
                '{"summary":{"text":"Das Buch beschreibt Druck auf das Zentrum.",'
                '"evidence_ids":["book:1"]},"details":[]}'
            ),
            '{"supported":false,"unsupported_claim_indexes":[0]}',
            (
                '{"summary":{"text":"Die Buchquelle beschreibt Druck auf das Zentrum.",'
                '"evidence_ids":["book:1"]},"details":[]}'
            ),
            '{"supported":true,"unsupported_claim_indexes":[]}',
        ]
    )

    result = tutor.synthesize_book_explanation(
        question="Was ist der Plan?",
        verified_facts=[],
        book_facts=[
            {
                "id": "book:1",
                "text": "The plan is pressure on the center.",
                "claim_type": "plan",
                "validation_status": "source_only",
            }
        ],
    )

    assert result.status == "grounded"
    assert result.text is not None
    assert result.text.summary.startswith("Die Buchquelle")


def test_book_synthesis_checks_and_deduplicates_sentences_inside_one_field() -> None:
    tutor = QueuedTutor(
        [
            (
                '{"summary":{"text":"Das Buch beschreibt Druck auf das Zentrum. '
                'Der Autor beschreibt denselben Druck noch einmal.",'
                '"evidence_ids":["book:1"]},"details":[]}'
            ),
            '{"supported":true,"unsupported_claim_indexes":[]}',
        ]
    )

    result = tutor.synthesize_book_explanation(
        question="Was ist der Plan?",
        verified_facts=[],
        book_facts=[
            {
                "id": "book:1",
                "text": "The plan is pressure on the center.",
                "claim_type": "plan",
                "validation_status": "source_only",
            }
        ],
    )

    assert result.status == "grounded"
    assert result.text is not None
    assert result.text.summary == "Das Buch beschreibt Druck auf das Zentrum."
