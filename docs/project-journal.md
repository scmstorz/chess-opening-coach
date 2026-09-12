# Chess Opening Coach — Project Journal

This journal records the product discovery, decisions, rejected alternatives,
implementation work, evidence, and course corrections for a later case study.
It deliberately distinguishes settled decisions from working hypotheses.

## 2026-08-29 — Project start

### Initial goal

Build a personal AI-assisted chess opening coach. The long-term learning goal is
not merely to memorize moves, but to understand why opening moves work and to
avoid losing the game through mistakes in roughly the first five to ten moves.

Core principle from the initial brief:

> Keep chess truth outside the LLM. The LLM explains verified facts; it does not
> define them.

The development setup should be local-first. Ollama is the intended initial LLM
runtime. A remote Git repository may be added later.

### Collaboration process

The repository was initialized locally with Git. The assistant then moved too
quickly from permission to initialize the repository into scaffolding an MVP.
The user correctly pointed out that key product decisions had not yet been
discussed. The uncommitted scaffold was removed completely; only the empty Git
repository remained.

This led to an explicit process decision:

- Product discovery proceeds as a one-question/one-answer dialogue.
- Implementation begins only after the relevant behavior and MVP scope have
  been discussed.
- Decisions and their rationale are recorded continuously for a later case
  study.
- Missteps and course corrections are part of the record rather than being
  omitted from the narrative.

### Training scenarios discovered

Two useful scenarios emerged:

1. **Free opening play.** The learner chooses White or Black, starts playing,
   and the coach takes the opposing side. As the move sequence becomes
   identifiable, the coach names the opening and explains how each move relates
   to established theory and objective quality.
2. **Targeted opening practice.** The learner explicitly chooses an opening and
   plays through it while the coach explains why its established moves work.

Additional scenarios are expected later. The first scenario is the priority for
the MVP.

### Agreed interaction behavior

- The coach comments after every learner move.
- The coach also explains every move it plays itself.
- Explanations should remain proportional: routine moves can receive a short
  comment, while critical choices deserve more detail.
- After a relevant mistake or opening deviation, both continuing from the new
  position and correcting the move must be possible.
- The default is correction: undo the move and let the learner try again.
- The coach does not reveal the answer immediately. It gives progressively more
  concrete hints.
- Attempt 1 failure: explain the issue and give a strategic hint.
- Attempt 2 failure: give a more concrete hint, such as the relevant piece,
  pawn break, or target square.
- Attempt 3 failure: reveal and explain the recommended move.

### Breadth decision

The first free-play version should recognize many common openings rather than
mastering only one opening family deeply. The intended practical horizon is the
first five to ten moves, not exhaustive opening theory.

### Proposed chess knowledge architecture

The following division was proposed and accepted as the current direction. It
remains subject to validation during implementation:

- `python-chess`: board state, legal moves, notation, and rules.
- Local `lichess-org/chess-openings` data: ECO codes, opening names, known move
  sequences, and transposition-aware recognition. The dataset is CC0.
- Opening statistics: select several common human opponent moves rather than
  always playing the engine's top choice. A cached Lichess Opening Explorer or
  a local snapshot is a possible later source.
- Stockfish: verify objective quality, compare candidates, and prevent unsound
  recommendations. It is not the opening encyclopedia or the pedagogy layer.
- Ollama: turn structured, verified inputs into explanations. It must not be the
  authoritative source for opening identity, legality, repertoire membership,
  evaluations, or concrete engine lines.
- A user-supplied opening PDF may later enrich strategic explanations through
  retrieval. It should not be the primary source for move legality or opening
  recognition.

Why not use the LLM alone: language models often know common opening ideas, but
can confuse names, exact move orders, and transpositions.

Why not use Stockfish alone: several opening moves can be objectively close;
the engine may favor uncommon moves and has no notion of which line is most
useful to teach a human learner.

### Learner context

The learner reports an online rating of approximately 700. The exact platform
label was given as chess.org and can be clarified later if needed.

The learner mainly plays games with ten minutes per player and no stated
increment. This places the practical target in rapid chess: decisions should
become recognizable quickly, but the training does not need to optimize for
bullet-style reflexes.

Current implications and hypotheses:

- Favor practical opening understanding over memorizing long master-level lines.
- Include common early deviations likely to occur in lower-rated rapid games,
  while keeping the coach's own play sound.
- Prioritize center control, development, king safety, tempo, and loose pieces.
- Do not treat small engine differences as meaningful learner errors.
- Explanations should be concise enough to build usable patterns for a 10-minute
  game, with detail available when a decision is genuinely important.
- Response time can eventually inform learner state.

### Timing modes

Both untimed and timed training should eventually be possible.

- The initial/default experience is untimed so that the learner can think,
  consume explanations, and use the progressive hint loop without pressure.
- A later timed mode should approximate the learner's normal 10-minute games
  and test whether learned patterns can be recalled under practical conditions.
- Timed simulation is not required for the first implementation slice.

### Primary interaction interface

The learner strongly prefers a graphical chessboard with mouse-based drag and
drop if the implementation effort is reasonable. This is considered feasible
and valuable rather than cosmetic: typing notation would introduce notation
errors and distract from position recognition, which is the actual learning
objective.

Current direction:

- The primary product interface should contain an interactive chessboard.
- Pieces can be dragged to make moves.
- The board orientation follows the learner's selected color.
- Move legality should be checked by the chess core, not trusted to the UI.
- A CLI may still exist as a development and debugging tool, but should not
  define the learner experience.
- The product will be a local browser application rather than a native desktop
  application. This is the lowest-complexity way to combine a Python chess
  backend, drag-and-drop UI, and local Ollama/Stockfish services while keeping
  the runtime and learner data on the user's machine.

### Local runtime and ports

The development machine already runs several local browser applications. The
coach must therefore not assume that a common development port such as 8000 or
8080 is available.

- Inspect active listeners before reserving stable development ports.
- Fail clearly if a reserved port is occupied; change it only through explicit
  configuration.
- Keep the documented local URL stable across restarts.
- Bind locally by default rather than exposing the development server on the
  network.

### Color selection

At the start of free play, the learner can either select White or Black or ask
the coach to choose the learner's color randomly. The board orientation follows
the resulting learner color.

### Explanation presentation

Because both learner and coach moves are explained, the interface must avoid a
wall of text.

- Show a short explanation of roughly one to three sentences after each half-move.
- Provide an expandable detail section for deeper strategic context, candidate
  comparisons, and verified engine lines.
- Keep exact engine scores out of the primary explanation unless they materially
  help answer the learning question.
- This layered presentation supports quick pattern recognition while preserving
  depth for deliberate study.

### In-position questions

The learner can pause the game after any move and ask free-form questions such
as "Why not Nc3?" or "What is Black's plan here?"

- The question is bound to the exact current position and move history.
- The game waits until the learner continues; the coach must not advance the
  board while a question is being discussed.
- Concrete candidate moves and variations are verified through chess data and
  Stockfish before Ollama explains them.
- The answer should distinguish engine evidence, known opening information, and
  strategic interpretation, including uncertainty where the evidence does not
  identify a unique reason.

### Progressive opening recognition

The coach should display an opening name early and refine it as more moves make
the classification specific. For example, a broad king-pawn opening can later
become the Italian Game and then a named variation.

- Opening identity is stateful and may become more specific after every move.
- The displayed name may change when a transposition reaches a better-known
  position through a different move order.
- The UI should communicate this as refinement rather than pretending that the
  first broad label was a mistake.
- Recognition comes from opening data and position/move history, not from the
  LLM's memory.

### Language and notation

- The initial user interface is German.
- Tutor explanations are German.
- Move lists and stored game notation use international SAN/PGN notation, such
  as `Nf3` and `Bb5`, rather than localized piece letters.
- Natural-language explanations can still say "Springer nach f3" or "Läufer
  nach b5".
- This keeps imported/exported PGN and external chess data interoperable while
  preserving a German learning experience.

### Tutor tone

The coach should be friendly and encouraging.

- Praise should be specific about what the learner recognized or achieved.
- Do not add exaggerated praise after every routine move.
- State mistakes honestly without shaming language.
- Criticism should lead into a useful question, hint, or next action.
- Explanations should be appropriate for an approximately 700-rated rapid player
  without sounding patronizing.

### Treatment of sound non-theory moves

An objectively sound but uncommon move must not trigger forced correction merely
because it is absent from common opening theory.

- Continue the game by default.
- Explain that the move is playable or good but less common.
- Mention the established alternative and its idea without labeling the learner's
  move a mistake.
- Reserve the undo-and-hint correction loop for a materially relevant chess
  error, not a small engine preference or database mismatch.

This reinforces the separation between opening convention and objective move
quality, especially because free play has no single personal repertoire line.

### Visible engine evaluation

The learner wants to see Stockfish evaluations rather than hiding them in an
advanced detail view. Every displayed value must be explained.

Proposed presentation:

- Show the numeric evaluation and a plain-language interpretation such as
  "approximately equal," "slight advantage," or "clear advantage."
- Explain that `+0.4` is a normalized position evaluation, not a promise of an
  immediate 0.4-pawn material gain.
- Show the change caused by a move when useful, while avoiding exaggerated
  criticism over small fluctuations.
- Represent forced mates separately rather than converting them into enormous
  pawn values.
- Retain engine name/settings with analysis records for reproducibility.

The score uses the standard White perspective:

- positive values mean an advantage for White;
- negative values mean an advantage for Black;
- zero means approximately equal.

This convention does not flip when the learner plays Black. The UI should label
the favored side clearly and explain the convention near the evaluation display,
so the standard remains useful without becoming a beginner usability trap.

### End of the opening phase

The coach should actively notify the learner when the game has probably left the
opening phase. The transition is not assumed to occur at one universal move
number.

At that point, the learner chooses between:

1. Continue the same game into the middlegame with the coach acting as a more
   general chess tutor.
2. Review an opening summary and start another opening game.

The wording should acknowledge that the opening-to-middlegame boundary can be
gradual. A future implementation can combine departure from known opening data
with position features such as development, castling, and central pawn contact.
This is broader than the strict opening MVP, so full middlegame tutoring may be
implemented after the opening loop is reliable.

### Working proposal for the opening summary

The learner does not want to design the report mechanics; the desired outcome is
simply to learn and improve. Product design should therefore translate session
evidence into a compact, actionable summary rather than asking the learner to
interpret raw metrics.

Proposed summary content, to be validated in use:

- The opening and most specific variation reached.
- Two or three central ideas from the played position.
- Important learner moves, separating repertoire/theory fit from objective
  engine quality.
- Mistakes or uncertain positions, including how many hints were needed.
- One memorable takeaway rather than a long list of advice.
- The position or concept the scheduler intends to revisit next.

Detailed move history and engine analysis can remain expandable. The primary
summary should answer: "What did I learn, and what should I practice next?"

### Persistent learner memory without automatic scheduling

The coach should retain learning history across sessions. It may detect that a
position, opening family, or concept caused repeated difficulty and make a
specific recommendation such as "We should practice X again."

However, recommendations must not automatically change or start the next
exercise. The learner remains in control and explicitly accepts or declines a
suggested review. This replaces the initial brief's automatic spaced-repetition
behavior for the foreseeable product scope.

Useful retained evidence may include:

- positions encountered and moves played;
- correct, playable, dubious, and illegal responses as separate categories;
- hints requested and attempts required;
- recurring concepts or mistake patterns;
- session summaries and review recommendations;
- response times, especially once timed mode exists.

### User scope

