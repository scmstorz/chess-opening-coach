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

- Inspect active listeners before local integration work.
- Select or request an actually free loopback port at startup.
- Display the exact local URL clearly.
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

An early preview used free port 4173 and the API used 8765. The finished launcher
does not hard-code either port: it asks the operating system for two available
loopback ports and prints the browser URL. A real launcher test selected backend
port 49625 and frontend port 49626 and reached both successfully.

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

### First-slice verification evidence

At the time of this journal entry:

- Python tests: 9 passed, including a conditional real Stockfish adapter test
  and grounding-regression tests.
- Python lint: clean after formatting and import correction.
- Web lint: clean.
- Vinext production build: successful.
- Initial rendered route: HTTP 200.
- Dynamic launcher: successful on automatically selected ports.
- Local health: 3,810 opening entries, Stockfish available, Ollama available.
- Live sound move: accepted, identified, evaluated, explained, followed by a
  verified coach response.
- Live mistake: board rollback and first correction hint confirmed.

One third-party warning remains in Python tests: Starlette reports that its
current `httpx`-based `TestClient` compatibility path is deprecated in favor of
the future `httpx2` package. It does not fail the tests and is outside application
code.
