# Chess Opening Coach — handoff for the next session

Snapshot: **2026-09-16, Europe/Berlin**. This is a navigation and decision
record, not a substitute for the detailed journal and architecture documents.
Start a new session by reading this file, then inspect the actual Git status and
runtime health: processes, model availability, and learner data can change while
the conversation is closed.

## Update: 2026-10-02 — Caro-Kann with White and local alias repair

The learner approved **Caro-Kann mit Weiß** as the fourth guided course. Three
new B12 Advance lessons teach `1.e4 c6 2.d4 d5 3.e5` against `3...Bf5`,
`3...c5`, and `3...e6`. Each contains five White decisions, a final scripted
Black move, and then free opening play. The old inactive Classical Caro-Kann
sketch was removed from the Italian PGN. Selection boundaries, suggestions,
continuation, and undo are covered by tests. See [ADR 0026](docs/decisions/0026-introduce-caro-kann-advance-course.md)
and the [evaluation](docs/evaluations/2026-10-02-caro-kann-white-course.md).
The complete backend suite, Ruff, frontend lint, production build, rendered
shell, short Stockfish audit, and isolated real-engine replays passed. After
explicit approval to discard the current in-memory game, the live starter was
restarted. Backend, frontend, and `schach.localhost` returned HTTP 200, and a
fresh API session accepted `caro-kann-white-bf5` with the expected five-move
progress and Caro-Kann prompt.

Earlier in the same session, `schach.localhost` returned 502 because vinext
ignored `--host` and bound its default `localhost` to IPv6 while nginx proxied
to IPv4. `scripts/start_local.py` now uses vinext's actual `--hostname`
argument with `127.0.0.1`; its regression test passes, and the alias returned
HTTP 200 after restart. The launcher repair and the Caro-Kann course belong to
the same delivery.

## Update: 2026-10-02 — repetition draws

The learner reported that a repeated queen/king cycle did not end the game.
The latest SQLite interaction history confirmed four equivalent positions had
each occurred three times with the same player and move rights. The cause was
the default `python-chess` `is_game_over()` behavior: claimable threefold
repetition is excluded unless explicitly requested. The implemented fix offers
**Remis beanspruchen** to the learner at an actually repeated current
position, records the claimed `1/2-1/2` result, and ends fivefold repetition
automatically. Turn snapshots preserve the board's move stack so undo does not
erase repetition evidence. See [ADR 0025](docs/decisions/0025-handle-repetition-draw-claims.md)
and the [evaluation](docs/evaluations/2026-10-02-repetition-draws.md). Backend,
API, build, rendered-page, lint, Ruff, publication, and the full 121-test
backend suite passed. After the learner explicitly approved discarding the
in-memory game, the main local starter restarted on `53686`/`53687`. The live
OpenAPI document contains the draw-claim route, a fresh session exposes
`game_end` and `draw_claim`, an invalid early claim returns 409, and the served
frontend contains the new claim action.

## Update: 2026-09-26 — French with White

The learner asked for more breadth and approved **Französisch mit Weiß** as a
third guided course. Three named C02 Advance lessons now teach
`1.e4 e6 2.d4 d5 3.e5 c5 4.c3` against `4...Nc6`, `4...Qb6`, and `4...cxd4`.
The former inactive Classical French sketch was removed from the Italian PGN.
Each prepared line ends after the fifth Black move and continues as free
opening play with White to move. The course has a visible introduction and
never enters Italian realistic selection. Four foundations sketches remain
inactive. See [ADR 0024](docs/decisions/0024-introduce-french-advance-course.md),
the [evaluation](docs/evaluations/2026-09-26-french-white-course.md), and the
latest journal entry. The work was published in commit `5615881`. The local
starter was restarted and a fresh API session accepted `french-white-nc6`;
check Git status and runtime health before taking further action.

## Update: 2026-09-26