The initial product is a single-user local application for the repository owner.
It needs no accounts, login flow, permissions model, or multiple learner
profiles. Learner state can be stored directly in the local application database.

### Session persistence boundary

An interrupted game does not need to be resumable after the browser closes or a
session is abandoned. This avoids implementing draft-game lifecycle and recovery
in the initial product.

The distinction is important: learner evidence such as attempts, mistakes,
hints, and concepts can still be persisted for longitudinal coaching even though
the exact board is not offered as a resumable game.

### PGN export

Played sessions should be exportable on demand as standard PGN. Coach
explanations should be embedded as PGN comments where practical, allowing the
game to be reviewed in other chess software without inventing a proprietary game
format. Export is distinct from resumable session storage.

PGN import of previously played platform games is explicitly out of scope. The
coach focuses on interactive games played inside the product rather than growing
into a general post-game analysis tool.

### Opponent move realism

The coach should not exclusively play engine-like main lines. It may sometimes
play plausible inaccuracies that commonly occur around the learner's level so
the learner can practice recognizing and exploiting them.

Guardrails:

- Deliberate training inaccuracies must remain legal and pedagogically useful,
  not random blunders.
- The system must distinguish them internally from recommended opening moves.
- Stockfish verifies their objective impact and the possible response.
- The tutor must never present a deliberately inferior move as established
  theory.
- The mix between sound theory and realistic inaccuracies is not yet fixed and
  should be adjustable rather than buried in LLM behavior.

When the coach deliberately plays such an inaccuracy, it should not immediately
reveal the problem. Instead, it turns the position into a small recognition
exercise: the learner is told that there is something to discover and is asked
to find an appropriate response. The full explanation follows after the learner
has engaged with the position.

The same three-attempt hint ladder used for correcting learner mistakes also
applies to these recognition exercises: strategic hint after the first failed
attempt, more concrete hint after the second, and solution with explanation after
the third.

### Offline feasibility

A fully offline runtime is technically possible after installation:

- The browser UI is served only on localhost.
- `python-chess` and the application run locally.
- Stockfish runs as a local process.
- Ollama and the selected model run locally.
- SQLite stores learner history locally.
- The CC0 Lichess opening-name dataset can be downloaded or packaged locally.
- User-provided PDFs and their retrieval index can remain local.

The main trade-off concerns opening popularity data. Opening names and known
lines are easy to keep locally, but representative move frequencies require
either a prepared local dataset, a potentially large game database, or cached
queries to an online opening explorer. Without online queries, the coach can
still work, but its weighting of "common at this level" moves depends on the
quality and freshness of the local snapshot.

The selected policy is **offline-first, not offline-only**:

- Training and all core functions must work without a connection.
- The application may use the network when it adds meaningful value, for example
  to refresh opening data or query move popularity.
- Retrieved information is cached locally where licensing and source terms allow.
- Network failure degrades enrichment rather than blocking a training session.
- Online data remains an input with provenance, not an unexamined source of
  chess truth.

Online access requires explicit learner consent:

- No silent background refreshes.
- Before a request, identify the source and explain the purpose briefly.
- The learner confirms or declines the operation.
- Declining must not block core training.
- A manual "update data" action can make recurring refreshes convenient without
  weakening this rule.

### Repository state at the end of discovery

- Local Git repository initialized on `main`.
- No application scaffold or dependencies installed.
- This project journal is the only project artifact so far.

## 2026-08-29 — First vertical slice implementation

### Scope approved

The learner explicitly approved implementation of the first milestone with:

- a local browser UI and graphical board;
- free play with selected or random color;
- progressive opening recognition;
- explanations after both sides' moves;
- visible Stockfish evaluation;
- acceptance of sound non-theory moves;
- the three-attempt correction loop;
- local Ollama explanations from verified facts;
- local learning-event persistence.

Free-form questions, deliberate coach inaccuracies, end-of-opening summaries,
PGN export, review suggestions, and timed mode remain later increments.

### Web project setup

The available Sites building workflow was used for the browser surface, but
hosting was intentionally skipped because the product is explicitly local.
The provided starter initially refused to initialize because the discovery
journal made the target non-empty. The journal was moved temporarily, stale
empty directories from the discarded scaffold were removed, the initializer
was run once successfully, and the journal was restored unchanged.

The first package installation failed because the sandbox could not resolve the
npm registry. After explicit approval, installation succeeded with 475 packages.
The starter loading screen was immediately replaced by a recognizable product
slice containing the chessboard, color choice, evaluation bar, opening identity,
and coach panel.

The integrated browser-preview connection failed because its runtime rejected a
`node:process` import. The local route itself compiled and returned HTTP 200.
Implementation continued, with full build and semantic HTTP validation retained
as evidence. No hosting step was performed.

### Port behavior

Active local listeners were inspected before choosing development ports. Many
services were already present, including ports 80, 443, 3306, 5432/5433, 8025,
8456, 8501/8502, 8787, 9200, 9515, and 11434.

An early preview used free port 4173 and the API used 8765. The first finished
launcher asked the operating system for two available loopback ports and printed
the resulting browser URL. A real launcher test selected backend port 49625 and
frontend port 49626 and reached both successfully.

Repeated hands-on sessions revealed the cost of that decision: every backend
restart invalidated the open browser URL, so normal reload and bookmarking did
not work. On 2026-08-30 the launcher changed to stable high defaults: backend
`53686`, browser `53687`. It verifies availability and stops with an actionable
error on conflict rather than choosing a surprise URL. Both remain deliberately
overridable through `CHESS_COACH_BACKEND_PORT` and
`CHESS_COACH_FRONTEND_PORT`. A live restart returned to the same browser URL; a
second concurrent launch stopped before spawning processes and named the
occupied backend port plus its override variable. ADR 0001 records the
amendment.

### Runtime architecture

The browser UI and chess backend were split into two local processes:

- React/vinext for the interaction surface;
- FastAPI/Python for `python-chess`, Stockfish, Ollama, and SQLite.

The development server proxies `/api` to Python, so the browser sees one local
origin. A single `npm run coach` command manages both processes. This decision is
recorded in ADR 0001.

### Opening data

The CC0 `lichess-org/chess-openings` files `a.tsv` through `e.tsv` were downloaded
with their source README and license. Exact provenance:

- commit `4b8622759e7ae6f93f011cc6c83a3823401ab45e`;
- source commit date 2026-08-04;
- retrieved 2026-08-29;
- 3,810 opening entries;
- 5,478 positions with outgoing theory moves.

The graph aggregates source-line coverage as a move weight. This resembles broad
theory prominence but is not actual game frequency or a 700-rating filter. That
limitation is made explicit in data and architecture documentation.

### Stockfish

Stockfish was not installed at discovery time. With explicit approval,
Homebrew installed Stockfish 18 at `/opt/homebrew/bin/stockfish`. The adapter:

- compares the played move with MultiPV candidates;
- uses a short local analysis budget for interactive response;
- normalizes evaluation loss to the side that moved;
- stores visible evaluation from White's perspective;
- caches results in SQLite;
- rejects a proposed coach theory move when it loses at least 0.40 pawns.

A live `1. e4` analysis returned `+0.46` with zero loss. A live `1. f3` test
returned 1.17 pawns of loss, left the board at the initial position, and entered
attempt 1 of the correction loop as intended.

### Local Ollama model experiments

The Ollama service exposed several installed models. Empirical tests were more
useful than choosing solely by parameter count:

| Model | Observed behavior |
| --- | --- |
| `gemma4:31b-mlx` | Good prose, roughly 19 seconds for a small answer, wrapped JSON in Markdown and returned `details` as a list. The first two-explanation move cycle took nearly 50 seconds and fell back. |
| `nemotron-3.5-lightning:30b-mlx` | Consumed the capped output budget in hidden reasoning and returned empty visible content in the test. |
| `qwen3:4b` | About 4.7 seconds with thinking disabled, but the capped response was truncated and the German chess explanation was weak. |
| `qwen3.8:27b-mlx` | Roughly 7.2 seconds for a focused structured answer with good German; selected as the preferred local default. |

The parser was hardened to accept fenced JSON and list-valued detail text. Model
selection remains configurable through an environment variable.

### Hallucination found during live integration

The first successful Ollama-backed end-to-end response exposed a critical
grounding failure in `qwen3.8:27b-mlx`. After `1. e4 g6`, the model incorrectly
associated Black's move with the King's Gambit and added unsupported frequency
claims. The same response also introduced the Sicilian Defense while explaining
`1. e4`, although no such classification was present in the supplied facts.

