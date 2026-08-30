from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path = Path(
        os.environ.get("CHESS_COACH_DATABASE", PROJECT_ROOT / "data" / "coach.db")
    )
    opening_data_path: Path = Path(
        os.environ.get("CHESS_COACH_OPENINGS", PROJECT_ROOT / "data" / "openings")
    )
    stockfish_path: str | None = os.environ.get("STOCKFISH_PATH")
    stockfish_time_seconds: float = float(os.environ.get("STOCKFISH_TIME", "0.12"))
    stockfish_explanation_time_seconds: float = float(
        os.environ.get("STOCKFISH_EXPLANATION_TIME", "0.8")
    )
    stockfish_multipv: int = int(os.environ.get("STOCKFISH_MULTIPV", "3"))
    ollama_url: str = os.environ.get("CHESS_COACH_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str | None = os.environ.get("CHESS_COACH_OLLAMA_MODEL")
