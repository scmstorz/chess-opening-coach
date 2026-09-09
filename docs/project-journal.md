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