There was also an application-side context bug: while explaining `1...g6`, the
prompt still contained the broader identity from before Black's move (`King's
Pawn Game`) rather than the newly reached identity (`Modern Defense`). This
stale label may have made the task less clear, but the prompt never contained a
King's Gambit label and therefore did not support the model's concrete claim.
Both the context ordering and the generated-output boundary were corrected.

The architecture was changed rather than merely tweaking the prompt:

1. Deterministic code now creates a complete verified summary and detail text.
2. Ollama may only paraphrase this draft.
3. Generated opening terminology and numeric facts outside the draft cause
   rejection.
4. Rejected, malformed, slow, or unavailable model output falls back to the
   verified draft.

After hardening, a live `1. e4 e6` cycle produced a grounded Ollama explanation
for the learner move. The coach explanation safely used the deterministic
fallback when the validator rejected the generated expansion. ADR 0004 records
the decision and its evidence.

### Glimmer and Ornith comparison

At the learner's suggestion, `muse-glimmer:30b-mlx` and `ornith-1.5:35b` were
compared with the selected Qwen model using a reproducible local benchmark. Six
common opening identities, seven objective concept questions, a deliberate
King's Gambit false premise, and the real grounded tutor adapter were tested.

Glimmer scored 6/6 on identities and 7/7 on the objective choices, making it the
most promising chess-knowledge candidate in this small test. Qwen scored 6/6
and 6/7; Ornith scored 5/6 and selected 7/7 choices, but its JSON was malformed
and its free prose contained several serious factual or linguistic errors.
Glimmer also produced some imprecise free explanations and did not fit the
current adapter's small structured-output budget. The default therefore remains
Qwen pending a larger, repeated benchmark and Glimmer-specific adapter tuning.

The benchmark runner and the full result review are retained in
`scripts/benchmark_ollama_chess.py` and
`docs/evaluations/2026-08-29-ollama-chess-models.md`.

### First learner usability finding

The first manual launch exposed an onboarding failure before the learner could
make a move. Selecting White looked sufficient, but the board remained inactive
until the separate `Training starten` button below it was pressed. The server
log confirmed that no session request had been sent; chess move handling itself
had not failed.

The inactive board now has a prominent overlay stating that training has not
started, explaining the required action, and offering the start button directly
on the board. This keeps session creation explicit while removing the ambiguous
appearance of draggable but inert pieces. The finding is important for the case
study: the first real user interaction caught a workflow problem that static
rendering and backend integration tests could not reveal.

The next learner feedback concerned board readability and temporal continuity.
White used the traditional hollow Unicode chess glyphs, which looked visually
weaker than Black, and the API returned the learner and coach moves together in
their final position. The board therefore appeared to jump, making the coach's
reply hard to follow.

Both colors now use filled silhouettes differentiated by their CSS color. Each
accepted feedback message also carries its verified UCI move and resulting FEN.
The browser replays these transitions in order, first the learner move and then
the coach move, while input remains locked. This preserves the backend as owner
of accepted board state and avoids optimistic animation of a move that the
three-attempt correction loop might reject.

The first animation version was immediately corrected after hands-on feedback:
replaying the learner's own drag after the coach finished thinking felt
redundant and temporally wrong. The browser now applies a legal learner move
visually as soon as it is dropped, then animates only the coach reply once the
verified response arrives. If the backend rejects a materially bad move, the
optimistic visual position returns to the verified position; on the third failed
attempt, the system-provided solution remains eligible for animation because it
is not the learner's submitted move.

A compact SVG chessboard in the existing green and neutral palette was added as
the browser favicon. SVG was chosen over a generated raster asset because the
geometric motif stays crisp at small browser-tab sizes and remains easy to
version and recolor with the interface.
After browser inspection, its outer background was changed from green to white
while retaining a green frame around the board for contrast at tab size.

A screenshot from the continuing manual session exposed two more layout issues.
The thinking overlay obscured too much of the position, and the fixed 470-pixel
message-feed limit left a large unused vertical region in the otherwise tall
coach panel. The board now retains 90% opacity with only a light translucent
input-blocking overlay. The feed is a flexible child that consumes the available
panel height down to the truth and question controls. It also scrolls smoothly
to its bottom whenever new feedback arrives, matching the turn-by-turn nature
of the session and removing repetitive manual scrolling.

That first flexbox adjustment was insufficient because the grid row could still
grow with the feed's content; `overflow-y: auto` has no effect without a bounded
height. The coach panel is now a sticky, viewport-bounded flex container on
desktop. Its feed uses the remaining height with `min-height: 0` and internal
vertical scrolling, while the heading, truth sources, and question control stay
fixed. The stacked layout uses a bounded feed region rather than a sticky panel.

The learner then requested a turn-back control with an important semantic
constraint: undoing their move must also remove the coach's reply. Undo is
therefore modeled as a verified learner-turn transaction rather than a raw
single-ply board pop. Before each accepted learner turn, the service snapshots
the board, opening identity, move-list length, feedback-list length, and latest
SQLite interaction ID. `Zug zurück` restores that snapshot, removes both plies
and both explanations, and deletes the corresponding interaction records so an
undone experiment does not distort later learning statistics. Snapshots form a
stack, allowing repeated undo while preserving an initial coach move when the
learner chose Black.

The explicit start gate was reconsidered once the onboarding overlay made its
purpose visible. It protected no meaningful choice: White was already the
default, sessions are local and disposable, and a new-game control exists. The
extra state therefore cost one click while making the initial board feel inert.
The browser now creates a White session on page load without darkening the
board. Selecting White, Black, or Random immediately creates a corresponding
fresh session, while `Neue Partie` repeats the currently selected choice. This
is a useful product-design reversal for the case study: improving explanation
of an unnecessary step did not make the step necessary.

The same feedback added a learner-controlled `Zug vorschlagen` hint. It was
deliberately not implemented as an LLM answer and does not play automatically.
The local opening graph supplies candidates; Stockfish rejects objectively
problematic theory edges; the interface highlights source and destination and
shows a short deterministic reason. The selection favors the most represented
safe theory edge, using a 0.40-pawn safety threshold. If the engine is offline,
the local theory ranking provides the fallback. Requesting a suggestion does
not create a learner attempt, change the board, or affect later review data.

Restarting the running development stack exposed a fixed-port edge case on
macOS: after a clean shutdown, neither service was listening, but the backend
port remained temporarily reserved by the operating system. The launcher's
bind probe reported this `TIME_WAIT` state as a port collision. Its read-only
availability socket now enables address reuse, which still rejects an active
listener but permits an immediate restart on the same stable URL.

Verification after this change: all 12 Python tests pass, Python and web lint
are clean, the production build and rendered-shell test pass, and an end-to-end
request returned the theory move `1.e4` with Stockfish 18 verification in 0.16
seconds. An immediate stop/start cycle also succeeded on ports 53686/53687.

### Suggested moves exposed the next learning interaction

The first use of `Zug vorschlagen` immediately produced the natural follow-up
question “Warum ist dieser Zug gut?”. The visible question field was still a
disabled roadmap placeholder, which made the otherwise coherent learning flow
stop exactly where understanding should begin. This observation promoted
grounded position questions into the next vertical slice.

The browser now sends the question together with the current session and the
highlighted suggestion. The backend validates the reference against the current
legal moves, checks its local-theory membership and resulting opening identity,
and asks Stockfish for quality and a short principal variation. It then creates
a set of complete deterministic answer facts. The question is context, never
chess evidence. The answer appears in the same scrolling feed and retains the
original question. Asking changes neither the board nor the SQLite learner
statistics.

An explicitly written legal SAN or UCI move overrides the highlighted
suggestion, preventing a question such as “Warum nicht d4?” from accidentally
receiving an explanation of the prior hint. If no move is named and no hint is
active, the service uses the same highest-ranked, engine-safe theory candidate
as the suggestion feature. If local theory has ended, the service now uses
Stockfish's preferred legal move as the concrete anchor and identifies its
engine basis instead of presenting it as opening theory.

GPT-OSS 20B was added to the existing local chess benchmark before choosing a
model for this interaction. It scored 6/6 opening names and 7/7 concept choices,
including the adversarial false-premise case, with valid JSON. This is the best
raw result in the small benchmark alongside Glimmer. However, GPT-OSS returned
no parseable visible content through the current schema-constrained grounded
adapter and fell back after 0.47 seconds. Qwen remains the production default
because its adapter behavior is currently more reliable; GPT-OSS is now the
leading candidate for provider-specific adapter tuning, not a new source of
chess truth.

The first live Qwen question initially looked fluent but added the sentence that
there were no tactical disadvantages or material losses. Neither claim existed
in the Stockfish data or deterministic answer, and the earlier lexical validator
did not catch the semantic expansion. This became a second concrete grounding
failure. Before release, the question adapter was changed from free
paraphrasing to verified-fact selection: Ollama receives atomic explanation
blocks and may return only their IDs in a small JSON object. The backend renders
the original verified sentences. Every returned ID is checked against an
allowlist. Thus the model can decide which facts best
answer “why?”, “theory?”, or “best move?”, but cannot write a new chess claim.

The hardened live test succeeded with Qwen. For “Warum ist dieser Zug gut?”
after the `e4` suggestion, the model selected the verified verdict, central-space
concept, theory membership, and engine-quality facts in 2.97 seconds. The
rendered prose contained no model-authored chess sentence. A second question,
“Warum nicht d4?”, correctly overrode the still-highlighted `e4`, analyzed `d4`,
and returned its verified concept and principal variation. The final automated
state is 15 passing Python tests plus clean Python/web lint, production build,
and rendered-shell test.

### Opening coverage is not the boundary of useful help

Continued play revealed that `Zug vorschlagen` still treated the end of the
local opening graph as the end of its responsibility. In the middle of a game,
the learner received “Für diese Stellung ist kein Zug in der lokalen
Eröffnungstheorie hinterlegt”. The statement was factually correct but
product-wise wrong: a request for help is still meaningful after the opening.

Suggestion selection is now explicitly two-stage. While local theory is
available, the existing coverage ranking and Stockfish safety check remain in
control. Once theory coverage ends, Stockfish supplies its current preferred
legal move. The response carries `basis: theory|engine`, and the browser labels
the latter `Engine-Vorschlag`; it never presents an engine-only move as opening
orthodoxy. The same fallback supports position questions without a named move.
If Stockfish itself is unavailable beyond local theory, the service states this
capability limit rather than guessing.

This change preserves learner agency and state semantics: a suggestion only
highlights the move, records no attempt, adds no move to the board, and can still
be followed by “Warum ist dieser Zug gut?”. A new service test removes all local
theory edges and verifies the complete engine branch, while the conditional
engine test verifies that the returned move is legal and practically equal to
Stockfish's own best result.

### “More details” must mean more explanation

A second live example exposed a pedagogical quality problem. The summary for
`c3` said that a pawn move “legt neue Felder dauerhaft fest”; expanding the
details repeated that phrase, added an evaluation, and named `Ba4` without
explaining either relationship. The details were longer but not deeper. The
root cause was a generic pawn template plus a model prompt that allowed summary
and detail content to drift between output fields.

Pawn explanations now derive exact square changes from the board. For `c2-c3`,
the coach says that the pawn changes its control from `b3/d3` to `b4/d4`, that
pawns cannot move backwards, and—when true—that the occupied square is no
longer available to a knight. A separate deterministic contrast checks whether
the engine's preferred move responds to an already attacked piece that the
learner's move leaves in place. In the concrete `1.e4 e5 2.Nf3 Nc6 3.Bb5 a6
4.c3` fixture, the detail must now connect all three facts: the bishop on `b5`
is attacked, `c3` leaves the attack in place, and `Ba4` moves the bishop out of
it. Short played-move and best-move Stockfish variations expose the calculation
behind the comparison and are explicitly described as examples rather than
forced lines. The tutor prompt now keeps verified summary and verified detail
in their respective output layers. A grounding regression additionally rejects
any rewrite that moves or drops concrete move, square, or number anchors from
the expanded detail layer; the deterministic explanation is safer than a fluent
but emptied-out rewrite.

The learner proposed consulting Qwen, GPT-OSS, and Ornith and merging all
comments. This was recorded as an evaluation direction, but not adopted as the
runtime truth mechanism. Several fluent model opinions do not become verified
by consensus, and merging them makes provenance, contradiction handling, and
hallucination checks harder. The current decision is to improve the verified
facts first and use one selected local model for pedagogy. A later optional
“deep explanation” experiment may let multiple models propose interpretations
only if every surviving chess claim maps back to board, repertoire, or engine
evidence.

The original local interaction was retained in SQLite and made the regression
reproducible: before `c3` the FEN was
`3r1rk1/ppp2ppp/3q1n2/1B2p3/2Pn4/3P3P/P1P2PP1/R1BQR1K1 w - - 3 14`.
Stockfish measured a 0.43-pawn loss, preferred `Ba4`, and calculated the sample
continuation `c3 Nxb5 cxb5 Qxd3`. Running the revised code against that exact
position now explains that the bishop on `b5` is attacked, that `c3` leaves the
attack in place, and that `Ba4` moves the bishop away before showing either
number or line.

Verification after both changes: 19 Python tests pass, including the explicit
attacked-bishop regression and a real-Stockfish best-move check. Python and web
lint, the production browser build, the rendered-shell test, and whitespace
checks are clean.

### A generic template contradicted the board: the `Na2` case

The next live challenge was sharper: after an engine suggestion of `Na2`, the
coach answered that the knight was developed and influenced central squares.
The learner correctly objected that a knight on the rim does neither. This was
not an LLM hallucination in the usual sense. The false sentence came from the
deterministic `_move_concept` template, and Qwen's grounded selector faithfully
selected that bad input. “Deterministic” therefore did not mean “true”; the
fact producer itself needed verification.

The exact position was recovered from the running local session:
`r1b2rk1/p3nppp/2pq1n2/1p2p1B1/Pb1pP2N/1BNP1Q2/1PP2PPP/R4RK1 w - - 0 13`.
A three-second Stockfish 18 MultiPV check confirmed `Na2` (+0.43) over `Nb1`
(-0.06) and `Nd1` (-0.34), but the evaluation alone still did not answer why.
Board geometry revealed the causal explanation: the black pawn on `d4` attacks
the knight on `c3`; `Na2` escapes that attack and simultaneously attacks the
black bishop on `b4`. In the principal variation `Na2 Bc5 Nc1`, the bishop moves
away and the knight immediately continues to `c1`. The rim square is a
double-purpose intermediate square, not an active permanent post.

The first hand-written model probe itself listed only `c1/b4` and omitted the
additional controlled square `c3`. That transcription mistake did not affect
the central-square conclusion, but it supplied another reason to generate
facts from board geometry rather than manually composing model context.

The learner explicitly asked whether the LLM could provide the explanation.
Qwen, GPT-OSS, and Ornith were tested with the same verified position and engine
facts. Free generation did not solve the reliability problem: Qwen invented a
`c1-a3` diagonal and called `Na2` the only saving move; GPT-OSS returned no
visible answer; Ornith claimed `Nb1` moved the knight to `c1` and cited unrelated
evidence. These outputs reinforced the claim-level grounding boundary rather
than arguing against LLM use.

The corrected pipeline now asks Qwen to rank complete verified facts. Actual
piece attacks, controlled squares, central-square intersection, counterattacks,
and same-piece PV continuations come from `python-chess` plus Stockfish. Facts
that carry the causal explanation are marked required and appended if the model
does not select them. In an isolated live run Qwen selected a concise answer
that explicitly agreed with the learner's rim heuristic, named the attack from
`d4`, listed `c1/c3/b4` and no central squares, identified the attack on the
bishop at `b4`, and explained the temporary `a2-c1` route.

The regression suite now contains the exact FEN and forbids the word
“entwickelt” in this explanation. Verification: 21 Python tests pass; Python
and web lint, the production build, rendered-shell test, and whitespace checks
are clean.

### Explanation-quality sprint: from verdict to comparison

The learner approved a focused quality sprint before further feature work. The
goal was not longer prose but a repeatable answer to three different questions:
what the move changes, why a plausible alternative differs, and which concrete
lines support the comparison.

Stockfish now has two time budgets. Normal move feedback retains the fast
0.12-second check. Questions use a cached 0.8-second, depth-18 MultiPV search for
three candidates. When the questioned move is outside that top group, it is
analyzed separately as a forced root move at the same depth. This mattered in
the original `c3` case: a short analysis sometimes returned only the move name,
whereas the focused line reliably continued `c3 Nxb5 cxb5 Qxd3`.

The comparison layer does not ask an LLM to infer differences from two scores.
It computes them from both resulting boards: which attacked piece each move
saves, which own piece stays attacked, approximate material priority, new
counterattacks, direct central control, and captures in the first reply. It also
detects checks and lines newly opened for bishops, rooks, and queens. Any
strategic synthesis is labeled as explaining a plausible part of the engine
gap, never its single proven cause.

For `Na2` the real output now compares it to `Nb1`: both save the attacked
knight, but only `Na2` attacks the bishop on `b4`; the lines then show `...Bc5`
and the knight's continuation to `c1`. For the other real failure, the parser
first needed a correction: “Warum ist c3 schlechter als Ba4?” had selected
whichever legal move appeared first internally rather than the first move named
in the question. It now respects textual order. The comparison then shows that
`c3` answers the attack on the pawn at `c2` and counterattacks the knight, but
leaves the three-point bishop on `b5` attacked; `Ba4` saves that bishop while
leaving only the one-point pawn exposed. The forced line confirms `...Nxb5`.

The browser expander now has three visible sections: concrete effects,
alternative comparison, and Stockfish lines with the White-positive score
convention repeated in context. Qwen still chooses the concise top-level facts,
while required causal facts and all three evidence sections remain
deterministic. A complete local run with Stockfish and Qwen succeeded in 13.05
seconds with no unsupported model-authored chess text.

The two learner-discovered failures are now stored in
`backend/tests/fixtures/explanation_cases.json`. The machine-readable corpus
contains FEN, question, focus move, engine lines, required phrases, and forbidden
claims so future explanation changes can add cases without inventing a new test
shape. The suite has 25 passing Python tests, plus clean Python/web lint,
production build, rendered-shell test, and whitespace checks.

### Main heading simplified

The learner replaced the campaign-like main heading “Deine ersten Züge. Mit
Plan.” with the direct product-area label “Eröffnungen”. The eyebrow still
identifies the current mode as free opening play, so the shorter heading avoids
repeating the same context and leaves room for future training modes.

### Closing the first learning loop

After the explanation-quality work, the next product step was chosen by asking
what the free-play experience still lacked rather than adding another mode. The
answer was closure: the coach could explain an unlimited sequence of moves but
did not yet say when the opening was probably over, extract a lesson, or retain
a reviewable result. The learner approved this as the next vertical slice before
targeted opening practice.

The phase boundary deliberately does not use either a universal move number or
the local opening graph alone. The implemented heuristic combines remaining
theory moves, elapsed half-moves, minor pieces no longer on starting squares,
castling history, and movement of the four d/e pawns. An early deviation can
therefore exhaust local theory without ending the opening. The UI exposes every
signal and calls the boundary “wahrscheinlich”, preserving the learner's final
decision.

At the transition the board pauses. The learner can continue into a middlegame
mode, where Stockfish rather than opening theory supplies coach moves and hints,
or request an opening review. The review contains the most specific opening
identity reached, exact center/development/king-safety observations, counts of
theory and near-best moves, correction points, one takeaway, and—only when the
evidence supports it—a suggested position to revisit. The recommendation is
stored but never starts an exercise automatically.

Completed reviews live in a new local SQLite `session_summaries` table; active
games remain intentionally in memory. This respects the local-only architecture
and keeps learning data out of browser storage. The summary path is
deterministic because the current knowledge sources do not support reliable
opening-specific strategic prose for every detected line. The LLM is not used
to fill that gap with plausible-sounding claims.

The regression suite now covers early theory departure, multi-signal phase
detection, the explicit continue path, automatic transition notices, persisted
grounded summaries, and the API round trip. The suite contains 31 passing Python
tests before final browser-build verification.

### First-slice verification evidence

At the time of this journal entry:

- Python tests: 9 passed, including a conditional real Stockfish adapter test
  and grounding-regression tests.
- Python lint: clean after formatting and import correction.
- Web lint: clean.
- Vinext production build: successful.
- Initial rendered route: HTTP 200.
- Stable launcher: successful on the documented ports with explicit overrides.
- Local health: 3,810 opening entries, Stockfish available, Ollama available.
- Live sound move: accepted, identified, evaluated, explained, followed by a
  verified coach response.
- Live mistake: board rollback and first correction hint confirmed.

One third-party warning remains in Python tests: Starlette reports that its
current `httpx`-based `TestClient` compatibility path is deprecated in favor of
the future `httpx2` package. It does not fail the tests and is outside application
code.

### From square lists to plan explanations

Continued real play found that mechanically correct detail was still not
necessarily educational. The coach introduced the first identifying move as if
it continued an already established opening, repeated the trivial fact that
pawns cannot move backwards, missed that a knight moving to `d5` occupies a
central square, and justified `Ra6` only by its destination and evaluation.

The first repair is semantic. Opening feedback now distinguishes the first
identification (“beginnt die Eröffnung”), a transition to a more specific named
variation, and continuation of the same identity. Piece templates no longer say
that a non-central move fails to control the center, and pawn comments no longer
compare old attack squares or state generic irreversibility. A knight's occupied
square is considered separately from the squares it attacks.

The deeper issue was unstable and impoverished evidence. Middlegame coach moves
now use a two-second selection budget instead of the shorter explanation search.
Normal questions build evaluation and line data from one comparison snapshot.
The new optional `Tief erklären` action discovers four candidates and then
rechecks the common root set with a five-second, depth-24 budget. It searches the
resulting lines for restrained pawn breaks, stable central posts, clarifying
exchanges, flexible move orders, own-side follow-up moves, and motifs recurring
across candidates. The wording calls these model plans rather than claiming that
Stockfish supplied a human reason.

The browser shows the deep option beside a highlighted suggestion and beneath
the free-question field. A lightly shaded board overlay reports the current
operation and an estimated seconds countdown. Each operation type learns a
rolling duration from previous runs on that browser. When work outlasts the
estimate, the UI says “noch einen Moment” rather than pretending to know an
exact completion time.

The authorized cloud experiment used Kimi K3 and DeepSeek V4 Pro on the exact
`a4`, `Nd5`, and `Ra6` cases. Non-thinking responses took 6.48–14.57 seconds for
Kimi and 6.96–11.02 seconds for DeepSeek, excluding Stockfish. Both were more
fluent, but both added unsupported positional claims; DeepSeek made especially
clear FEN-level errors in the `Nd5` and `Ra6` explanations. The experiment is
therefore retained as negative design evidence: stronger prose does not remove
the grounding problem. Full method and findings are recorded in
`docs/evaluations/2026-09-08-cloud-chess-explanations.md`.

After this increment, 33 Python tests pass, Python and web lint are clean, the
production browser build succeeds, and whitespace validation is clean.

### Choosing both a knowledge compiler and a better teaching outcome

The cloud-model experiment led to a new source strategy: instead of asking a
more fluent model to invent the strategic reason for an engine move, compile
human-authored chess explanations into a local, citable evidence layer. A
detailed agent briefing proposed a complete offline compiler for a 2021
beginner-opening book, with page- and bounding-box provenance, FTS5 retrieval,
conservative chess parsing, and strict separation from the existing opening
graph and Stockfish.

Review exposed an important product distinction. One possible milestone was a
technically complete, searchable book database. Another was a visibly better
answer to an actual learner question such as “Why is Bb5 useful?”. The former
does not automatically produce the latter: the initial briefing intentionally
kept book passages outside the tutor's verified answer facts and would first
have displayed them only as references. The learner rejected the implied
choice and required both outcomes.

The chosen path keeps the whole-book compiler but stages it toward grounded
synthesis. First, existing failures become a before-state evaluation set. The
complete PDF is then imported with stable provenance and searchable chunks.
Position-, opening-, move-, and question-aware retrieval is connected to the
coach before a final synthesis layer combines four explicitly labelled evidence
classes: board facts, opening data, Stockfish results, and attributed book
passages. Extraction, retrieval, and explanation can thus fail—and be measured—
independently.

The learner explicitly authorized automatic processing of the short retrieved
passages by the local Ollama model. The whole book is never placed in a prompt,
and no network permission is involved. Book prose remains untrusted source
material: “the author recommends X” is valid provenance, but it does not become
engine or repertoire truth through paraphrasing. Cloud transmission of book
text remains outside this decision and would require a separate, explicit
confirmation.

This planning step also changed the definition of done. The knowledge work is
not complete when rows exist in SQLite. It must both make the full book locally
searchable and show measurable educational improvement on the captured real
questions. OCR, embeddings, diagram-to-FEN, and multi-book consensus remain
deliberately deferred until those two outcomes are evaluated.

The next UI question exposed another division of responsibility. Showing the
English source excerpt next to its German explanation would make provenance
visible, but it would also ask the learner to read everything twice and verify
the model personally. The learner explicitly rejected that burden. The normal
feed will show a single German explanation plus compact source metadata, while
the original passage stays in the compiler for diagnostics, tests, and later
editorial review.

This raises the grounding bar for the implementation. Every synthesized
sentence must cite internal evidence IDs; moves, numbers, names, variants, and
board effects can be checked deterministically. A second local model can serve
as an extra entailment critic, but agreement between probabilistic models is not
proof. If a strategic paraphrase cannot be tied back confidently enough, the
safe behavior is a conservative fallback rather than fluent unsupported prose.

The learner strongly confirmed that refusal is the desired product behavior,
not an unfortunate technical edge case. The coach may retain facts it can prove
but must say when it lacks a sufficiently supported explanation of the
long-term purpose. Generic principles must not be used to disguise that gap.
The implementation will expose a structured fallback reason so that these cases
can be counted, inspected, and turned into retrieval or knowledge-base work.

### Implementing the first local knowledge compiler

The owned reference PDF was copied into `data/books/` as a durable local source.
That directory is the standard location for later books as well. PDFs and the
derived knowledge database are ignored by Git so a future public repository
does not redistribute copyrighted material. A tracked registry records title,
checksum, and import date, making the private source reproducible without
publishing its contents.

The compiler uses Poppler's existing text and geometry tools rather than
starting with OCR. It stores book metadata, pages, positioned spans, sections,
chunks, FTS rows, claims, concepts, candidate lines, exact position evidence,
diagram metadata, aliases, and issues in a separate versioned SQLite database.
Runtime opens this database read-only. Exact chess positions use the coach's
existing canonical FEN key; the compiler does not introduce a parallel hashed
identity. Only numbered lines beginning at `1.` for White are reconstructed.
Natural-language move prose and fragments without a known start position are
retained for inspection but not promoted to position evidence.

The real import yielded 122 pages, 962 spans, 67 sections, 100 synchronized FTS
chunks, 399 claims, one valid numbered line with three position-evidence rows,
38 images, 31 likely board diagrams, and 70 explicit issues. SQLite integrity,
foreign keys, FTS synchronization, orphan checks, and index-use checks all
passed. A German “Spanische Partie” query resolves through aliases to the Ruy
Lopez section on PDF pages 18–20.

Visual inspection changed the meaning of “source of truth”. The PDF is the
source of truth for what its author says and where it appears, but not for chess
correctness. It contains, among other problems, probability arithmetic in which
38% plus 25% becomes a claimed 75%, and malformed move prose such as “King's
pawn to e2”. The compiler therefore splits usable prefixes from unsafe sentence
tails, quarantines statistics and natural-language move claims, and labels the
remaining prose `source_only` rather than silently calling it verified.

The first `Bb5` synthesis produced a useful implementation failure sequence.
Qwen first exhausted a too-small structured-output budget, then cited only the
book for a concrete move anchor, and finally converted the book's general Ruy
Lopez purpose into the stronger statement that `Bb5` directly disrupts the pawn
structure. A second local LLM critic accepted the overstatement. This confirms
the earlier decision that probabilistic agreement is an extra check, not proof.

The accepted path now gives each generated sentence evidence IDs, repairs a
missing concrete-anchor link only when exactly one verified fact contains that
anchor, requires explicit attribution of every `source_only` sentence, and
forbids an opening-level source claim from sharing a sentence with concrete move
notation. Repeated source paraphrases are dropped instead of making the learner
read the same idea twice. For `Bb5`, the book's attributed general plan is kept
separate from the board-derived fact that the bishop attacks the `c6` knight,
which also defends `e5`. The browser receives only this German synthesis and
compact source metadata; the English passage and local path remain internal.

A final integration run found one more structural trap: Qwen placed a valid
translation and an unsupported “destabilize the opponent” expansion into one
JSON `summary.text` value. The critic rejected the combined value, correctly,
but the product had promised sentence-level rather than field-level evidence.
The parser now splits every generated field into actual sentences, applies the
grounding rules to each, and retains only supported non-redundant sentences.
Retrieval was tightened at the same time to return atomic claims instead of
concatenating unrelated plan, definition, and history claims from a chunk.
After those changes, the real end-to-end `Bb5` request returned `grounded`, used
the page-20 plan claim, and serialized only safe source metadata to the browser.

The result and remaining limits are recorded in
`docs/evaluations/2026-09-09-book-knowledge-baseline.md`. The other real learner
failures (`c3`, `Na2`, `a4`, `Nd5`, and `Ra6`) remain evaluation cases rather
than being declared fixed merely because a book database now exists.

### A stronger second book challenges the layout assumptions

The learner selected Paul van der Sterren's *Fundamental Chess Openings* as the
second permanent local source and expected it to be good. The 14 MB PDF was
copied unchanged into `data/books/`; its SHA-256 is recorded in the local-source
registry and the file remains Git-ignored. The publisher note explicitly dates
the book to 2009, while unrelated conversion timestamps also occur in the front
matter. Metadata inference was therefore extended to accept only explicit
publication wording instead of guessing from arbitrary dates.

The expectation about content survived visual review. Ruy Lopez pages 642-647
and Queen's Gambit Declined pages 17-18 show clean diagrams, side-to-move labels,
and precise strategic prose. But the 1,252-page Kindle layout exposes a compiler
assumption: move numbers and moves are separate visual table columns, producing
text like `1 e4 e5 2 Nf3 Nc6 3 Bb5` rather than dotted PGN.

The parser now normalizes this typeset form before `python-chess` validation. It
finds 213 complete legal lines. Treating all intermediate positions of those
lines as evidence anchors immediately produced a dangerous false retrieval: a
Panov Attack paragraph containing an embedded comparison to `1 d4 d5 2 c4`
appeared as an exact source for the early Queen's Gambit position. This was legal
chess and wrong evidence.

The repaired rule anchors commentary only to the final position of a displayed
line beginning near the start of its chunk. Legal embedded comparisons remain
searchable but do not bind the surrounding prose to a position. Retrieval checks
the position after the questioned move first and stops at exact facts instead of
padding the answer with broad opening matches. The second import consequently
retains 213 complete lines but promotes only 55 high-confidence final-position
anchors. Concrete SAN in prose is quarantined until a unique start position can
be reconstructed.

The high issue count—5,508—is an observability result rather than a verdict on
the book: 3,516 fragments need earlier context, 1,548 claims contain unpositioned
SAN, 263 natural-language move descriptions need context, and 158 legal embedded
lines are deliberately not anchors. Fourteen assumed-start lines are genuinely
invalid. The database remains structurally sound with 1,399 synchronized FTS
chunks across both books.

The first positive product result uses the exact position after `1 d4 d5 2 c4
e6`. Van der Sterren describes Black as holding the centre while preparing
natural development. A real local Stockfish/Qwen run returned a grounded German
answer that connected this attributed plan to the verified squares `d5` and
`f5`, the freed bishop on `f8`, and a model development sequence. Only the book,
author, year, and PDF pages 17-18 reach the browser.

The Ruy Lopez result is intentionally less gratifying. The table ending in
`3 Bb5` is reconstructed correctly, but the nearby introduction mainly covers
history and Black's alternatives. It does not directly establish a safe
long-term purpose for `Bb5`. The coach retains the earlier board-derived
defender explanation rather than laundering the prestige of a good book into an
irrelevant answer. The next high-value increment is therefore contextual
reconstruction of variation fragments, not a third book.

### Closing the six-case explanation loop

The learner approved all five proposed steps: checkpoint the two-book system,
create a fixed quality corpus, reconstruct safe book context, deepen the
explanation path, and rerun the same cases. Commit `44fb06c` first preserved the
two-book compiler baseline before the new work began.

The initial machine-readable corpus covers the reported `c3`, `Na2`, `a4`,
`Nd5`, `Ra6`, and `Bb5` failures. Its first action was to reject two transcribed
FENs because their focus moves were illegal. Correcting the fixtures rather than
working around the failure became a small but important case-study lesson:
evaluation evidence is not exempt from chess verification.

The book compiler now understands a conservative subset of abbreviated
variation fragments. It accepts a fragment only if a single position inside the
nearest verified parent line has the correct move number and makes the complete
fragment legal. Parent ID, inference method, start FEN, and absolute ply range
are stored. A same-chunk Ruy Lopez line safely reconstructs `3...a6 4.Ba4` from
the complete `1.e4 e5 2.Nf3 Nc6 3.Bb5` line. The full second-book import resolves
79 fragments and increases final-position evidence from 55 to 61 anchors;
3,437 context-dependent and 14 invalid lines remain unavailable. Diagram images
are not promoted to FEN authority because reliable board recognition has not
yet been built.

The first real end-to-end run revealed a more important failure than a red test.
The `c3` case had no recognized opening identity, so global move-token retrieval
found a statement on PDF pages 719-720 saying that “this question” caused a
major disagreement. Qwen translated it faithfully, the evidence links were
valid, and the result was still irrelevant to the learner's position. `Nd5`
found a similarly vague passage. Retrieval now allows broad move and question
search only inside a recognized opening section; unidentified positions require
an exact position anchor. This distinguishes provenance correctness from
relevance correctness.

Deep analysis now asks two independent engine questions. The root comparison
measures the focus move against top and explicitly named alternatives under one
search setting. A new post-move search checks three plausible opponent replies
and reports own-side follow-ups only when they recur across branches. Inferior
moves no longer inherit a supposed plan from a recovery line. The `Ra6` case now
corrects the user's “best move” premise to `...b5` and admits that no supported
long-term rook purpose is available. For `c3 versus Ba4`, the named `Ba4` is
actually included in the consistent comparison instead of silently discussing
another engine candidate.

The local model remains a constrained teacher rather than a chess authority. It
may select exactly one summary-eligible verified fact; it cannot invent prose in
the no-book path. The expanded layer removes a verbatim summary, and mechanical
newly opened lines such as a rook merely seeing an empty adjacent square are no
longer presented as strategic teaching points.

The final production-path benchmark used Stockfish 18,
`qwen3.8:27b-mlx`, both books, and the actual service. All six cases passed every
automated guardrail. Cold local runs took roughly 22-42 seconds when model
synthesis was needed; a repeated cached `c3` run took 10.43 seconds. The browser's
rolling estimate remains preferable to a false exact countdown. The result is
recorded as regression success, not “solved chess pedagogy”: recurring moves are
evidence for a robust follow-up, not proof of the unique reason for a move.

The design choices and detailed results are recorded in ADR 0008 and
`docs/evaluations/2026-09-09-deep-explanation-quality-cycle.md`.

### Dogfooding before adding a third book

When the next step appeared to be another source import, the learner proposed
that the agent should play the product itself. This changed the immediate
priority. A third book could increase coverage, but it could not reveal whether
the end-to-end interaction was asking Stockfish and RAG about the right
position. The planned import was therefore deferred in favor of a white game, a
black game, intentional inaccuracies, suggestions, deep questions, and undo.

The local Browser-control skill was selected because this was a local web-app
test. Its bundled runtime failed during setup: it imported `node:process`, which
the current browser-control execution environment rejects. This is external to
the Chess Coach; the frontend and API health checks remained good. The test
continued through the same FastAPI requests used by the page. Consequently the
move and explanation paths are production-path evidence, while visual
drag-and-drop and scrolling are explicitly not claimed as revalidated.

The first white game exposed a severe semantic reference bug. After the learner
played `b3` and the coach replied, “Why was `b3` inaccurate?” returned a deep,
cited explanation of `Bxc6`. Every downstream fact was legal and grounded, but
the question resolver had used the live board. Since `b3` was no longer legal
there, it silently selected a current theory suggestion. This is a distinct
truth boundary: grounding requires the correct historical position, not merely
a valid current one.

Accepted transition messages now reconstruct the position immediately before a
named past learner move. “My last move” language uses the last accepted learner
transition. The historical analysis leaves the live board and undo state
unchanged and fails closed if replay cannot prove the position. Automated tests
cover both explicit `b3` and implicit last-move questions. A separate regression
covers a legal move rejected into the correction loop: because the board has not
advanced, “my last move” must resolve to that current retry, not the last
accepted historical move.

The first corrected question then showed why dogfooding must continue past the
first bug. The coach discussed `d3` but could not state why it was sensible.
`python-chess` can prove two useful causal facts without prose generation: the
pawn on `d3` supports the pawn on `e4`, and vacating `d2` frees development
squares for the bishop on `c1`. Those facts now appear in ordinary and deep
feedback. A real repeated run made them the visible two-sentence answer while
retaining the small engine preference for `Nf3` in the comparison layer.

The Ruy Lopez suggestion had repeated the c6-knight attack in a specific
defender explanation and a generic bishop-geometry template. Specific causal
facts now suppress a redundant generic template. Sentence-level deduplication
also runs across expanded sections. Generic central-square deltas were removed
from alternative comparisons because the learner had repeatedly identified
them as technically true but strategically unhelpful. When the main line
immediately captures a moved piece, the coach suppresses temporary attacks from
that destination and explains that any benefit must lie in the resulting
position.

The final `Bb5` run uncovered a subtler citation issue. Retrieval returned a
Schliemann/Jaenisch recommendation from the same Ruy Lopez section, and its
reference appeared even though the visible synthesis used another general plan.
The broad FTS match had provenance but insufficient variation context.
Recommendations and warnings now require an exact position match; broad
opening, move, and question matches may contribute only general plans. The same
database query now returns the one general Ruy Lopez plan and omits the unrelated
Schliemann claim.

The black-side run started with coach `1.e4`, accepted theoretical `1...c5`, and
continued with `2.Nf3`. Undo removed the learner move and coach reply together,
restored Black to move after `1.e4`, and preserved the initial coach message.
The first coach move correctly introduced the opening rather than claiming to
continue one.

Deep local calls varied from roughly 28 seconds to more than one minute when the
book synthesis or critic retried. The rolling countdown remains the honest UI
choice. The completed change set passes 67 backend tests plus lint, production
build, and the rendered-shell test. ADR 0009 and
`docs/evaluations/2026-09-09-dogfooding-session.md` preserve the decision and
full observations. If source expansion follows, John Emms' *Discovering Chess
Openings* is the leading local candidate because it adds principle-oriented
teaching rather than another encyclopedic catalogue.

### Separating the publishable product from private book knowledge

When the Emms source was located, the learner raised a more fundamental
question: had local book RAG made the entire application impossible to publish?
The answer required separating software publication from content publication.
Keeping everything private would discard reusable engineering work; publishing
only the derived database would still expose searchable protected prose; and
static LLM paraphrases were not accepted as an automatic rights-clearing step.

The chosen architecture keeps the application, compiler, schemas, open opening
data, and synthetic tests in a public core. Owned PDFs, extracted chunks, and
`book_knowledge.db` are an operator-supplied private overlay. The existing Git
ignore rules already excluded every PDF and SQLite corpus, and an audit of all
84 historical paths found no leaked book or database file. The Emms PDF could
therefore remain useful locally without becoming part of a future repository.

This boundary is now executable. `CHESS_COACH_RUNTIME_PROFILE=public` installs
a null book provider even if the books flag is true and a private database is
present. The development default remains `local`, where book access is still an
explicit feature flag. Unknown profiles fail at configuration construction.

A publication gate adds defense in depth. It rejects private paths, PDF/e-book
formats, SQLite databases, and sidecars in both the Git index and historical
paths. If the local corpus is available, it creates in-memory hashes of every
24-word source sequence and scans indexed plus current tracked text. The strict
release command fails if that overlap scan cannot run. The first strict run
passed across 84 tracked and 84 historical paths and 88 tracked text variants.
This control does not decide whether a short quotation is legally justified or
whether a source was lawfully acquired, so the documented release process still
requires manual review and publication from Git rather than a zip of the local
working directory.

ADR 0010 records the options and decision; `docs/publication-safety.md` is the
operating procedure. This became a case-study example of turning a late legal
and product concern into a testable architectural boundary rather than a prose
disclaimer.

The legal check consulted the German Copyright Act provisions on protected
works, public availability, text and data mining, quotation, and private
reproduction. They informed a deliberately conservative release policy rather
than a claim that the engineering gate constitutes legal clearance.

### Importing the principle-oriented Emms source behind that boundary

The source was found in the learner's `Documents/Books/Schach` folder under a
filename ending in `(2020)`. Its own front matter states first publication in
2006. The durable private copy was therefore named `John Emms - Discovering
Chess Openings.pdf`; the compiler correctly inferred 2006 instead of preserving
the misleading filename suffix. Its SHA-256 is recorded in the public local
source registry, while the file itself remains ignored.

Visual inspection covered the contents, introduction, centre and development
lessons, the early `Bb5` explanation, a Ruy Lopez `a4` pawn break, the later Ruy
Lopez overview, and an Open Sicilian example. The source is unusually well
aligned with the product: it asks learners to reconstruct sensible theory from
centre control, development, and king safety instead of merely memorizing an
encyclopaedia.

The complete local import produced 363 pages, 795 positioned spans, four
detected sections, 160 chunks, 352 claims, 127 valid or context-resolved lines,
seven final-position anchors, 342 likely board diagrams, and 859 review issues.
The combined three-book database has 1,559 chunks and passes integrity, foreign
key, FTS, orphan, and index-plan verification.

The low anchor count is an informative negative result. This converted PDF
often places a move, explanatory prose, another move, and a diagram inside one
large text block. The current conservative parser validates complete sequences
but will not stitch isolated moves through prose. Emms already contributes to
broad concept search, but the live coach must not attach its excellent `Bb5`
prose to the exact `3.Bb5` position until that progressive sequence is proven.
The next compiler increment is therefore uniquely legal progressive annotated
move reconstruction, followed by the unchanged `d3`, `Bb5`, `Na2`, and `a4`
evaluation set. The detailed import record is in
`docs/evaluations/2026-09-09-publication-boundary-and-emms-import.md`.

The immediate three-case production-path regression explicitly selected
`qwen3.8:27b-mlx` with Stockfish 18 and the three-book database. `Bb5`, `Na2`,
and `a4` all passed every automated guardrail, and none displayed an Emms
reference. This is the intended fail-closed outcome until the source gains exact
position anchors. Cached engine data made these runs unusually fast, so their
timings were not reused for the countdown model.

### Compiling progressive annotated moves instead of guessing between prose

The next increment targeted Emms' characteristic `move -> explanation -> next
move` layout. The parser first normalizes separately typeset move numbers while
preserving source offsets. A progressive chain then starts only from a verified
nearby parent FEN, requires exact move number and color, validates every SAN with
`python-chess`, and needs at least two sequential moves. Competing equally long
legal continuations, conflicting parents, or a branch-limit hit are recorded as
ambiguity rather than resolved by preference or by an LLM.

The first pass increased Emms from seven position anchors to 110 evidence rows
covering 100 distinct positions. This was useful enough to expose its own flaw
during production dogfooding. After `1.e4 e5 2.Nf3 Nc6 3.Bb5 a6`, the `Ba4`
lookup attached an Archangel-variation naming sentence from later in a large
chunk. Legal move reconstruction had succeeded, but claim locality had not.

The repaired relation is smaller than a chunk. Claims may bind only within the
same source text block or the immediately following one; intervening numbered
moves terminate the relation unless the claim explicitly mentions the focus
move. Transitions already present inside a verified compact line are not
duplicated. If an exact progressive position has no safe claim, retrieval now
returns no book evidence instead of falling back to broad opening prose. This
turns the final `Ba4` result into an honest gap.

The conservative final Emms import contains 73 progressive half-moves, 81
position evidence rows across 76 distinct positions, 13 positioned claims,
nine normal-use claims, and 51 explicitly ambiguous chunks. The increase in
flagged lines from 445 to 529 comes partly from recognizing more separately
typeset black move fragments; recognition does not imply promotion. The final
book has 212 valid or context-resolved lines and 953 open review issues. The
combined database remains at 1,559 chunks and passes every structural check.

The key positive case is now real rather than inferred. After `3.Bb5`, retrieval
finds two legality-checked Emms claims on PDF pages 54-55: the attack on the
`c6` defender of `e5` and the conditional pin following `...d6`. The local model
may translate and combine those claims but does not decide their position.

The model/critic handoff also needed refinement. Qwen first invented an
unsupported long-term-pressure conclusion. The critic correctly identified
only that sentence, yet the all-or-nothing handler threw away four supported
sentences too. Critic indexes now remove only unsupported sentences and their
evidence links. A later run reversed the actor in the conditional pin
explanation; the critic removed that sentence while retaining the correct
book-derived defender explanation. The learner sees one German answer, not an
English verification task, and only evidence actually used by surviving text
becomes a reference.

The six fixed explanation cases pass again on the production service with
Stockfish 18 and `qwen3.8:27b-mlx`; the final two-claim `Bb5` run took 25.89
seconds in its focused run and 26.97 seconds in the final full-suite run. It
exposed Emms pages 54-55 with no warnings. A white HTTP game covered
suggestion, deep question, `...a6`, `Ba4`, and complete-turn undo. A second
black-side game began with `1.Nf3`, correctly introduced the Zukertort Opening,
accepted `...d5`, and suggested theoretical `...c5` after `2.g3`. These checks
exercise the browser's production endpoints but do not claim a fresh visual
drag-and-drop inspection.

ADR 0011 contains the binding rules. The full metrics, failed intermediate
`Ba4` result, critic behavior, and dogfooding transcript are summarized in
`docs/evaluations/2026-09-09-progressive-emms-and-dogfood.md`.

### Turning learner objections into a durable explanation-quality loop

After the third-book compiler work passed its fixed cases, the next bottleneck
was no longer missing chess infrastructure. The project had repeatedly learned
more from direct learner objections than from automated “grounded” checks, but
those objections existed only in conversation. The agreed next slice was a
low-friction feedback mechanism under every explanation in the coach feed.

The choice was deliberately a three-state scale rather than thumbs or stars.
`Hilfreich` measures whether an explanation did its job. `Unklar` says that the
answer may be defensible but did not create understanding. `Falsch` flags a
suspected factual or positional error. This distinction maps to different next
checks and directly reflects the earlier `c3` and `Na2` failures. A free-text
report is valuable but cannot be mandatory after every half-move, so the first
click saves immediately. The two negative choices open an optional note field;
a positive judgment can also be annotated.

Saving only the label would repeat the original reproducibility problem. Each
feed message now has a session-unique UUID and an explicit position FEN. The
feedback row snapshots the opening, question, UCI/SAN move, visible summary,
expanded sections, engine payload, knowledge status, source, model, and public
book-reference metadata. Questions about past moves preserve the reconstructed
historical FEN, not the live board. The record excludes retrieved book passages
and filesystem paths.

One row per message is updated if the learner changes the judgment. Feedback
survives a later chess undo: the response disappears from the active feed as
requested, while the rating remains useful evidence about content that was
actually shown. This is safe because the complete snapshot no longer depends
on the mutated session.

The `Feedback prüfen` control opens a scrollable local list of the unclear and
wrong snapshots without interrupting the active game. The review boundary is as important as capture. A learner click is evidence
about explanation quality, not a new source of chess truth. No rating changes
an engine result, book claim, prompt, or test automatically. A local endpoint
returns the review list, and an export utility writes `unclear` and `wrong`
records into the ignored `outputs/` directory as fixture candidates. Human
review must still classify the failure before a regression expectation changes.

The implementation reuses the local learner SQLite database. Browser-only
storage would make quality evidence fragile; cloud D1 would contradict the
settled offline-first, single-user boundary. The existing hosting manifest
therefore remains without a database binding. ADR 0012 records these options,
the undo semantics, and the distinction between user signal and chess truth.

The automated first check exercises rating, revision, note storage, filtered
review, the position/move/engine snapshot, feedback persistence through a later
turn undo, and summary counts. All 78 backend tests, frontend lint, and the
production build pass. A real learner play session remains the necessary next
test because no automated check can establish that the controls are pleasant
to use or that the three labels feel natural during play.

### Grounded did not yet mean relevant

The first live feedback after adding the rating controls exposed a presentation
problem and a deeper retrieval problem. One expanded answer rendered three large
cards for three passages from the same book. The claim-level references were
valuable for an audit, but repeating the title, author, and status did not help
the learner. The UI now groups by stable book ID, merges adjacent or overlapping
page ranges, retains disjoint ranges, and displays the contributing passage
count once. This is only a view aggregation; the backend and feedback snapshot
keep every source reference.

A question about why White's `c4` was useful began with a book statement about a
strategy for Black in the Dutch Defense. The statement was attributed and had
survived the synthesis critic, but it was irrelevant in two independent ways.
The stored interaction showed a Modern Defense pre-move FEN, while the broad FTS
query had combined chapters through the generic word `Defense`. The surviving
Dutch statement also explicitly described Black while the focused mover was
White.

The repair adds two gates after full-text search. The first requires the
normalized opening family in broad opening, move, and question matches; a
variation suffix is ignored and British/American `Defence` spelling is
normalized. The second inspects broad plan claims for an explicit actor. An
opponent plan cannot justify the focused side's move unless the learner asks for
that opponent's plan. An actorless broad plan is also withheld from a concrete
“why is this move good?” question unless it has exact-position evidence. This
reduces recall on imperfectly sectioned books, but no evidence is better than a
fluent wrong-side explanation. Querying the actual stored `c4` FEN against the
three-book database now returns zero claims instead of the earlier French,
Bogo-Indian, and Dutch mixture.

### Improvised notation reveals an unsafe focus fallback

In the position after `1.e4 g6 2.d4 Bg7 3.Nf3 d6 4.c4 Bg4 5.Nc3 Nc6 6.d5 Nd4`,
the learner asked why `Kf3xKd4` was not good. International notation uses `K`
for king and `N` for knight, so the string was not valid SAN. The fields still
made one intended move highly likely: the knight on `f3` can capture the knight
on `d4`. The service recognized neither the malformed description nor its
uncertainty. It silently retained the UI's highlighted suggestion and answered
about `Be3` instead.

The first proposed repair was to accept source and destination coordinates as a
robust alias. The learner corrected the product requirement: when the piece
letters contradict the board, the coach must ask what was meant. Silent repair
would hide uncertainty and miss a useful notation lesson. The chosen resolver
therefore accepts verbose coordinates only through `python-chess` legality, but
returns a confirmation prompt for conflicting designators. The proposed move is
stored with the exact FEN. A simple affirmative answer continues the original
question only if the position has not changed.

This case also exposed a priority failure in explanation composition. `Nxd4`
vacates `f3`, which had blocked the bishop on `g4` from the queen on `d1` through
`e2`. Black can immediately answer `...Bxd1`. The correct beginner explanation
does not require a long-term plan, book passage, or another model. A new narrow
board detector checks whether the focused move newly permits a legal slider
capture of a previously unattacked queen or rook and whether the vacated square
lies between attacker and target. When it fires, the causal tactical sentence
is the short answer and book retrieval plus LLM selection are skipped.

The real local production components reproduced the required conversation. The
first response asked whether the learner meant `Nxd4` and explained `K` versus
`N`. After `ja`, the coach stated that `...Bxd1` wins the queen and identified
the opened `g4-f3-e2-d1` diagonal. No book citation appeared. This is a compact
example of the project's principle becoming an ordering rule: immediate board
truth outranks engine comparison; engine comparison outranks broad strategic
interpretation; the LLM operates only after the relevant truth has been chosen.

ADR 0013 records the alternatives and boundaries. The exact incidents,
production-path outputs, and targeted regression scope are preserved in
`docs/evaluations/2026-09-09-relevance-and-tactical-priority.md`.

The final checkpoint reports 83 passing backend tests plus Ruff, frontend lint,
the rendered-page test, production build, and publication-safety scan. The scan
covered 95 tracked and historical paths and compared the public code text with
105 private-corpus variants without detecting a source leak.

### From free exploration to the first deliberate repertoire lesson

The next discussion returned to the product's central learning job. Free play
can recognize many openings and explain what happened, but it does not ensure
that one repeatable setup is learned. The learner wants both: exploratory play
and deliberate practice of a selected opening. At roughly 700 rapid Elo and
without a clock in the app, the practical target is to reach move ten with a
safe, comprehensible position rather than accumulate encyclopedic variations.

The first proposed slice was an Italian lesson from White. The Italian Game was
chosen because its early moves make the basic relationships visible: claim the
center, develop while creating a threat, castle, stabilize `e4`, and prepare
`d4`. A quiet `d3`/`c3` setup avoids making trap memorization the first lesson.
The learner selected White and authorized agent self-play for testing. When
offered a preview-versus-recall choice, the learner explicitly chose immediate
play: do not show the move first; ask for it.

That choice changes the interface contract. Guided mode opens an already active
board and immediately says “Was ist dein erster Zug?” There is no start gate and
no discovery page. Only lesson title, goal, and 1/10 progress are visible. The
answer is absent from the prompt, although the existing `Zug vorschlagen`
control remains an intentional escape hatch. This separates an involuntary
spoiler from a learner-requested hint.

Four implementation options were considered. Reusing weighted moves from the
large opening graph could drift away from the lesson. Asking Stockfish to create
the line would confuse a volatile top choice with a human repertoire. A JSON
lesson format would duplicate chess notation and future variation semantics.
The selected option is one project-authored annotated PGN, parsed and validated
with `python-chess`. It contains one main line, an explanation after every
half-move, and two custom hint annotations on every White move. No prose from
the private books is copied into the tracked file.

The first line is `1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.d3 Nf6 5.O-O d6 6.c3 O-O
7.Re1 a6 8.Bb3 Ba7 9.Nbd2 Re8 10.h3 h6`. Fixed Black replies are a deliberate
property of retrieval practice, not an attempt to model every opponent. The
free-play mode remains available for that exploration. PGN branches are deferred
until the learner has tested whether this narrow lesson actually teaches the
setup.

A legal deviation now stays off the board. The first and second deviations
produce progressively more specific hints; the third records the attempted move,
reveals and places the lesson move, and then plays the fixed coach response. The
feedback keeps two facts separate: the move did not match this lesson, and
Stockfish may still judge it perfectly playable. The existing SQLite interaction
table therefore gains `training_mode`, `lesson_id`, and `repertoire_match`
instead of overloading `theory_match`. An in-place migration preserves existing
local data.

The same separation appears in the suggestion path. In guided mode a suggestion
is explicitly labeled as the move of the training line; Stockfish data remains a
quality check. Questions about that suggestion receive the authored lesson idea
as a required verified fact. The generic book/LLM path may add only already
grounded detail, while immediate tactical facts still outrank every strategic
layer.

Undo needed one further state dimension. A turn snapshot now includes the lesson
ply, so taking back a turn removes the learner move and coach reply together and
asks the previous lesson question again. The final half-move automatically
creates a grounded summary. Unlike the older general completion state, this
final guided turn may be undone; its stored summary is deleted and the tenth
question reopens.

Stockfish checked every half-move of the authored line at 0.5 seconds and MultiPV
4. The largest measured loss was 0.16 pawns for `3.Bc4`; all other moves were at
most 0.14. A second production-service self-play used the normal shorter budget
and reported 0.22 for `Bc4`, while all other learner moves were no more than
0.04 behind. The defining Italian move is therefore a useful case-study example:
small shallow-search ranking changes must not rewrite a coherent, sound human
repertoire.

The agent then played the complete White lesson through the real production
service. The session began with the unanswered prompt, advanced through all 20
half-moves without the generic phase detector interrupting it, and completed
after `10...h6` with the expected final FEN and a persisted summary. Dedicated
tests also cover both hints, third-attempt revelation, suggestion without board
mutation, an authored answer to “Warum ist dieser Zug gut?”, SQLite truth-layer
fields, active undo, and undo after completion. ADR 0014 and the dated evaluation
record the rationale and observed outputs for the case study.

The final checkpoint reports 91 passing backend tests plus Ruff, frontend lint,
the rendered-page test, production build, publication-safety scan, and a clean
whitespace diff. The public safety scan still finds no tracked private PDF,
compiled book database, or matching long passage from the local corpus.

## 2026-09-11 — From one memorized line to opponent variation

The first guided self-play led directly to the next product objection. If Black
always plays the same Italian replies, the learner can memorize that sequence
without learning how to react when a real opponent chooses another, possibly
worse, move. The desired outcome is transfer: recognize whether the Italian
plan still applies, whether the opening family has changed, or whether a
concrete mistake should be exploited.

Three complementary exercises were agreed rather than one replacement mode.
The model line remains useful for forming a stable plan. A deviation drill
should jump directly to the critical position. A realistic opponent should
start from move one and make its selection visible only through moves on the
board. The learner is still White, plays immediately, and remains untimed.

Four implementation directions were considered. A full PGN variation tree is
the long-term expressive model but introduces transposition and accepted-move
policy before this learning hypothesis has been tested. Per-move Stockfish
selection creates variety without curriculum coherence. Artificially weakening
Stockfish to imitate 700 Elo would falsely imply known player frequencies and
could select noise. The chosen intermediate structure is a family of complete,
linear annotated PGN scenarios. One is selected per session, so the coach varies
between games while every individual path remains legal, authored, and
explainable.

The family now contains 13 scenarios. It covers switches after `1.e4` to the
Sicilian, French, and Caro-Kann; alternatives after `1.e4 e5 2.Nf3` through the
Petroff, Philidor, and Damiano; Italian branches through Two Knights,
Hungarian, Rousseau, and Blackburne-Shilling; and the slow early moves `...h6`
and `...a6`. The source explicitly explains that White cannot force an Italian
after the first three opening switches. Slow moves are answered by continuing
development rather than pretending they deserve a tactical refutation.

Scenario weights sum to 100 for inspection, but no external frequency claim is
attached to them. Network access was not used. Common sound lines receive most
of the weight; traps, dubious gambits, and mistakes remain rare. This is a
curriculum hypothesis to revise from observed learner games, not chess.org
telemetry.

The implementation adds `LessonFamily`, `DrillStartPly`, `RealisticWeight`, and
`OpponentCategory` parsing. Direct drills reconstruct the position and expose
the prior move list only as muted context. Realistic sessions conceal the
selected lesson ID, title, goal, ECO, and scenario-specific progress length. A
first implementation would have revealed every scenario after Black's first
move; a new Petroff regression showed the leak because `1...e5` is still shared
with the model line. The final rule locates each scenario's first differing ply
and reveals it only after that specific Black reply has appeared.

Session persistence gains `lesson_style`; session state gains an initial FEN
and context history. This lets historical questions replay a branch from its
real starting position. A generic next-coach helper also permits a short tactic
lesson to finish on White's move instead of fabricating another Black reply.
The browser exposes `Grundlinie`, `Abweichung üben`, and `Realistischer Gegner`;
the last is the guided default. Branch prefixes appear in a subdued move strip.

The first Stockfish audit was both verification and design feedback. Across 44
initial learner decisions, no proposed move lost more than 0.34 pawns, but the
Hungarian line had a conceptual mismatch: its goal promised more central space
while `5.O-O` delayed the available `5.d5`. The line was revised to end on
`5.d5`. A second Stockfish 18 run over 43 final learner decisions measured a
maximum loss of 0.27; established scenarios stayed within 0.10 and solid ones
within 0.05. This was not blind top-move optimization: the engine prompted a
change because its concrete candidate agreed with the authored teaching goal.

The agent then selected and played every scenario through the real service with
the real local opening data and Stockfish. All 13 sessions completed, all 132
half-moves matched independent PGN reconstruction, and every interaction was
accepted and persisted. A further 60 random branch sessions all started in a
legal White-to-move position with a clean current history. Automated tests cover
hidden selection, delayed reveal, branch suggestions, custom-FEN historical
questions, White-move completion, and undo. The remaining evidence must come
from the learner: whether the uncertainty feels realistic, which deviations
actually recur, and where objectively sound alternatives deserve explicit
acceptance.

The final implementation checkpoint reports 98 passing backend tests, Ruff,
frontend lint, the vinext production build, the rendered web-shell contract,
and a clean whitespace diff. The release publication guard checks 104 tracked
paths and 102 historical paths against 104 private-corpus text variants and
finds no private source leak.

## 2026-09-12 — Variation must respect prerequisites

The learner's first session with the varied opponent exposed the most important
limitation faster than further agent self-play could. Black selected `1...c5`.
The coach accurately named the Sicilian Defense and said that Italian was no
longer possible, but the learner had no Sicilian repertoire yet. The answer was
factually correct and still failed the learning job.

The initial design had combined two different kinds of transfer. Varying after
the Italian position tests whether its plans are understood. Varying on move one
tests whether White knows a repertoire against several defenses to `1.e4`.
Calling both “Italienisch üben” hid a prerequisite problem behind breadth.

Three repairs were considered before changing the code. Keeping the behavior
with a better explanation still asks an unprepared question. Merely lowering
the weights makes the broken promise rarer rather than correct. Deleting the
lessons throws away useful authored and verified material. The selected repair
makes `LessonFamily` an enforceable curriculum boundary.

The active `italian-white` family now contains seven scenarios, all sharing
`1.e4 e5 2.Nf3 Nc6 3.Bc4`. The coach may then play `3...Bc5`, `3...Nf6`,
`3...Be7`, `3...f5`, or `3...Nd4`, with two later slow-move scenarios after the
classical reply. Their pedagogical weights are renormalized to total 100. Both
direct deviation practice and the hidden realistic opponent draw only from this
family.

The six earlier switches remain in the same PGN but move to
`e4-white-foundations` with zero selection weight: Sicilian, French, Caro-Kann,
Petroff, Philidor, and Damiano. They are intended for a later, separately named
course whose introduction supplies the missing plans. Attempting to select them
through the Italian API now fails closed rather than relying on the UI to hide
them.

The correction also tightens the hidden-answer contract. A test of the direct
Two Knights drill found that the question did not show `d3`, but the lesson goal
did. The goal was rewritten around the purpose—secure `e4` and continue calm
development—without spelling out the move. This is another example of why the
whole learner-visible payload, not one sentence, must be checked for leakage.

No chess line changed, so the preceding Stockfish audit remains valid. The
change is instead an evidence-based curriculum correction: less breadth now
creates a more honest and usable learning step. ADR 0016 and the dated
acceptance note preserve the triggering quote, rejected options, new boundary,
and regression expectations.

The corrected real-service acceptance run played all seven active lessons to
completion with Stockfish 18. All 80 half-moves were accepted and persisted,
and all seven shared the required five-ply Italian prefix. One hundred hidden
realistic selections and 60 random branch starts stayed inside the active
Italian family; all branch contexts began after Black's third move or later.
The six future `1.e4` foundation lessons still loaded but were never selected.
The final checkpoint reports 99 passing backend tests, Ruff, frontend lint, the
vinext production build, the rendered-shell contract, and a clean whitespace
diff. The release publication guard checked 104 tracked and 104 historical paths
against 111 private-corpus text variants without finding a leak.

## 2026-09-12 — Public remote and an explicit license boundary

The learner created the public GitHub repository
`https://github.com/scmstorz/chess-opening-coach` and requested a simple,
permissive license. The remote was confirmed empty before being configured as
`origin`; this avoids silently overwriting or merging an independently
initialized public history.

