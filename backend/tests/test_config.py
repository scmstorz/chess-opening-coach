from pathlib import Path

import pytest
from chess_coach.api import build_service
from chess_coach.config import Settings


def _settings(tmp_path: Path, *, runtime_profile: str, books_enabled: bool) -> Settings:
    return Settings(
        runtime_profile=runtime_profile,
        database_path=tmp_path / "coach.db",
        opening_data_path=tmp_path / "openings",
        book_database_path=tmp_path / "private-books.db",
        books_enabled=books_enabled,
        stockfish_path=None,
        ollama_model=None,
    )


def test_public_profile_disables_private_book_knowledge_even_when_enabled(
    tmp_path: Path,
) -> None:
    service = build_service(_settings(tmp_path, runtime_profile="PUBLIC", books_enabled=True))
    try:
        status = service.book_knowledge.status()
        assert service.runtime_profile == "public"
        assert status["available"] is False
        assert "öffentlichen Laufzeitprofil" in status["reason"]
    finally:
        service.engine.close()
        service.store.close()


def test_local_profile_keeps_private_book_knowledge_opt_in(tmp_path: Path) -> None:
    service = build_service(_settings(tmp_path, runtime_profile="local", books_enabled=True))
    try:
        status = service.book_knowledge.status()
        assert service.runtime_profile == "local"
        assert status["reason"] == "Die lokale Buchdatenbank fehlt."
    finally:
        service.engine.close()
        service.store.close()


def test_unknown_runtime_profile_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported CHESS_COACH_RUNTIME_PROFILE"):
        _settings(tmp_path, runtime_profile="hybrid", books_enabled=True)
