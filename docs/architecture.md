# Architecture

## Runtime shape

The application is local but uses a browser as its UI:

```text
Browser / React UI
        |
        | /api through local development proxy
        v
Python / FastAPI
  |        |          |             |              |
  v        v          v             v              v
python-  opening    Stockfish      Ollama         book knowledge
chess    TSV graph   UCI process    local API      read-only SQLite
  |
  v
SQLite learner log and engine cache
```

The book-knowledge database is separate from the learner log. Its compiler is
an offline authoring process; runtime opens it read-only. Owned PDFs, extracted
text, and the derived database remain local and are ignored by Git.

The runtime has an explicit publication boundary. The default `local` profile
may use an enabled operator-supplied knowledge database. The fail-closed
`public` profile always installs a null book provider, even when the database
exists or the books flag is true. Public Git and release artifacts contain the
compiler but not its private inputs or outputs. A release guard scans Git paths,
history, and - when the local corpus is available - long source-text overlap.
The detailed operating procedure is in `docs/publication-safety.md`.

`scripts/start_local.py` uses stable loopback ports (`53687` for the browser and
`53686` for FastAPI) and checks that they are available before starting. Both
can be changed explicitly through environment variables. The browser sees one
origin; the web development server proxies `/api` requests to the Python
service. Neither server binds to the LAN by default.

## Guided repertoire scenarios

Guided practice is a separate decision policy from free play. Its tracked,
project-authored PGN files provide legal moves, explanations after both sides'
moves, two hints for every learner decision, and compact scenario metadata.
`python-chess` validates the complete line while loading it. Stockfish verifies
objective plausibility but does not replace the repertoire move with its current
top-one candidate.

The active Italian-from-White family contains one model line and six opponent
deviations. Every active scenario shares the prefix
`1.e4 e5 2.Nf3 Nc6 3.Bc4`; only then may the coach vary. Six already-authored
responses to earlier opening switches remain in the PGN under the separate
`e4-white-foundations` family with zero selection weight. They are not reachable
through the UI until a later foundations curriculum teaches those openings.
The same active linear scenario can be presented in three ways:

```text
model line
  -> reconstruct initial board
  -> repeat one stable setup

branch drill
  -> choose a non-mainline scenario
  -> reconstruct its board at DrillStartPly
  -> show earlier moves as context
  -> ask White at the critical decision

realistic opponent
  -> choose one weighted scenario
  -> keep its identity hidden
  -> start at move one
  -> reveal only after Black plays the first move differing from the model
  -> finish the prepared segment without ending the opening session
  -> continue with theory/Stockfish until the normal opening-phase decision
```

Selection happens once per session. This creates variation between sessions
while preserving coherent replies and explanations within one game. The
selection weights are curriculum weights, not claimed player-frequency data.
Every branch position stores an initial FEN and contextual move history; replay
for historical questions therefore starts at that FEN rather than assuming the
normal initial position.

A scenario boundary and an opening-phase boundary are different states. Direct
model-line and branch drills may finish when their authored moves are exhausted.
In realistic-opponent mode, however, that same point is only an `Etappenziel`:
the fixed reply policy is released and the game continues using local theory or
Stockfish. The opening-end heuristic is not allowed to interrupt that continuation
before the 20-ply model-line horizon. It may then offer the learner the existing
choice between continuing into the middlegame and evaluating the opening.

Turn snapshots include both the current lesson ply and whether the prepared
realistic segment has ended. Undoing the final learner turn therefore removes
its free coach reply and milestone, restores the prior guided question, and does
not leave the session accidentally in free play.

The model is deliberately finite. A legal White move can be objectively sound
without matching the active scenario, so `repertoire_match`, broad
`theory_match`, and Stockfish loss remain separate fields. New accepted
alternatives or transpositions require authored semantics rather than being
created implicitly by engine randomness.

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

An A-versus-B question is treated differently from an open-ended `why?` query.
Every explicitly named legal alternative is a required root and promotes the
comparison itself to the common depth-24 search, even when the learner did not
press `Tief erklären`. The deeper reply-robust plan search remains opt-in. This
prevents a named alternative from being silently replaced by a convenient top-N
candidate and gives the requested move enough principal variation for a causal
comparison.