Leaving the repository unlicensed, applying GPL-3.0-or-later to all original
work, and licensing the original work under MIT with explicit third-party
notices were compared. No license was rejected because public visibility by
itself does not grant open-source reuse rights. GPL would align directly with
the GPL-3.0-or-later `python-chess` dependency, but would not meet the learner's
preference for a simple permissive grant on independently reusable project
code. MIT was selected because it is concise and GPL-compatible.

The distinction must remain visible: MIT covers the original project code and
authored repository material, not every component of a running installation.
`python-chess` remains GPL-3.0-or-later, separately installed Stockfish remains
GPLv3, and the included Lichess opening data remains CC0. A combined
redistribution can therefore carry obligations beyond the project's MIT text.
`THIRD_PARTY_NOTICES.md` records those boundaries, and both Python and npm
metadata now identify the original project license and public repository.

The license change does not weaken the private-content boundary. The three
owned PDFs, extracted book passages, compiled knowledge database, and learner
database remain ignored local files outside the MIT grant. Public runtime still
fails closed without book retrieval, and publication still requires both the
release guard and human review. ADR 0017 preserves the options, reasoning, and
consequences for the case study.

Before the first public push, the complete backend and frontend checks passed:
99 Python tests, Ruff, frontend lint, the production build, and the rendered
shell contract. After all new license files were staged, the stricter release
guard inspected 109 indexed paths and all 106 historical paths, then compared
the public text with 109 private-corpus variants without finding a leak. The
check was deliberately repeated after staging because the guard treats the Git
index—not untracked working files—as the proposed public artifact.

