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
  -> evaluate opening-phase signals after the completed turn
  -> repeat feedback flow
```

Materially bad moves currently use a 0.75-pawn correction threshold. The
threshold is deliberately more forgiving than a raw engine annotation system
and is expected to change with real learner feedback.

## Opening-phase transition

The opening does not end at one fixed move number, and exhausting the local
opening graph is not sufficient on its own. After a completed turn, the service
combines five observable signals: remaining theory edges, the number of minor
pieces no longer on their starting squares, castling history, movement of the
four central d/e pawns, and elapsed half-moves. An early unusual move can exhaust
the graph without triggering the transition. A sufficiently mature position or
a completed game does.

The result is deliberately worded as probable. The session pauses in a
`transition` phase and the learner explicitly chooses either `middlegame` or
`complete`. Continuing switches theory membership from an expected signal to
historical context; Stockfish supplies coach moves and suggestions. Completing
the opening creates a deterministic review from stored interactions and current
board facts.

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

Normal move feedback uses the short engine budget. Coach move selection outside
the opening graph uses a separate two-second stability budget, so a transient
shallow candidate is less likely to be presented as the best move. A standard
`why?` question uses a depth-18, three-candidate MultiPV search. If
the questioned move is not among the leading candidates, Stockfish analyzes it
again as a forced root move and adds it to the comparison. Cache keys include
the FEN, engine, explanation time, depth, candidate count, and optional focus
move. This gives weak moves a real continuation instead of comparing a deep
best line with a one-ply placeholder.

`Tief erklären` uses a five-second, depth-24 budget. A first pass discovers four
candidates. A second pass then analyzes that common root set—including the
focused move—under the same limit. Scores and lines shown in one explanation
therefore come from one internally consistent snapshot. The service looks for
recurring own-side follow-ups across the candidate lines, flexible move orders,
central posts that cannot immediately be challenged by a pawn, restrained pawn
breaks, and verified exchanges. These are labeled as model plans, not forced
continuations or reasons stated by Stockfish.

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
Generic piece templates are not treated as verified facts: controlled central
squares, attacked pieces, attacks on the moving piece, and same-piece
continuations are derived from the actual board and PV. Ollama ranks these
atomic facts for relevance. Mechanically important facts are marked required
and appended if the model omits them, so language selection cannot empty the
answer of its causal explanation.

The comparison layer also computes move deltas for the focus and nearest engine
candidate: which attacked piece each move saves, which own pieces remain under
attack, approximate material priority, new counterattacks, central-square
control, captures in the first reply, checks, and newly opened slider lines.
Interpretive wording is deliberately qualified: these visible differences can
explain part of an evaluation gap, but the number does not prove one exclusive
strategic cause.

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
  -> run standard MultiPV, or a two-pass depth-24 comparison in deep mode
  -> compare concrete board effects and principal variations
  -> derive cautious plan patterns and atomic deterministic German answer facts
  -> let Ollama select only the fact IDs most relevant to the question
  -> render the selected verified text or use the deterministic fallback
```

The browser renders the short selected answer first. Its expander separates the
medium-term plan, recurring patterns across lines, concrete effects, alternative
comparison, and raw Stockfish calculation. Standard answers omit the recurring-
patterns section. This prevents a fluent summary from hiding the evidence needed
to learn from the position.

The UI estimates remaining time from an operation-specific rolling average kept
in browser storage. It counts down only as an estimate and changes to “noch einen
Moment” instead of showing a false negative countdown. This preference-like
telemetry is device-local and is not learner-state data.

The user question itself is treated as untrusted context, not as evidence. The
answer is added to the in-memory conversation feed but not recorded as a move or
learner attempt in SQLite. If the local theory graph provides no safe anchor,
Stockfish provides one; if Stockfish is also unavailable, the coach states that
capability limit instead of inventing an explanation.

The initial implementation briefly allowed Ollama to paraphrase the complete
answer. A live `Warum ist dieser Zug gut?` test caused Qwen to add an unsupported
claim about the absence of tactical or material drawbacks. The question adapter
was therefore tightened before release: the model can now select only IDs from
an allowlisted set of already written facts. This preserves adaptive
emphasis while making novel chess prose structurally impossible in this path.

## Persistence

SQLite stores interactions, cached Stockfish results, and completed opening
summaries. A summary records the final position, identified opening, observed
center/development/king-safety facts, strong moves, correction points, one
takeaway, and an optional review recommendation. The recommendation is data,
not an automatic scheduler action: the learner remains in control.

Active games are held in memory because interrupted games are intentionally not
resumable. The local Python SQLite database remains the source of truth for
learning data; browser storage is not used for it.

## Current boundaries

- Single local learner
- Standard chess only
- Untimed free opening play
- No authentication or cloud persistence
- No imported PGN analysis
- No automatic network refresh
- No cloud-generated tutor prose in the product runtime
- No resumable interrupted games
