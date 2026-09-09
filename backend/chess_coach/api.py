from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from chess_coach.book_knowledge import BookKnowledgeBase, NullBookKnowledgeBase
from chess_coach.config import Settings
from chess_coach.engine import StockfishService
from chess_coach.openings import OpeningBook
from chess_coach.service import CoachService
from chess_coach.storage import SQLiteStore
from chess_coach.tutor import OllamaTutor


class NewSessionRequest(BaseModel):
    color: str = Field(pattern="^(white|black|random)$")


class MoveRequest(BaseModel):
    from_square: str = Field(pattern="^[a-h][1-8]$")
    to_square: str = Field(pattern="^[a-h][1-8]$")
    promotion: str | None = Field(default=None, pattern="^[qrbn]$")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=600)
    focus_move_uci: str | None = Field(default=None, pattern="^[a-h][1-8][a-h][1-8][qrbn]?$")
    deep: bool = False


def build_service(settings: Settings | None = None) -> CoachService:
    settings = settings or Settings()
    store = SQLiteStore(settings.database_path)
    engine = StockfishService(
        settings.stockfish_path,
        time_seconds=settings.stockfish_time_seconds,
        explanation_time_seconds=settings.stockfish_explanation_time_seconds,
        selection_time_seconds=settings.stockfish_selection_time_seconds,
        deep_time_seconds=settings.stockfish_deep_time_seconds,
        multipv=settings.stockfish_multipv,
        cache=store,
    )
    book_knowledge = (
        BookKnowledgeBase(settings.book_database_path)
        if settings.books_enabled
        else NullBookKnowledgeBase("Buchwissen ist in der Konfiguration deaktiviert.")
    )
    return CoachService(
        OpeningBook(settings.opening_data_path),
        engine,
        OllamaTutor(settings.ollama_url, settings.ollama_model),
        store,
        book_knowledge=book_knowledge,
    )


def create_app(service: CoachService | None = None) -> FastAPI:
    coach = service or build_service()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        coach.engine.close()
        coach.store.close()

    app = FastAPI(title="Chess Opening Coach API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.coach = coach

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "openings": {
                "source": coach.openings.source,
                "entries": coach.openings.entries_loaded,
            },
            "stockfish": {
                "available": coach.engine.available,
                "path": coach.engine.executable,
                "name": coach.engine.name,
            },
            "ollama": coach.tutor.status(),
            "books": coach.book_knowledge.status(),
        }

    @app.post("/api/sessions")
    def new_session(request: NewSessionRequest) -> dict[str, Any]:
        return coach.create_session(request.color)

    @app.post("/api/sessions/{session_id}/moves")
    def play_move(
        session_id: Annotated[str, Path(min_length=1)], request: MoveRequest
    ) -> dict[str, Any]:
        try:
            return coach.play_learner_move(
                session_id, request.from_square, request.to_square, request.promotion
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/undo")
    def undo_move(session_id: Annotated[str, Path(min_length=1)]) -> dict[str, Any]:
        try:
            return coach.undo_last_turn(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/opening/continue")
    def continue_after_opening(session_id: Annotated[str, Path(min_length=1)]) -> dict[str, Any]:
        try:
            return coach.continue_after_opening(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/opening/summary")
    def finish_opening(session_id: Annotated[str, Path(min_length=1)]) -> dict[str, Any]:
        try:
            return coach.finish_opening(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/suggestion")
    def suggest_move(session_id: Annotated[str, Path(min_length=1)]) -> dict[str, Any]:
        try:
            return coach.suggest_move(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/sessions/{session_id}/questions")
    def answer_question(
        session_id: Annotated[str, Path(min_length=1)], request: QuestionRequest
    ) -> dict[str, Any]:
        try:
            return coach.answer_question(
                session_id,
                request.question,
                request.focus_move_uci,
                deep=request.deep,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/learning/summary")
    def learning_summary() -> dict[str, int]:
        return coach.store.summary()

    return app


app = create_app()