## 2026-09-12 — Making the public clone genuinely startable

The first public README already named prerequisites, four installation commands,
and `npm run coach`. The learner's simple question—whether somebody else could
run it—exposed that this was a developer reminder rather than complete
onboarding. It began after cloning, assumed macOS, recommended only the owner's
18 GB Ollama model, and described missing services as “usable” without defining
the resulting product.

The setup path was rewritten from the perspective of a clean machine. Apple
Silicon/macOS retains `qwen3.8:27b-mlx` as the production-tested quality option.
The approximately 2.5 GB `qwen3:4b` model is now the explicit low-resource
choice, with the documented trade-off that its German prose was weaker in the
small local benchmark. Because chess truth is not delegated to the model, this
changes explanation selection quality rather than legality or engine truth.

Linux receives a separate Ubuntu/Debian path and explicit Node, uv, Ollama, and
Stockfish guidance. Native Windows was not silently claimed: the current
launcher has been exercised on POSIX systems, so Windows is documented through
WSL 2 until a native acceptance run exists. The stable URL remains the same on
the Windows host.

A capability matrix now states what happens without private books, Ollama,
Stockfish, or both local services. Troubleshooting covers version checks, venv
setup, the Ollama process and model, explicit Stockfish paths, occupied ports,
and the health endpoint. Inspection of the launcher confirmed that it
re-executes the `.venv` Python automatically after `uv sync`, so macOS/Linux
users do not need a separate activation step.

