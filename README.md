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
- Automatic selection of free frontend and backend ports
- White, Black, and random learner color
- Progressive opening recognition across 3,810 local Lichess opening entries
- Theory-aware and Stockfish-checked coach moves
- Visible engine evaluation using the standard White-positive convention
- German feedback after every learner and coach move
- Expandable explanation detail
- Ollama explanations with deterministic grounding fallback
- Three-attempt correction loop for materially bad moves
- Local SQLite interaction history and Stockfish cache
- Responsive layout and keyboard-focusable board squares

The first milestone intentionally does not yet include free-form position
questions, deliberate opponent inaccuracies, opening summaries, PGN export,
review recommendations, or timed 10+0 simulation.

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

The launcher asks the operating system for two free loopback ports, starts the
local Python API and browser UI, and prints the exact URL. It does not assume
that ports such as 8000 or 8080 are free.

Stop both processes with `Ctrl+C`.

## Configuration

All settings are optional environment variables:

```bash
CHESS_COACH_OLLAMA_MODEL=qwen3.8:27b-mlx
CHESS_COACH_OLLAMA_URL=http://127.0.0.1:11434
STOCKFISH_PATH=/absolute/path/to/stockfish
STOCKFISH_TIME=0.12
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
scripts/start_local.py       free-port local launcher
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

