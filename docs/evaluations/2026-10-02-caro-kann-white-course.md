# Caro-Kann-from-White course: content and continuation audit

- Date: 2026-10-02
- Learner context: approximately 700 rapid Elo, untimed guided practice
- Engine: local Stockfish, 0.35 seconds per unrestricted and forced-root
  search, two threads and 64 MB hash

## Question

Can a compact Caro-Kann course teach a repeatable response to `1...c6`, explain
the point of the Advance, and expose three recognizably different Black plans
without leaking those lessons into Italian practice?

## Authored scope

Three new B12 lessons start at move one and share
`1.e4 c6 2.d4 d5 3.e5`. Against `3...Bf5`, White plays `Nf3` and `Be2` to
develop and prepare castling. Against the immediate `3...c5`, White exchanges
on c5 and plays `Nf3`; the explanation explicitly says the temporary extra pawn
is not meant to be defended with more pawn moves. Against `3...e6`, White plays
`Nf3` and answers the later `...c5` with `c3` to support d4.

The former inactive Classical Caro-Kann sketch was removed from the Italian
PGN. The loader checks legal replay, nonempty explanations for both colors, and
exactly two hints for every learner move. Every line ends after Black's fifth
move, with White to move in free opening play.

## Engine check

Reproduce with:

```bash
.venv/bin/python benchmarks/audit_sicilian_lessons.py \
  --pgn data/repertoires/caro-kann-white.pgn \
  --engine /opt/homebrew/bin/stockfish --seconds 0.35
```

Recorded maximum evaluation loss per authored move:

| Black's third move | White maximum | Black maximum |
| --- | ---: | ---: |
| `...Bf5` | 0.09 pawn | 0.01 pawn |
| `...c5` | 0.13 pawn | 0.16 pawn |
| `...e6` | 0.01 pawn | 0.37 pawn |

The short searches support plausibility rather than uniqueness or frequency.
The higher Black loss in the `...e6` exercise matches its teaching role as a
passive but playable reply that a developing learner may encounter.

## Product checks

Service tests select all three named lines, request every repertoire suggestion,
play through the milestone, and continue for a free learner and coach move
without invoking the tutor. Undo restores the fifth learner decision. Selection
tests reject realistic-style access, and the rendered page test requires the
Caro-Kann course control.

The complete 127-test backend suite passed. Ruff, frontend lint, the production
build, the rendered-shell test, and `git diff --check` also passed. An isolated
replay with real Stockfish and the full local opening graph reached all three
milestones. The first free suggestions were `Be3`, `c3`, and `Bd3`; the coach
answered with legal moves `...Qb6`, `...f6`, and `...Qc7`. All three sessions
remained in the opening phase. The replay used an in-memory database, so it did
not add test games to the learner's history.

After explicit approval to discard the current in-memory game, the local
starter was restarted. The backend, direct frontend, and `schach.localhost`
each returned HTTP 200. A fresh live API session selected
`caro-kann-white-bf5`, reported five learner decisions, and returned the
expected Caro-Kann introduction.

## Limits

This is one compact Advance repertoire, not a survey of the Classical,
Panov, Fantasy, or exchange variations. The exercises distinguish three plans
but do not model their real-world frequency. A learner playtest should verify
that the difference between developing, exchanging on c5, and supporting d4
with c3 is clear on the board.