`Tief erklären` uses a five-second, depth-24 budget. A first pass discovers four
candidates. A second pass then analyzes that common root set—including the
focused move—under the same limit. Scores and lines shown in one explanation
therefore come from one internally consistent snapshot. The service looks for
recurring own-side follow-ups across the candidate lines, flexible move orders,
central posts that cannot immediately be challenged by a pawn, restrained pawn
breaks, and verified exchanges. These are labeled as model plans, not forced
continuations or reasons stated by Stockfish.

The deep path adds a differently scoped search after the focus move. It checks
three plausible opponent replies and keeps the learner's follow-up moves only
when they recur in at least two branches. This distinguishes “better than
another first move” from “still supports the same follow-up against different
answers”. Explicit alternatives named in a question are forced into the root
comparison. Recovery moves after an inferior focus move are not rebranded as
the move's purpose.

## LLM grounding boundary

Ollama never receives authority to produce the verdict. The core first creates a
complete verified `summary` and `details`. Ollama is instructed to paraphrase
only that draft. Generated numbers and opening terminology are checked; output
that appears to add unsupported facts is discarded in favor of the deterministic
text.

Expanded move details are intentionally a separate information layer, not a
longer copy of the summary. Pawn explanations enumerate their verified before-
and-after controlled squares, support of an existing pawn, and newly freed
bishop development. When the best engine move relocates an already
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
attack, approximate material priority, new counterattacks, captures in the first
reply, checks, and newly opened slider lines. A generic list of differently
controlled central squares is no longer rendered as an explanation: it was
correct geometry but repeatedly failed to answer the learner's strategic
question. If the first checked reply captures the focused piece, its temporary
destination attacks are suppressed rather than advertised as a lasting benefit.
Only newly opened lines that reach a central square or opposing piece are kept;
seeing a merely empty adjacent square is not promoted as a teaching point.
Interpretive wording is deliberately qualified: these visible differences can
explain part of an evaluation gap, but the number does not prove one exclusive
strategic cause.

The model may select exactly one summary-eligible atomic fact. The expanded
layer removes a verbatim copy of that summary. Book retrieval never performs a
global SAN-only search when the current opening is unknown: a token such as
`c3` has too many meanings without an exact position anchor.

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

Verbose source/target descriptions are resolved through the current legal move
set. If their piece letters contradict the actual pieces—for example `Kf3xKd4`
where `f3` contains a knight—the service does not silently repair the input or
fall back to the highlighted suggestion. It asks whether the learner means
`Nxd4`, explains the international `K`/`N` distinction, and stores that proposed
interpretation with the current FEN. An affirmative response continues only if
the board is unchanged.

Natural German castling descriptions are also resolved through the legal move
set. Long/large/queenside castling maps to `O-O-O`, and
short/small/kingside castling maps to `O-O`. In an explicit comparison, the raw
engine section prioritizes both named moves over unrelated top candidates. A
narrow board-derived explainer can contrast an advanced g-pawn, a verified
`...h5` lever, existing queen pressure on `h2`/`h7`, and the rook files. It also
states that connecting the rooks is common to both castlings and therefore does
not explain the preference.

Questions may also refer to an accepted learner move after the coach has already
replied. The service replays accepted transition messages, resolves the named or
last learner move, and changes only the analysis context to the verified board
immediately before that move. The live session board, undo stack, and learner log
remain unchanged. Replay begins from the session's recorded initial FEN, so
direct branch drills can answer questions about moves after their custom starting
position. A legal move rejected by the active correction loop is still legal on
the unchanged current board and takes precedence over historical replay.

