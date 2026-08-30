from typing import Any

from chess_coach.tutor import OllamaTutor, TutorText, _is_grounded_rewrite, _parse_model_json


class SelectionTutor(OllamaTutor):
    def __init__(self, response: str) -> None:
        super().__init__("http://127.0.0.1:1", "test-model")
        self.response = response

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"message": {"content": self.response}}


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