Two automated README contracts preserve the public clone command, dependency
installation, start command, stable URL, platform boundary, small-model option,
degraded modes, and troubleshooting section. The dated onboarding audit records
the trigger, gaps, decisions, and remaining native-Windows limitation for the
case study.

The acceptance run exported the complete staged Git index to a new temporary
directory rather than testing the owner's working tree. Only the explanatory
README remained below `data/books/`; no PDF or local database was present. Both
Python and JavaScript dependencies installed into new local directories using
only the existing offline caches. The README contracts and production frontend
build passed in that export.

Finally, the exported application started through the documented `npm run
coach` command in the fail-closed `public` profile. Its health response reported
3,810 open opening records, Stockfish, the 2.5 GB `qwen3:4b` option, and zero book
sources with private knowledge explicitly disabled. The complete development
checkpoint now contains 101 passing backend tests, Ruff, frontend lint, the
production build, rendered-shell test, clean diff, and the strict publication
scan.

## 2026-09-12 — A scenario ending is not an opening ending

The learner reported that “Realistischer Gegner” repeatedly announced success
too early while Black appeared to play ordinary Italian moves. The persisted
interaction history made the report reproducible: the selected line was the Two
Knights scenario `1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.d3 Bc5 5.O-O d6 6.c3`. Its move
order transposes toward the familiar setup, but its authored PGN stops after 11
plies while the model line contains 20. The service used PGN exhaustion as its
only completion condition and therefore locked a still-useful opening position.