The learner approved the first new guided opening course: **Sizilianisch mit
Weiß**. This update adds a separately named course with an
introduction and three finite exercises against `2...d6`, `2...Nc6`, and
`2...e6`. After each taught segment, the session continues with a free coach
reply and further play; an initial premature completion was repaired in the
same work session. The `...d6` sketch was moved out of the Italian PGN and
reviewed; the other two lines were authored and Stockfish checked. Italian
realistic selection still stays inside Italian positions; at that point five `1.e4`
foundations sketches remained inactive. See [ADR 0021](docs/decisions/0021-introduce-sicilian-white-course.md),
the [evaluation](docs/evaluations/2026-09-26-sicilian-white-course.md),
[ADR 0022](docs/decisions/0022-continue-after-sicilian-teaching-line.md), and the
latest journal entry. The original 2026-09-16 Git and runtime details below
are historical snapshots; check them again before continuing.

The course selector now labels Italian choices as exercise types and Sicilian
choices as Black's second move, after a learner screenshot exposed the ambiguity.

The learner also reported slow “Coach prüft den Zug” feedback after playing a
suggested move in the `...e6` line. ADR 0023 documents a local code change:
free continuation after a guided segment now returns verified automatic move
feedback without waiting for Ollama paraphrasing; explicit questions still use
the tutor. The frontend has a separate short progress estimate for that path.
The learner explicitly approved discarding the in-memory game. The local
starter was restarted; backend health and the browser both responded.

## One-minute orientation

The project is a **local-first, single-user browser chess coach** for a learner
of approximately 700 online Elo who usually plays 10-minute rapid games. The
goal is to understand opening ideas and survive the first moves, not memorize a
single master line. The current browser UI is German; moves use international
SAN/PGN notation such as `Nf3` and `Bb5`. Training is untimed for now.

Core rule: **keep chess truth outside the LLM**. `python-chess` checks rules,
the local opening graph or authored lesson defines opening/repertoire context,
Stockfish evaluates moves, SQLite persists learner evidence, and Ollama may
select or reword only verified explanation material. Book claims have their own
provenance and verification limits. Legality, repertoire/theory membership,
and objective engine quality must never collapse into one “right/wrong” label.

The public repository is `https://github.com/scmstorz/chess-opening-coach`.
Before writing this handoff, the working branch was `main`, clean and aligned
with `origin/main`. The latest **application-code** commit was **`b325365`**.
The last two application changes are:

1. `1898d76 Preserve explicit move comparisons`
2. `b325365 Avoid redundant tutor work for castling comparisons`

The code and original repository material use MIT, with separately documented
third-party licenses. The public Git repository does **not** contain the owned
chess-book PDFs, extracted passages, the derived knowledge database, or the
learner database. Never publish a raw copy of this working directory.

## What the product currently does

- The chessboard is playable immediately in the browser. Moves work by drag
  and drop or clicking squares; pieces and coach moves are visually legible and
  animated. White, Black, and random learner colors are available in free play.
- Free play recognizes many common openings from 3,810 local Lichess CC0
  opening entries. It offers theory-aware, Stockfish-checked coach replies,
  explains both sides' moves, and continues with Stockfish when local opening
  theory runs out. A non-playing **Zug vorschlagen** hint works after the
  opening too.
- Guided Italian practice for White has one authored model line plus six
  active deviations. Modes are model-line repetition, a direct deviation drill,
  and a realistic hidden opponent line. All active scenarios stay inside the
  Italian family until after `1.e4 e5 2.Nf3 Nc6 3.Bc4`.
- A separate guided Sicilian course for White teaches one central plan through
  three named lines. A French course teaches the Advance pawn chain through
  three named lines. A Caro-Kann course teaches its Advance through three more
  named lines. Three further annotated `1.e4` response scenarios (Petroff,
  Philidor, Damiano) remain **inactive** and must not leak into
  “Italienisch üben”.
- The correction loop normally gives a strategic hint, then a more concrete
  hint, then reveals the answer on the third unsuccessful attempt. It is for
  materially bad moves, not sound moves merely absent from the training line.
  Full-turn undo removes the learner move **and** the coach reply.
- The right-hand feed has compact summaries and expandable detailed sections.
  Free questions about current or past positions can compare named moves.
  **Tief erklären** checks candidate lines and multiple plausible opponent
  replies. An honest evidence limit is better than a fluent invented plan.
- Stockfish scores are visible from White's perspective: `+` favors White and
  `-` favors Black, regardless of learner color. The current move-correction
  threshold is 0.75 pawn; small evaluation gaps are not treated as major
  human errors.
