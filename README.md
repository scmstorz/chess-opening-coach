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
- SQLite stores interactions and cached engine analysis locally.

## What works now

- Local browser UI with a drag-and-drop and click-to-move chessboard
- Stable local URL at `http://localhost:53687/` with explicit port overrides
- White, Black, and random learner color
- Immediately playable White game on page load; choosing a color starts a fresh game
- Progressive opening recognition across 3,810 local Lichess opening entries
- Theory-aware and Stockfish-checked coach moves
- Non-playing `Zug vorschlagen` hint from opening theory or Stockfish, with source/target highlighting
- Grounded follow-up questions about the current position or suggested move
- Board-derived explanations of direct threats, controlled squares, and concrete engine lines
- Optional `Tief erklären` analysis with four consistently rechecked candidates
- Plan-oriented explanations that look for recurring follow-up ideas across engine lines
- Expandable sections for long-term plan, concrete effects, alternatives, and engine lines
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
STOCKFISH_PATH=/absolute/path/to/stockfish
STOCKFISH_TIME=0.12
STOCKFISH_EXPLANATION_TIME=0.8
STOCKFISH_SELECTION_TIME=2.0
STOCKFISH_DEEP_TIME=5.0
STOCKFISH_MULTIPV=3
CHESS_COACH_DATABASE=/absolute/path/to/coach.db
CHESS_COACH_OPENINGS=/absolute/path/to/opening-tsv-directory
```

## Verification

```bash
.venv/bin/pytest
.venv/bin/ruff check backend scripts
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
