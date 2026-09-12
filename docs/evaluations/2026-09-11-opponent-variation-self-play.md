# Opponent variation: engine audit and self-play

- Date: 2026-09-11
- Engine: Stockfish 18
- Product level: Italian-from-White curriculum for an approximately 700 rapid
  learner, without a clock

## Question under test

Does the guided lesson still teach transferable opening decisions when Black
does not cooperate with one fixed Italian main line?

The answer is divided into three modes rather than forcing one mode to do all
jobs: repeat the model line, drill one deviation from its decision point, or
start at move one against a hidden selected scenario.

## Curated scenario set

| Scenario | First relevant Black choice | Category | Selection weight |
|---|---:|---:|---:|
| Quiet Italian model line | `1...e5` and continued main line | established | 24 |
| Sicilian switch | `1...c5` | established | 14 |
| French switch | `1...e6` | established | 8 |
| Caro-Kann switch | `1...c6` | established | 8 |
| Petroff | `2...Nf6` | established | 10 |
| Philidor | `2...d6` | solid | 8 |
| Damiano | `2...f6` | mistake | 1 |
| Two Knights | `3...Nf6` | established | 18 |
| Hungarian | `3...Be7` | solid | 3 |
| Rousseau | `3...f5` | dubious | 2 |
| Blackburne-Shilling | `3...Nd4` | trap | 2 |
| Early `...h6` | `4...h6` | slow | 1 |
| Early `...a6` | `4...a6` | slow | 1 |

The weights deliberately total 100, but are an internal curriculum choice. No
claim is made that they reproduce game frequencies at 700 Elo. Network access
was not used. The set combines common sound defenses with a few instructive
offbeat decisions and rare mistakes.

## Engine audit

Every White move from each scenario's `DrillStartPly` was compared with
Stockfish's candidate under a 0.35-second search capped at depth 20. The audit
covered 43 learner decisions.

- Maximum measured loss across the complete set: 0.27 pawns.
- Established scenarios: maximum 0.10.
- Solid scenarios: maximum 0.05 after revision.
- Slow scenarios: maximum 0.10.
- Trap scenario: maximum 0.06.
- The rare Damiano tactic and dubious Rousseau line varied more at shallow
  budgets, but their taught responses remained below 0.30.

The first Hungarian draft produced the audit's useful failure. It taught
`4.d4 d6 5.O-O` while its own goal claimed that White should exploit Black's
passivity in the centre. Stockfish consistently highlighted `5.d5`; the line
was shortened to finish with that thematic advance. A repeat audit reduced the
solid-category maximum from 0.34 to 0.05. The change was made because engine
evidence agreed with the stated lesson concept, not merely because one move was
ranked first.

## Production-service self-play

This section records the completion semantics used at the time of the original
run. ADR 0018 later changed realistic sessions so an exhausted authored scenario
continues as free opening play; direct model and branch drills remain finite.

A real `CoachService` instance used the local 3,810-line opening book, the
normal 0.12-second move-analysis budget, Stockfish 18, in-memory SQLite, and the
actual annotated PGN loader. The agent explicitly selected each scenario in the
realistic style and supplied every expected White move.

Observed result:

- all 13 scenarios reached `complete`;
- all 132 authored half-moves were legal, accepted, explained, and persisted;
- each final FEN matched independent reconstruction from the PGN;
- lines ending on White's move completed without an invented Black reply;
- the hidden scenario stayed unnamed through shared prefix moves and was
  revealed only after the first differing Black move;
- 60 additional random branch sessions all started from a reconstructed legal
  White-to-move position with empty current-session history and visible context.

Unit tests additionally cover a direct Sicilian drill, delayed Petroff reveal,
weighted selection reaching at least ten distinct scenarios, suggestion at a
branch start, historical questions from a non-initial FEN, persistence of the
style, completion on White's move, and undo from that completion.

The final repository checkpoint passed 98 backend tests, Ruff, frontend lint,
the production build, the rendered web-shell test, and the release publication
guard. The latter compared 104 tracked paths and 102 historical paths against
104 local private-corpus text variants without finding a leak.

## What this evidence does not prove

The engine audit establishes legal and objective plausibility, not that the
chosen line is the easiest explanation for this learner. The weights are not
empirical opponent frequencies. The service self-play does not test mouse
interaction or visual comprehension. Most importantly, a finite scenario
library cannot cover every poor move a human opponent may play. Real learner
sessions should determine which additional branches, accepted alternatives, or
transpositions deserve authored support next.
