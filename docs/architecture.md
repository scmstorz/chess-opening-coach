# Architecture

## Runtime shape

The application is local but uses a browser as its UI:

```text
Browser / React UI
        |
        | /api through local development proxy
        v
Python / FastAPI
  |        |          |             |
  v        v          v             v
python-  opening    Stockfish      Ollama
chess    TSV graph   UCI process    local API
  |
  v
SQLite learner log and engine cache
```

`scripts/start_local.py` asks the operating system for two available loopback
ports and starts both services. The browser sees one origin; the web development
server proxies `/api` requests to the Python service. Neither server binds to the
LAN by default.

## Three truth layers

Every learner move is represented through independent facts:

1. **Legality** — `python-chess` determines whether the move can be played.
2. **Opening theory** — the local opening graph determines whether the move is
   represented in known opening lines and which opening position was reached.
3. **Engine quality** — Stockfish evaluates the best candidate and the played
   move from the same position.

A move can therefore be legal, absent from theory data, and objectively good.
Such a move continues the game and receives neutral guidance rather than forced
correction.

## Move lifecycle

```text
drag or click move
  -> validate legal move
  -> collect theory candidates
  -> compare with Stockfish
  -> accept or start correction loop
  -> update opening identity
  -> create verified German feedback draft
  -> ask Ollama to paraphrase the draft
  -> validate generated output or use deterministic fallback
  -> persist interaction
  -> choose and verify coach move
  -> repeat feedback flow
```

Materially bad moves currently use a 0.75-pawn correction threshold. The
threshold is deliberately more forgiving than a raw engine annotation system
and is expected to change with real learner feedback.

## Opening recognition and move selection

The Lichess CC0 TSV lines are parsed into a position graph at startup. Position
keys use the first four FEN fields, excluding move counters. Exact named
positions update the displayed ECO/name; otherwise the most recent identified
opening remains visible.

Outgoing graph edges are weighted by the number of source lines that contain
them. This is useful as an offline coverage proxy but not equivalent to game
frequency. Coach candidates are checked with Stockfish; a candidate losing at
least 0.40 pawns is replaced by the current engine best move.

## Engine semantics

Scores are stored and displayed from White's perspective:

- positive: White is better;
- negative: Black is better;
- zero: approximately equal;
- forced mate: separate mate representation.

Move loss is normalized to the side that moved. Analysis keys include the
position, candidate, engine identity, time budget, and MultiPV setting and are
cached in SQLite.

## LLM grounding boundary

Ollama never receives authority to produce the verdict. The core first creates a
complete verified `summary` and `details`. Ollama is instructed to paraphrase
only that draft. Generated numbers and opening terminology are checked; output
that appears to add unsupported facts is discarded in favor of the deterministic
text.

The initial real-world test justified this boundary: `qwen3.8:27b-mlx`, running
through Ollama, incorrectly called `1...g6` a King's Gambit line. An integration
bug had also supplied the broader pre-move opening identity instead of the newly
reached identity, but neither context contained the invented King's Gambit
claim. The ordering bug was fixed, and the hardened flow rejected subsequent
unsupported expansions while retaining useful local explanations.

## Persistence

SQLite stores interactions and cached Stockfish results. Games are held in
memory because interrupted games are intentionally not resumable. Learner events
survive sessions and can support later review recommendations without automatic
scheduling.

## Current boundaries

- Single local learner
- Standard chess only
- Untimed free opening play
- No authentication or cloud persistence
- No imported PGN analysis
- No automatic network refresh
- No resumable interrupted games
