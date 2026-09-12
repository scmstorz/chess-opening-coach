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
- Guided Italian-from-White curriculum with one model line and six active Italian deviations
- Six additional `1.e4` response lessons retained locally for a later foundations curriculum
- Three guided styles: repeat the model line, start at a deviation, or face a hidden varying opponent line
- Realistic-opponent sessions continue as free opening play after a prepared variation ends
- Immediate recall, two hints, and a third-attempt reveal in every guided scenario
- Separate guided and free-play modes; free play retains White, Black, and random color choice
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
- Conservative, locally learned countdowns with separate scripted and adaptive move profiles
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

The first milestone intentionally does not yet include exhaustive repertoire
trees, PGN export, cross-session review prompts, empirical opponent-frequency
modelling, or timed 10+0 simulation.

## Quick start

The public repository contains the application, its guided repertoire, and the
CC0 opening data. It does not contain or require the private chess books used by
the project owner.

### macOS with Apple Silicon

Install [Homebrew](https://brew.sh/) and the
[Ollama macOS app](https://ollama.com/download), then launch Ollama once. The
following block installs the remaining tools, downloads the recommended local
model, and starts the coach:

```bash
brew install git node uv stockfish
git clone https://github.com/scmstorz/chess-opening-coach.git
cd chess-opening-coach
ollama pull qwen3.8:27b-mlx
uv sync --extra dev
npm ci
npm run coach
```

Open `http://localhost:53687/`. Stop both local processes with `Ctrl+C`.

`qwen3.8:27b-mlx` currently offers the best tested production fit but downloads
about 18 GB. For a much smaller first run, use the approximately 2.5 GB
`qwen3:4b` model. Its German explanations are weaker, while all chess verdicts
remain grounded outside the model:

```bash
ollama pull qwen3:4b
CHESS_COACH_OLLAMA_MODEL=qwen3:4b npm run coach
```

### Linux

Install [Node.js 22.13 or newer](https://nodejs.org/en/download) first. On
Ubuntu or Debian, install the remaining system tools and Ollama with:

```bash
sudo apt update
sudo apt install -y git curl stockfish
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://ollama.com/install.sh | sh
```

Restart the shell if `uv` is not found. Then install and start the public coach
with the smaller model:

```bash
git clone https://github.com/scmstorz/chess-opening-coach.git
cd chess-opening-coach
ollama pull qwen3:4b
uv sync --extra dev
npm ci
CHESS_COACH_OLLAMA_MODEL=qwen3:4b npm run coach
```

If the system package places Stockfish outside `PATH`, set its absolute path as
described under troubleshooting.

### Windows

Native Windows startup is not yet part of the tested support matrix. The
supported route is [WSL 2](https://learn.microsoft.com/windows/wsl/install).
Open PowerShell as Administrator, run the following command, restart Windows if
requested, and then follow the Linux instructions inside the Ubuntu terminal:

```powershell
wsl --install -d Ubuntu
```

The browser on Windows can open the same `http://localhost:53687/` address used
inside WSL.

## Optional components

The application starts with reduced capabilities when optional local services
or private data are absent:

| Missing component | What still works | What is reduced |
| --- | --- | --- |
| Private chess books | The complete public application | No book-backed plans or citations |
| Ollama | Legal moves, opening recognition, Stockfish, and deterministic verified explanations | No local-model selection or synthesis |
| Stockfish | Guided lessons, legal-move checks, opening recognition, and Ollama/deterministic wording | No objective evaluation, deep analysis, or reliable post-opening suggestion |
| Ollama and Stockfish | The PGN-guided opening lessons and deterministic chess rules | No engine quality judgment and less adaptive explanation |

Ollama and Stockfish are always local. The public application requires no API
key or account.

## Startup checks and troubleshooting

Check the installed tools before diagnosing the application:

```bash
node --version
npm --version
uv --version
ollama list
command -v stockfish
```

- **`node` is too old:** install Node.js 22.13 or newer, open a new terminal,
  and rerun `npm ci`.
- **Python reports a missing package:** rerun `uv sync --extra dev`. The launcher
  automatically uses the resulting `.venv` on macOS and Linux.
- **Ollama is unavailable:** launch the macOS/Windows application or run
  `ollama serve` on Linux. Confirm that the selected model appears in
  `ollama list`.
- **The configured Ollama model is missing:** pull it first or start with an
  installed model, for example
  `CHESS_COACH_OLLAMA_MODEL=qwen3:4b npm run coach`.
- **Stockfish is not found:** locate the executable and pass its absolute path,
  for example
  `STOCKFISH_PATH=/usr/games/stockfish npm run coach` on some Linux systems.
- **Port 53686 or 53687 is occupied:** stop the other local process, or choose
  both ports explicitly with
  `CHESS_COACH_BACKEND_PORT=53786 CHESS_COACH_FRONTEND_PORT=53787 npm run coach`.
- **The page opens but a capability is unavailable:** inspect
  `http://127.0.0.1:53686/api/health`. It reports the detected opening data,
  Stockfish, Ollama model, book database, and runtime profile without exposing
  private book text.

The launcher never silently changes the browser URL. By default it starts the
Python API on `53686` and the browser UI on `53687`, then prints the exact local
address once both are ready.

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
CHESS_COACH_GUIDED_LESSONS=/absolute/path/to/guided-pgn-directory
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
data/repertoires/            authored guided lessons in annotated PGN
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

## License

Original project code and authored repository material are available under the
[MIT License](LICENSE). Third-party software and data retain their own licenses;
see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). In particular,
`python-chess` is GPL-3.0-or-later, so redistribution of a complete combined
application may carry GPL obligations in addition to the MIT grant for this
project's original code.

Private chess-book PDFs, extracted source passages, compiled claims, and the
local book database are operator-supplied inputs. They are neither distributed
by this repository nor licensed under MIT.

## Documentation

- [Project journal](docs/project-journal.md)
- [Architecture](docs/architecture.md)
- [Case study outline](docs/case-study-outline.md)
- [Architecture decisions](docs/decisions/)
- [Local Ollama chess-model comparison](docs/evaluations/2026-08-29-ollama-chess-models.md)
- [Kimi and DeepSeek explanation comparison](docs/evaluations/2026-09-08-cloud-chess-explanations.md)
- [Six-case deep-explanation quality cycle](docs/evaluations/2026-09-09-deep-explanation-quality-cycle.md)
- [Opponent-variation engine audit and self-play](docs/evaluations/2026-09-11-opponent-variation-self-play.md)
- [Italian curriculum scope acceptance](docs/evaluations/2026-09-12-italian-scope-acceptance.md)
- [Public repository and license decision](docs/decisions/0017-public-repository-license.md)
- [Public-clone onboarding audit](docs/evaluations/2026-09-12-public-clone-onboarding.md)