Four responses were considered. Keeping the short ending would preserve a
simple state machine but fail the product promise. Padding every PGN would add
authoring without repairing the concept. Splicing the model suffix onto every
branch would assume invalid transpositions. The selected design separates the
end of authored guidance from the end of the opening and game.

In realistic mode, the boundary is now an `Etappenziel`. The progress counter
ends, the board remains active, and both sides continue through the ordinary
theory/Stockfish policy. The opening-phase heuristic is held until at least the
20-ply model-line horizon, after which its existing evidence-based, learner-
controlled decision can appear. Direct model repetition and branch drills stay
finite because their product promise is specifically to complete that line.

This change also exposed a less visible state invariant: undo crosses a policy
boundary, not merely a board transition. `guided_segment_complete` is therefore
stored in every turn snapshot. Undoing `6.c3` removes White's move, the free
Black reply, and the milestone, then restores the final authored question. ADR
0018 records the rejected options and the dated regression note preserves the
real sequence and acceptance criteria for the case study.

The first implementation checkpoint contains three new state-machine
regressions: exact short-line continuation, undo across the policy boundary, and
full realistic model-line transition. A production-service replay with the
3,810-line opening graph and Stockfish 18 continued the reported sequence with
the legal `6...h6`, kept the board active for White, and emitted no success
claim. The complete suite passed 104 backend tests, Ruff, frontend lint, the
production build, the rendered-shell contract, and the whitespace check. The
staged public-release guard checked 113 paths and 111 historical paths against
113 private-corpus text variants without finding a leak.