```text
user question + current FEN + verified transition history + optional highlighted move
  -> resolve and validate one legal move with python-chess
  -> when necessary, reconstruct the historical pre-move board
  -> check local theory membership and resulting opening identity
  -> run standard MultiPV, or a two-pass depth-24 comparison in deep mode
  -> promote an immediate board-proven material consequence, when present
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

Immediate one-ply loss of a previously unattacked queen or rook is a stronger
answer than a general plan. The deterministic detector requires a legal opponent
capture and verifies that the focused move vacated a square between the slider
and its target. When this narrow condition holds, its causal sentence becomes
the answer and both LLM selection and book retrieval are skipped.

The UI estimates remaining time from operation-specific recent histories kept
in browser storage. Scripted repertoire replies and adaptive coach replies use
separate profiles: the former usually needs only board and engine checks, while
the latter can include two Ollama explanations and varies much more. The
adaptive profile starts at 30 seconds; the scripted profile at
4 seconds. Each profile retains the last eight valid measurements and estimates
from their 80th percentile plus a 20-percent and two-second margin. This targets
the upper part of recent experience rather than a mean that is exceeded about
half the time.

The final move of a realistic scripted segment uses the adaptive profile because
that request may cross into free play and generate the first unscripted coach
reply. Versioned storage keys deliberately retire the earlier pooled rolling
average. The countdown remains an estimate and changes to “noch einen Moment”
if work still exceeds it. This preference-like telemetry is device-local and is
not learner-state data.

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

## Local book knowledge

The knowledge compiler imports an owned PDF through Poppler into a separate,
versioned SQLite schema:

```text
PDF
  -> metadata + page geometry + positioned text blocks + image inventory
  -> repeated-header removal + section and chunk reconstruction
  -> claims, concepts, conservative PGN candidates, and extraction issues
  -> FTS5 index + exact position evidence using the existing FEN position key
```

Every claim retains book, PDF page, span, section, and chunk provenance. Dotted
PGN and typeset leading tables such as `1 e4 e5 2 Nf3` are normalized. A
contextual fragment may be reconstructed only from one unique legal position in
the nearest verified parent line; its parent ID, method, and absolute ply range
remain auditable. One leading displayed line anchors its final position, not
every prefix position. Legal embedded comparisons remain searchable without
becoming position anchors. Natural-language move descriptions, unresolved
contextual fragments, statistics, and unpositioned SAN claims remain issues and
are excluded from runtime evidence until separately verified.

Progressive annotated layouts such as `move -> prose -> next move` use a second,
stricter resolver. It requires a verified local parent FEN, exact move number and
color, legal SAN, at least one confirming subsequent move, and one unique
longest continuation. Claims bind to the reconstructed position only in the
same positioned PDF text block or the immediately following block; intervening
numbered moves end the relation unless the claim itself names the focus move.
An ambiguity or branch limit produces an issue, never a preferred guess.

Question retrieval tries the position after the focused move, then the current
position, the exact opening section, a focused move, and finally full-text
question matches. Exact-position evidence stops broadening even when it has no
safe claim, because generic prose must not fill a known position-specific gap.
Section-wide
opening, move-token, and question matches may contribute general plans but not
local recommendations or warnings; those require an exact reconstructed
position. Without a recognized opening, move-token and question broadening are
disabled because SAN alone is not a position identity. The runtime returns at
most a few short safe claims. It never sends the entire book to a model and
never exposes a local filesystem path to the browser.

Broad full-text results must still contain the normalized opening-family name;
a generic term such as `Defense` cannot mix Dutch, French, and Modern chapters.
For a question about the focused side's move, broad plan claims explicitly
written for the opponent are excluded. Actorless broad plans are excluded as
well unless exact-position evidence makes them locally relevant. A learner who
explicitly asks about the opponent's plan can still receive those claims.

Grounded synthesis is intentionally asymmetric. A `source_only` book statement
is always attributed as something the book or author describes. An
opening-level source statement cannot be rewritten as the direct effect of a
specific move. Concrete moves and squares require matching deterministic board
facts; missing evidence links are reconstructed only when an anchor has one
unambiguous verified source. A second local LLM reviews entailment, but its
agreement is not considered proof. Deterministic rules still reject new anchors,
unattributed source claims, excessive certainty, and move-level overstatement.
When the critic identifies individual unsupported sentences, only those
sentences and their evidence links are removed; supported source sentences may
survive. An empty supported remainder rejects the complete synthesis.
The UI receives only a German explanation and compact source metadata. Multiple
used passages from one book render as one card with merged page ranges and the
most conservative validation label; the underlying claim-level references stay
separate for diagnostics and feedback. Failed
generation, weak evidence, or rejected grounding produces a structured status
and an explicit learner-facing knowledge boundary.

## Human explanation feedback

Every message shown in the coach feed receives a session-unique UUID and the FEN
of the position its explanation concerns. For a question about an earlier move,
this is the reconstructed historical pre-move FEN rather than the live board.
The learner can assign one revisable three-state judgment:

- `helpful`: the explanation helped;
- `unclear`: it may be correct, but did not create understanding;
- `wrong`: the learner suspects a factual or positional error.

The first click persists immediately. `unclear` and `wrong` open an optional
note field automatically; helpful answers can receive a note as well. The note
is never required because requiring prose after every half-move would work
against the low-friction training loop.

```text
feed explanation + position UUID
  -> one-click learner judgment
  -> optional note
  -> SQLite upsert of judgment plus immutable explanation context
  -> local review list and API
  -> optional ignored JSON export
  -> human verification before a regression fixture is changed