- A probable end of the opening is detected using several signals. The learner
  chooses whether to continue into the middlegame or create an opening review.
  Recommendations to repeat a weak area may be remembered, but must never
  automatically start or switch exercises.
- Explanations can be rated **Hilfreich**, **Unklar**, or **Falsch**. Ratings
  and optional notes are stored with position, answer, engine, and source
  context. They become human-reviewed fixture candidates, not automatically
  accepted chess judgments.
- A local book compiler/retriever supports three privately owned books. It
  stores page/claim provenance, quarantines unsafe extraction, and may pass
  short relevant extracts to local Ollama automatically. The UI presents one
  grounded German answer and compact source metadata, not an extra passage the
  learner must verify by reading twice.

The authoritative feature list and installation instructions are in
[`README.md`](README.md); the component boundaries are in
[`docs/architecture.md`](docs/architecture.md).

## Important product decisions and preferences

- The user explicitly wants a **question–answer dialogue for major product
  decisions**. The project once scaffolded too early; that was reversed and
  recorded. Implement approved, bounded increments, not a speculative feature
  explosion.
- The tone should be friendly and encouraging, without patronizing praise.
  Explanations should teach *what a move accomplishes and why*, preferably a
  concrete cause-and-effect chain, not generic square lists, repetition of the
  summary, or “Stockfish likes it”.
- The user wants to ask immediately after any move, including a highlighted
  suggestion, and to receive useful feedback after every coach move too.
- The experience is **offline-first**, not forbidden from all network use.
  Future external requests/data refreshes require an explicit, contextual ask
  and must not silently interrupt training. Cloud chess models were benchmarked
  by specific authorization but are **not** in the active runtime.
- The user wants all decisions, rejected options, failed experiments, tests,
  and lessons learned preserved for a future case study. Add a dated journal
  entry and, for material architectural choices, an ADR and reproducible
  evaluation. Keep public documentation free of private book passages and API
  credentials.
- The learner's current interest is primarily White practice. Timed 10+0
  training, PGN export, resumable sessions, and automatic spaced repetition are
  not implemented. An abandoned live board need not be resumable; retained
  learning history is a separate concern.

## Most recent issue and its resolution

Immediately before this handoff, the user showed an explanation of
`11.O-O-O` that answered “Why was long castling better than short castling?”
by comparing long castling with `h4` and saying merely that castling protects
the king and connects rooks. This was a **relevance failure despite true
facts**: the named alternative `O-O` had vanished.

The reconstructed pre-move position was:

```text
rnb1k2r/1pqp1pp1/p3pn1p/2b5/2PNP1P1/1QN1B3/PP2BP1P/R3K2R w KQkq - 0 11
```

The key sequence ends `10.g4 h6 11.O-O-O`. White's g-pawn is already on
`g4`. Stockfish's short-castling continuation begins `O-O h5`: Black attacks
that pawn and can open lines beside a king on `g1`. Black's queen on `c7`
already attacks `h2`. Long castling puts White's king on `c1`, away from this
kingside lever; White can use `h4` as a follow-up. Both castlings connect the
rooks, so that property is **not** the deciding explanation.

The repair in [`backend/chess_coach/service.py`](backend/chess_coach/service.py)
resolves natural German castling names (including elliptical “die kleine”)
through legal moves, forces explicitly mentioned A/B moves into a common
depth-24 Stockfish comparison, prioritizes both in the displayed engine lines,
and creates a narrow board/PV-derived castling explanation. When that answer is
complete, it bypasses both broad book retrieval and Ollama selection. A real
`qwen3.8:27b-mlx` check selected the same correct summary but cost roughly
45 extra seconds; the final deterministic path answered in approximately
10 seconds. It does not claim long castling is generally superior.

Tests include a fixture for the exact FEN/question and a historical replay
after the coach reply. See
[`ADR 0020`](docs/decisions/0020-explicit-move-comparisons.md) and the
[`dated evaluation`](docs/evaluations/2026-09-13-explicit-castling-comparison.md).
The full backend suite passed **107 tests** at the last code checkpoint; Ruff
and the public/private publication gate also passed. The two commits above
were pushed. Do not assume those numbers are still current after future edits.

## Current local runtime snapshot — volatile