## 2026-09-12 — A countdown should estimate the wait, not the average task

While continuing the live test, the learner reported that the coach-move
countdown was consistently too low. Inspection found that the browser did learn
durations, but its single `move` exponential average combined very fast authored
lesson replies with much slower free replies. The latter can invoke Ollama once
for the learner move and again for the coach move. Recent work on realistic
continuation made this distinction especially visible: the UI changed policies,
but its timing model did not.

Merely raising the 18-second default would not repair an already stored low
average. A global multiplier would still mix incompatible workloads. An exact
backend prediction was rejected for now because model cold starts, retries,
caches, and machine load are not reliably knowable before the request. The
selected client-only design separates `move-guided` and `move-adaptive` timing
histories.

Scripted moves start at four seconds. The initial adaptive estimate was set to a
conservative 45 seconds, then reduced to 30 seconds after immediate learner
feedback that the starting wait felt too long. Slower real measurements raise it
automatically. The final move of a realistic script already uses the adaptive
profile because its request may also generate the first free reply. Instead of
estimating the mean, each profile keeps eight measurements and uses their 80th
percentile with a 20-percent and two-second margin. New versioned storage keys
discard the misleading pooled history while keeping all timing data on the
device.

ADR 0019 preserves the options and formula. Frontend lint, the production build,
the rendered-shell test, and whitespace validation pass. The backend process and
its in-memory sessions were not restarted. The frontend development server did,
however, reload the page module and created a new visible browser session; this
is a development-time interruption worth avoiding during future live-play fixes.
The staged public-release guard checked 114 paths and 113 historical paths
against 114 private-corpus text variants without finding a leak.
After lowering the initial adaptive estimate to 30 seconds, the follow-up guard
checked the same 114 staged paths plus 114 historical paths and again found no
private-corpus overlap.
