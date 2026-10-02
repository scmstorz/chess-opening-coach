# French-from-White course: content and continuation audit

- Date: 2026-09-26
- Learner context: approximately 700 rapid Elo, untimed guided practice
- Engine: local Stockfish, 0.35 seconds per unrestricted and forced-root
  search, two threads and 64 MB hash

## Question

Can a separate French course teach a transferable response to `1...e6`,
including the purpose of the `e5`–`d4` pawn chain, while keeping Italian
practice limited to Italian positions?

## Authored scope

The former inactive `3.Nc3` French sketch was removed from the Italian PGN.
Three new C02 Advance lessons start at move one and share
`1.e4 e6 2.d4 d5 3.e5 c5 4.c3`. Against `4...Nc6` and `4...Qb6`, White develops
`5.Nf3`, which also protects `d4`. Against `4...cxd4`, White plays `5.cxd4`
to restore a pawn on `d4`. Each lesson includes a fifth Black move, so the
prepared segment ends with White to move. The scripted segment then becomes
free opening play, with the same immediate deterministic feedback used after
the Sicilian teaching lines.

The PGN loader checks move legality, nonempty explanations for both sides,
and exactly two hints for each learner move. The explanation for `...Qb6`
distinguishes its view of `b2` from the later pressure on `d4` after a center
exchange; it does not claim the queen currently attacks `d4` through its own
pawn on `c5`.

## Engine check

Reproduce with:

```bash
.venv/bin/python benchmarks/audit_sicilian_lessons.py \
  --pgn data/repertoires/french-white.pgn \
  --engine /opt/homebrew/bin/stockfish --seconds 0.35
```

Recorded maximum evaluation loss per taught move:

| Black's fourth move | White maximum | Black maximum |
| --- | ---: | ---: |
| `...Nc6` | 0.10 pawn | 0.14 pawn |
| `...Qb6` | 0.13 pawn | 0.11 pawn |
| `...cxd4` | 0.09 pawn | 0.19 pawn |

Short engine searches vary and support plausibility, not a unique best move
or an estimate of how often these replies occur at the learner's level.

## Product checks

Service tests create each named line, obtain every hinted repertoire move,
play the full segment, verify the selected Black reply and milestone, then
request and play one free move. A tutor spy rejects automatic model calls in
free continuation. Undo restores the final guided decision. Selection tests
keep hidden French variations and the remaining inactive foundations sketches
inaccessible. The rendered page test finds the French course control.

An isolated replay with real Stockfish and the full local opening graph reached
all three milestones. The first free suggestions were `Bd3`, `Bd3`, and `Nc3`;
the coach answered with legal moves `...cxd4`, `...cxd4`, and `...Nge7`.
All three sessions stayed in the opening phase with White able to continue.
The live local server was not used for this replay, so learner records were
not polluted by test games.

## Limits

The course covers one coherent Advance structure and three short replies,
not every French variation or transposition. A real learner playtest should
check whether the distinctions between supporting `d4`, developing `Nf3`,
and recapturing on `d4` are clear from the board and the feedback.
