from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PROFILES = frozenset({"local", "public"})


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True, slots=True)
class Settings:
    runtime_profile: str = os.environ.get("CHESS_COACH_RUNTIME_PROFILE", "local")
    database_path: Path = Path(
        os.environ.get("CHESS_COACH_DATABASE", PROJECT_ROOT / "data" / "coach.db")
    )
    opening_data_path: Path = Path(
        os.environ.get("CHESS_COACH_OPENINGS", PROJECT_ROOT / "data" / "openings")
    )
    guided_lessons_path: Path = Path(
        os.environ.get(
            "CHESS_COACH_GUIDED_LESSONS", PROJECT_ROOT / "data" / "repertoires"
        )
    )
    book_database_path: Path = Path(
        os.environ.get(
            "CHESS_COACH_BOOK_DATABASE", PROJECT_ROOT / "data" / "book_knowledge.db"
        )
    )
    books_enabled: bool = _env_bool("CHESS_COACH_BOOKS_ENABLED", True)
    stockfish_path: str | None = os.environ.get("STOCKFISH_PATH")
    stockfish_time_seconds: float = float(os.environ.get("STOCKFISH_TIME", "0.12"))
    stockfish_explanation_time_seconds: float = float(
        os.environ.get("STOCKFISH_EXPLANATION_TIME", "0.8")
    )
    stockfish_selection_time_seconds: float = float(
        os.environ.get("STOCKFISH_SELECTION_TIME", "2.0")
    )
    stockfish_deep_time_seconds: float = float(
        os.environ.get("STOCKFISH_DEEP_TIME", "5.0")
    )
    stockfish_multipv: int = int(os.environ.get("STOCKFISH_MULTIPV", "3"))
    ollama_url: str = os.environ.get("CHESS_COACH_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str | None = os.environ.get("CHESS_COACH_OLLAMA_MODEL")

    def __post_init__(self) -> None:
        normalized_profile = self.runtime_profile.strip().lower()
        if normalized_profile not in RUNTIME_PROFILES:
            choices = ", ".join(sorted(RUNTIME_PROFILES))
            raise ValueError(
                f"Unsupported CHESS_COACH_RUNTIME_PROFILE {self.runtime_profile!r}; "
                f"choose one of: {choices}"
            )
        object.__setattr__(self, "runtime_profile", normalized_profile)

    @property
    def private_book_knowledge_enabled(self) -> bool:
        """Return whether private local book knowledge may enter runtime prompts."""

        return self.runtime_profile == "local" and self.books_enabled
