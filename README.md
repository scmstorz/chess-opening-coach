# Chess Opening Coach

A local-first browser coach for learning the first moves of a chess game with
understanding rather than rote memorization.

The current MVP lets one local learner choose White, Black, or a random color,
move pieces on a graphical board, and receive German feedback after both learner
and coach moves. Opening identity, engine quality, and LLM pedagogy remain
separate sources of information.

## Core principle

> Keep chess truth outside the LLM. The LLM explains verified facts; it does not
> define them.

- `python-chess` owns rules, notation, and legal board state.
- The local Lichess opening dataset owns ECO codes, names, and theory coverage.
- Stockfish owns objective move analysis.
- Ollama rewrites an already verified feedback draft into learner-friendly German.
- Locally compiled chess books contribute attributed strategic source claims.
- SQLite stores interactions and cached engine analysis locally.

The open-source core contains no copyrighted chess books or compiled book
corpus. Private book knowledge is an optional local overlay supplied by the
operator.

## What works now

- Local browser UI with a drag-and-drop and click-to-move chessboard
- Stable local URL at `http://localhost:53687/` with explicit port overrides
- White, Black, and random learner color
- Immediately playable White game on page load; choosing a color starts a fresh game
- Progressive opening recognition across 3,810 local Lichess opening entries
- Theory-aware and Stockfish-checked coach moves
- Non-playing `Zug vorschlagen` hint from opening theory or Stockfish, with source/target highlighting
- Grounded follow-up questions about the current position or suggested move
- Friendly clarification when source/target squares imply a move but the typed piece notation conflicts
- Board-derived explanations of direct threats, controlled squares, and concrete engine lines
- Deterministic priority for immediate queen or rook loss before plans, books, or LLM wording
- Optional `Tief erklären` analysis with consistently rechecked candidates and three opponent-reply branches
- Plan-oriented explanations that retain only follow-up ideas recurring across independent reply branches
- Expandable sections for long-term plan, concrete effects, alternatives, and engine lines
- A local PDF knowledge compiler with page-level provenance, FTS retrieval, and explicit issue quarantine
- Grounded German book synthesis with one compact source card per book and an honest evidence fallback
- Learned countdown estimates for normal and deep coach operations
- Visible engine evaluation using the standard White-positive convention
- German feedback after every learner and coach move
- Expandable explanation detail
- Ollama explanations with deterministic grounding fallback
- Three-attempt correction loop for materially bad moves
- Full-turn undo that removes both learner and coach responses
- Multi-signal detection of the probable opening-to-middlegame transition
- Learner-controlled choice to continue or create a grounded opening review
- Persistent opening summaries with optional, non-automatic review recommendations
- One-click `Hilfreich`, `Unklar`, or `Falsch` ratings below every feed explanation
- Optional feedback notes stored with the exact position, move, answer, engine result, source, and model
- In-app local review list plus fixture-candidate export for learner-identified explanation failures
- Local SQLite interaction history and Stockfish cache
- Responsive layout and keyboard-focusable board squares

The first milestone intentionally does not yet include deliberate opponent
inaccuracies, PGN export, cross-session review prompts, targeted repertoire
training, or timed 10+0 simulation.

## Prerequisites

