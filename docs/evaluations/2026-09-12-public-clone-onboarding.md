# Public-clone onboarding audit

- Date: 2026-09-12
- Scope: local setup from the public Git repository

## Trigger

After the first public push, the learner asked whether another person could
actually run the project locally. The README already listed dependencies and a
start command, but it assumed that the reader had the repository, knew how to
install the prerequisites, and had hardware suitable for the owner's 18 GB
Ollama model.

## Gaps found

- There was no copy-and-paste path beginning with `git clone`.
- Platform guidance was effectively macOS-only.
- The only named model was `qwen3.8:27b-mlx`, which is a large Apple-oriented
  download.
- “Usable without Ollama or Stockfish” did not say which features degraded.
- Common failures around ports, model availability, engine paths, and the
  virtual environment were not actionable.
- Native Windows startup was not verified and therefore could not honestly be
  promised.

One apparent risk proved already handled in code: `npm run coach` begins with
the system Python only long enough for the standard-library launcher to find
and re-execute `.venv/bin/python` on macOS or Linux. A shell activation step is
therefore unnecessary after `uv sync` on those platforms.

## Decision

The README now provides:

- one complete Apple Silicon/macOS path using the production-tested
  `qwen3.8:27b-mlx` model;
- an explicit `qwen3:4b` low-resource path with a quality warning;
- an Ubuntu/Debian path with links for Node, uv, and Ollama;
- Windows support through WSL 2, while native Windows remains unclaimed;
- a capability matrix for missing books, Ollama, and Stockfish; and
- command-level troubleshooting plus the local health endpoint.

The public clone is intentionally bookless. Setup neither requests nor implies
access to the project owner's PDFs or compiled corpus. The coach reports the
missing private provider and continues with public opening data, deterministic
logic, and whichever optional local services are available.

## Acceptance checks

Automated documentation contracts require the clone URL, dependency install,
start command, stable browser URL, all three platform headings, the smaller
model, degraded modes, and troubleshooting guidance. A staged-export smoke test
must additionally prove that the proposed public files contain no private
inputs and can install and build without relying on the owner's existing
working tree.

## Verification result

The complete staged Git index was exported into a new temporary directory. Its
`data/books/` directory contained only the tracked explanatory README; it had no
PDF, knowledge database, or learner database. `uv sync --extra dev --locked
--offline` created a new virtual environment from the local package cache, and
`npm ci --offline` created a new JavaScript installation. The two README
contracts and the complete production web build passed inside that export.

The exported application then started through the documented `npm run coach`
entry point with `CHESS_COACH_RUNTIME_PROFILE=public`. Its health response
reported 3,810 public opening entries, local Stockfish, `qwen3:4b`, and zero
books with the explicit reason that private knowledge is disabled in the public
profile. This verifies the macOS/Linux launcher path and the bookless public
boundary. Native Windows remains deliberately unverified and documented only
through WSL 2.
