from chess_coach.tutor import TutorText, _is_grounded_rewrite, _parse_model_json


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