At the 2026-09-16 inspection, the fixed browser URL responded at
`http://localhost:53687/`; the API is on `127.0.0.1:53686`. Health reported
`runtime_profile=local`, Stockfish installed at `/opt/homebrew/bin/stockfish`,
3,810 opening entries, and three local books (1,559 retrieval chunks). **Ollama
was not reachable at that moment** (`Connection refused`); the coach can still
give deterministic and Stockfish-backed feedback, but model-backed wording or
book synthesis is reduced until Ollama runs again. This is not evidence of a
new application bug. The model normally selected by the adapter, when Ollama
is available, is `qwen3.8:27b-mlx`.

Do not assume the process or current in-memory board survives closing the
notebook. Sessions are intentionally not resumable after a server restart.
Persistent learning records live in the ignored local `data/coach.db`; private
book knowledge lives in ignored `data/book_knowledge.db`. No account or cloud
sync is involved.

To resume, check the URL and health first. If the app is not running, use
`npm run coach` from this directory; the launcher deliberately fails when its
fixed ports are occupied instead of silently choosing a new URL. If only the
LLM is unavailable, start the local Ollama service and verify the installed
model before investigating the coach. Do not kill an occupied port blindly;
identify its process first. See README troubleshooting for platform details.

## What is *not* decided or finished

The learner has now chosen Sicilian, French, and Caro-Kann courses for White. A
first guided course for Black was recommended next but has not been approved.
Expansion to nearby `1...e5` responses is also undecided. Each inactive sketch
needs didactic and Stockfish review before activation. Hidden mixed-opponent
practice requires explicit prior teaching and remains locked. A fourth broad
book still lacks evidence of a current retrieval bottleneck. The next
conversation can playtest the Caro-Kann course, choose the first Black course,
or address a newly observed issue.

Other known limits and deferred work:

- Opening-graph edge weights represent dataset coverage, **not** empirical
  frequency at 700 Elo. Realistic opponent selection uses pedagogical weights.
- Strategic “why” explanations remain a quality challenge. Stockfish gives
  evaluations and candidate lines, not authoritative prose about purpose;
  models and books can also produce irrelevant or unsupported interpretations.
  Keep turning real learner objections into position-level regressions.
- The first-stage learner model is simpler than the original vision: there is
  no automatic review scheduler or concept-misconception detector yet.
- Windows support is via WSL 2, not a tested native launcher. No timer, voice
  interface, multiplayer, opening-database refresh, or cloud production tutor.

## Where to work next

| Concern | Primary files |
| --- | --- |
| Browser board, feed, timers, guided controls | `app/page.tsx`, `app/globals.css` |
| API/startup/settings | `backend/chess_coach/api.py`, `config.py`, `scripts/start_local.py` |
| Chess flow, questions, explanations | `backend/chess_coach/service.py` |
| Opening identity/theory | `backend/chess_coach/openings.py`, `data/openings/` |
| Guided lesson parsing and selection | `backend/chess_coach/guided.py`, `data/repertoires/` |
| Engine comparison/cache | `backend/chess_coach/engine.py`, `storage.py` |
| Local model and book grounding | `backend/chess_coach/tutor.py`, `book_knowledge/` |
| Regression cases | `backend/tests/`, `benchmarks/fixtures/explanation_quality_cases.json` |
| Publication boundary | `docs/publication-safety.md`, `scripts/check_publication_safety.py` |

The 122-kB chronological [`project journal`](docs/project-journal.md) is the
full process record. [`case-study-outline.md`](docs/case-study-outline.md)
collects the narrative arc; numbered decisions are in `docs/decisions/` and
reproducible findings in `docs/evaluations/`. The journal's final two dated
sections cover the proposed content priority and the castling repair.

Before another public commit or push, run appropriate tests and the strict
publication guard while the local private corpus is present:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check backend benchmarks scripts
npm run check:publication:release
git diff --check
```

For browser changes also run `npm run lint` and `npm test`. Inspect the Git
diff and status, and never stage a PDF, private knowledge database, learner
database, API key, or verbatim book passage. Publishing should use Git, not a
zip of the workspace. There is no need to deploy the Sites configuration for
ordinary local development; the documented public deployment boundary still
applies if hosting is proposed later.