- macOS or another local development system
- Python 3.11+
- Node.js 22.13+
- [`uv`](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) with a chat model
- [Stockfish](https://stockfishchess.org/)

Recommended local setup on macOS:

```bash
brew install stockfish
ollama pull qwen3.8:27b-mlx
uv sync --extra dev
npm ci
```

The application can use another installed Ollama model through
`CHESS_COACH_OLLAMA_MODEL`. Without Ollama or Stockfish, it remains usable with
deterministic explanations or without engine scoring, and reports the missing
capability in the UI.

## Start

```bash
npm run coach
```

The launcher starts the local Python API on port `53686` and the browser UI at
`http://localhost:53687/`. It checks both ports first and reports a clear error
instead of silently changing the browser URL when either is occupied.

Stop both processes with `Ctrl+C`.

## Configuration

All settings are optional environment variables:

```bash
CHESS_COACH_OLLAMA_MODEL=qwen3.8:27b-mlx
CHESS_COACH_OLLAMA_URL=http://127.0.0.1:11434
CHESS_COACH_BACKEND_PORT=53686
CHESS_COACH_FRONTEND_PORT=53687
CHESS_COACH_RUNTIME_PROFILE=local
CHESS_COACH_BOOKS_ENABLED=true
CHESS_COACH_BOOK_DATABASE=/absolute/path/to/book_knowledge.db
STOCKFISH_PATH=/absolute/path/to/stockfish
STOCKFISH_TIME=0.12
STOCKFISH_EXPLANATION_TIME=0.8
STOCKFISH_SELECTION_TIME=2.0
STOCKFISH_DEEP_TIME=5.0
STOCKFISH_MULTIPV=3
CHESS_COACH_DATABASE=/absolute/path/to/coach.db
CHESS_COACH_OPENINGS=/absolute/path/to/opening-tsv-directory
```

`CHESS_COACH_RUNTIME_PROFILE=local` permits the explicitly enabled private
book database. `CHESS_COACH_RUNTIME_PROFILE=public` disables private book
retrieval even if `CHESS_COACH_BOOKS_ENABLED=true`; this is the fail-closed
profile for public builds and demonstrations.

## Local chess books

Owned PDF sources live in `data/books/`. PDFs and the derived
`data/book_knowledge.db` are deliberately ignored by Git and must not be
deployed. Import or refresh a book with:

```bash
.venv/bin/python -m chess_coach.book_knowledge.cli ingest \
  "data/books/Stewart, Clyde - Chess Openings For Beginners (2021).pdf"
.venv/bin/python -m chess_coach.book_knowledge.cli ingest \
  "data/books/Fundamental Chess Openings - Paul van der Sterren.pdf"
.venv/bin/python -m chess_coach.book_knowledge.cli ingest \
  "data/books/John Emms - Discovering Chess Openings.pdf"
.venv/bin/python -m chess_coach.book_knowledge.cli verify
```

The compiler stores the complete searchable text locally with book, page,
section, chunk, and claim provenance. A book is treated as an attributed source,
not as automatic chess truth: questionable statistics and unsafe move prose are
quarantined. Only short retrieved excerpts may be sent automatically to the
local Ollama process. The browser shows the resulting German explanation and
source metadata, never the original English excerpt. If the evidence or its
grounding is insufficient, the coach says so instead of inventing a plan.

Typeset move tables such as `1 e4 e5 2 Nf3 Nc6 3 Bb5` are normalized and
validated with `python-chess`. Only the final position of a displayed leading
line anchors the following commentary. Embedded comparison lines remain
searchable but do not attach their whole paragraph to every position they pass
through.

Abbreviated continuations such as `3...a6 4.Ba4` are accepted only when one
nearby, already verified parent line supplies a unique legal starting position.
The inference method and parent are stored for audit; unresolved fragments stay
quarantined. The same fail-closed rule applies when numbered moves alternate
with prose: at least two legal moves must form one unique continuation, and a
claim is bound only within the same positioned PDF text block or the next one.
Exact position evidence without an exact safe claim is not padded with broad
opening prose. Without a recognized opening, bare move names never trigger a
global book search.

## Publication safety

Run the normal repository guard before every commit or public archive:

```bash
npm run check:publication
```

Before a release, run the stricter local check while the private knowledge
database is available:

```bash
npm run check:publication:release
```

The guard rejects private document/database paths and file types in the Git
index or repository history. When the local corpus exists, it also compares
tracked text with non-reversible fingerprints of 24-word source sequences to
catch accidentally copied extracts. It never adds the fingerprints or source
text to Git. See `docs/publication-safety.md` for the operating boundary and
limitations.

## Explanation feedback

Every explanation in the coach feed can be rated with one click. `Unklar` and
`Falsch` immediately open an optional note field; a note can also be added to a
helpful answer. SQLite stores one revisable judgment per message together with
a snapshot of its FEN, move, rendered explanation sections, Stockfish payload,
source metadata, and active model. Browser storage is not used for these records.

Review the newest records through `GET /api/feedback`, optionally filtered with
`?rating=unclear` or `?rating=wrong`. Export the two failure categories into the
Git-ignored `outputs/` directory with:

```bash
.venv/bin/python scripts/export_explanation_feedback.py
```

The export creates candidates for human review. A learner rating is evidence
about teaching quality, not proof that a chess claim is false, so cases are not
automatically promoted into the regression suite.

## Verification

```bash
.venv/bin/pytest
.venv/bin/ruff check backend scripts
.venv/bin/python benchmarks/explanation_quality.py
npm run check:publication:release
npm run lint
npm test
git diff --check
```

## Repository map

```text
app/                         React browser interface
backend/chess_coach/         verified chess and tutor services
backend/tests/               backend unit and API tests
data/openings/               local CC0 opening source data
data/books/                  local, Git-ignored owned PDF sources
docs/                        journal, architecture, ADRs, case-study material
scripts/start_local.py       stable-port local launcher
tests/                       rendered web-shell test
```

## Data and privacy

Runtime data stays on the local machine. The app is designed to work offline
after setup. Future network refreshes must be explicit, explain their source and
purpose, and remain optional.

Opening names and lines are sourced from
[`lichess-org/chess-openings`](https://github.com/lichess-org/chess-openings),
commit `4b8622759e7ae6f93f011cc6c83a3823401ab45e`, under CC0. The source README and
license are retained in `data/openings/`.

## Documentation

- [Project journal](docs/project-journal.md)
- [Architecture](docs/architecture.md)
- [Case study outline](docs/case-study-outline.md)
- [Architecture decisions](docs/decisions/)
- [Local Ollama chess-model comparison](docs/evaluations/2026-08-29-ollama-chess-models.md)
- [Kimi and DeepSeek explanation comparison](docs/evaluations/2026-09-08-cloud-chess-explanations.md)
- [Six-case deep-explanation quality cycle](docs/evaluations/2026-09-09-deep-explanation-quality-cycle.md)
