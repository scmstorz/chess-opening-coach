# Sicilian-from-White course: line and selection audit

- Date: 2026-09-26
- Learner context: approximately 700 rapid Elo, untimed guided practice
- Engine: local Stockfish via `python-chess`, 0.35 seconds per root search,
  two threads and 64 MB hash

## Question

Can the coach teach a first response to `1...c5` without making the Italian
course select a position for which its plan no longer applies?

## Authored scope

Three named, finite lessons begin `1.e4 c5 2.Nf3`, then show `2...d6`,
`2...Nc6`, or `2...e6`. White plays `d4`, recaptures with `Nxd4` after
`...cxd4`, and develops `Nc3` against `...Nf6`. Each authored segment covers five
White decisions and stops before further Sicilian subvariations; the session
then continues as free opening play. The PGN loader
checks legality, nonempty explanations after every move, and two hints for
each learner move.

The old Sicilian switch sketch was removed from the Italian PGN and rewritten
as the `...d6` lesson. Two related responses were added. A manual review
corrected an early `...e6` draft: `Nc3` did **not** defend a knight on `d4`
against `...Nc6`. The final line uses `...Nf6`, which attacks `e4`; the
explanation now correctly says that `Nc3` defends `e4`. This illustrates why
valid moves alone do not verify prose.

## Engine check

Reproduce with:

```bash
.venv/bin/python benchmarks/audit_sicilian_lessons.py --engine /opt/homebrew/bin/stockfish
```

The script compares each authored move with Stockfish's preferred move from
the same position, using separate unrestricted and forced-root searches.
In the recorded run:

| Lesson | Maximum White loss | Maximum Black loss |
| --- | ---: | ---: |
| `...d6` | 0.10 pawn | 0.05 pawn |
| `...Nc6` | 0.00 pawn | 0.01 pawn |
| `...e6` | 0.09 pawn | 0.13 pawn |

These are short, time-limited searches and will vary slightly between runs.
They support objective plausibility of the examples, not a unique best-move
claim or a prediction of opponent frequencies.

## Product checks

Backend tests create and play each named lesson through `CoachService`,
check the introduction and Black's selected second move, verify the free coach
reply and a further learner turn, and reject an attempt to select a hidden
Sicilian line. Undo restores the final taught decision. Italian selection still
contains only the seven Italian scenarios; the other five foundations lessons
remain inaccessible. The browser offers explicit course and lesson controls.

A live local run of the `...d6` lesson reached `5.Nc3`, received a free `...g6`
coach reply, remained in the opening phase, and left White with legal moves.

## Limits

The module teaches one central plan, not a complete repertoire against every
legal Black reply. The engine check cannot prove that the learner understands
the explanations. Real playtesting should focus on whether the learner knows
*why* `d4` and `Nxd4` follow `...c5`, and whether the named `...d6`, `...Nc6`,
and `...e6` choices are easy to distinguish in the interface.