```

The snapshot contains the position, opening identity, question, move, summary,
expanded sections, engine payload, book-reference metadata, knowledge status,
source, and model. It does not contain retrieved source passages or PDF paths.
One row per `(session_id, message_id)` is updated when the learner changes their
mind; the original creation time remains stable and the update time changes.

An undo operation removes the game turn and its visible coach response as
before, but already submitted explanation feedback remains in the quality log.
That judgment describes a generated artifact and remains useful even when the
learner chooses a different chess move afterwards. The complete snapshot makes
the issue reproducible without relying on the now-mutated game session.

Ratings are signals, not chess ground truth. Neither `wrong` nor `unclear`
automatically changes prompts, book claims, engine thresholds, or regression
expectations. A local review/export step must first determine whether the cause
was factual error, weak pedagogy, missing evidence, wrong position resolution,
or simply a learner preference.

## Guided repertoire practice

Guided practice is a separate session mode rather than a flag on broad theory
matching. An annotated PGN supplies one authored move sequence, explanations for
both sides, and two hints for every learner move. The service validates that PGN
up front and exposes only lesson metadata and progress; it never exposes the
next expected move until the learner explicitly requests a suggestion or
reaches the third failed attempt.

```text
active lesson position
  -> learner plays a legal move
  -> python-chess legality
  -> exact lesson-position and move match
     -> match: authored explanation -> fixed coach reply -> next question
     -> no match: Stockfish quality + hint, board unchanged
        -> third miss: record attempt -> play authored solution -> continue
```

Broad `theory_match`, exact `repertoire_match`, and engine loss remain distinct
values. A lesson can deliberately teach a sound human move that is not
Stockfish's current top-one choice. Turn snapshots include the lesson ply so one
undo restores both half-moves, both explanations, and the previous question.
The current implementation represents each curated opponent response as a
separate annotated PGN game. Accepting arbitrary PGN variations as equivalent
repertoire answers is still a later explicit design decision.

## Persistence

SQLite stores interactions, cached Stockfish results, completed opening
summaries, and explanation feedback. A summary records the final position, identified opening, observed
center/development/king-safety facts, strong moves, correction points, one
takeaway, and an optional review recommendation. The recommendation is data,
not an automatic scheduler action: the learner remains in control.

Active games are held in memory because interrupted games are intentionally not
resumable. The local Python SQLite database remains the source of truth for
learning and explanation-quality data; browser storage is not used for it.
Cloud D1 remains unconfigured because offline-first, single-user persistence is
a settled product requirement rather than an incidental implementation detail.

## Current boundaries

- Single local learner
- Standard chess only
- Untimed free opening play and a guided Italian-from-White scenario family
- No authentication or cloud persistence
- No imported PGN analysis
- No automatic network refresh
- No cloud-generated tutor prose in the product runtime
- No cloud transmission of owned book text
- No resumable interrupted games
