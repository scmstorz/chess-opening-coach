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

`scripts/start_local.py` uses stable loopback ports (`53687` for the browser and
`53686` for FastAPI) and checks that they are available before starting. Both
can be changed explicitly through environment variables. The browser sees one
origin; the web development server proxies `/api` requests to the Python
service. Neither server binds to the LAN by default.

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

The learner's move suggestion uses the same truth boundary but has no game-side
effects. While local theory edges exist, it considers up to five of the most
represented legal edges and selects the first candidate losing less than 0.40
pawns in Stockfish. If no candidate clears that safety threshold, the
least-losing theory candidate is used. Without Stockfish, the highest-ranked
local theory edge remains the offline fallback.

After the local opening graph ends, Stockfish supplies its current preferred
legal move directly. The response includes a `basis` discriminator and the UI
labels it as an `Engine-Vorschlag`, not as opening theory. This avoids turning a
coverage boundary into a false claim about the quality or status of the
position. Post-theory suggestions require Stockfish; if it is unavailable, the
service reports that limitation instead of inventing a move. Both suggestion
types mark source and destination and give a deterministic concept explanation;
neither plays the move nor adds a learner interaction. The SQLite engine cache
may still be populated.

```text
local theory edges
  -> top five by dataset coverage
  -> Stockfish safety check
  -> mark one sound theory move [basis: theory]
no local theory edge
  -> Stockfish preferred legal move
  -> mark engine move [basis: engine]
  -> learner decides and plays
```

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

Expanded move details are intentionally a separate information layer, not a
longer copy of the summary. Pawn explanations enumerate their verified before-
and-after controlled squares. When the best engine move relocates an already
attacked piece and the played move leaves it attacked, the service derives that
contrast from `python-chess`. Short principal variations then show the engine's
concrete calculation. The active Ollama model may make these facts easier to
read, but must preserve concrete move, square, and number anchors inside the
detail layer. The runtime does not merge unverified prose from multiple models.

The initial real-world test justified this boundary: `qwen3.8:27b-mlx`, running
through Ollama, incorrectly called `1...g6` a King's Gambit line. An integration
bug had also supplied the broader pre-move opening identity instead of the newly
reached identity, but neither context contained the invented King's Gambit
claim. The ordering bug was fixed, and the hardened flow rejected subsequent
unsupported expansions while retaining useful local explanations.

## Grounded position questions

Position questions use the same verified-answer pattern as move feedback. The
browser sends the question and, when present, the currently highlighted
suggestion. The service verifies that the referenced move is legal in the
unchanged session position. An explicitly named legal SAN/UCI move in the
question takes precedence over the highlighted move; otherwise the service uses
the same theory-first, Stockfish-after-theory selection as the visible hint.

```text
user question + current FEN + optional highlighted move
  -> resolve and validate one legal move with python-chess
  -> check local theory membership and resulting opening identity
  -> analyze the move and a short PV with Stockfish
  -> build atomic, deterministic German answer facts
  -> let Ollama select only the fact IDs most relevant to the question
  -> render the selected verified text or use the deterministic fallback
```

The user question itself is treated as untrusted context, not as evidence. The
answer is added to the in-memory conversation feed but not recorded as a move or
learner attempt in SQLite. If the local theory graph provides no safe anchor,
the coach states that limitation instead of inventing an explanation.

The initial implementation briefly allowed Ollama to paraphrase the complete
answer. A live `Warum ist dieser Zug gut?` test caused Qwen to add an unsupported
claim about the absence of tactical or material drawbacks. The question adapter
was therefore tightened before release: the model can now select only IDs from
an allowlisted set of already written facts. This preserves adaptive
emphasis while making novel chess prose structurally impossible in this path.

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
