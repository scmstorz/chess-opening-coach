# ADR 0018: Separate scenario completion from opening completion

- Status: accepted
- Date: 2026-09-12

## Context

In a real “Realistischer Gegner” session, Black selected the Two Knights
scenario and played `1...e5 2...Nc6 3...Nf6 4...Bc5 5...d6`. After White's
`6.c3`, the service emitted “Geschafft: Du hast diese realistische Gegnerlinie
vollständig gespielt” and locked the board. The line had reached the end of its
11-ply authored PGN, but the ordinary Italian model lesson continues to 20
plies. More importantly, the opening itself had not necessarily ended.

The defect was semantic rather than chessical: one numeric condition
(`lesson_ply >= len(lesson.moves)`) represented three different events:

1. the prepared scenario has no further authored move;
2. the learner has completed the selected exercise;
3. the opening phase or game has ended.

Those events happen together in a finite branch drill, but not in a game against
a realistic opponent.

## Options considered

1. Keep the early success message and let the learner start another session.
   Rejected because it contradicts the mode's promise of playing an opponent and
   prevents transfer beyond the memorized branch.
2. Extend every short scenario manually to the same move number. Rejected because
   it creates filler lines, increases authoring cost, and still equates a data
   boundary with a chess phase boundary.
3. Splice the remaining model-line moves onto every deviation. Rejected because
   transpositions are not guaranteed and a different Black setup may require a
   different plan.
4. Mark the scenario boundary as a milestone and continue from the actual board
   with the existing theory-first, Stockfish-verified free policy.

## Decision

Choose option 4 for `realistic` sessions only. Model-line repetition and direct
branch drills remain finite exercises and still produce their existing success
summary. In realistic mode, exhausting the chosen PGN now:

- emits an `Etappenziel`, not “Geschafft”;
- removes the progress counter for the exhausted fixed segment;
- keeps the board active;
- chooses later coach moves from local opening theory, falling back to Stockfish;
- evaluates later learner moves through the normal legality/theory/engine path;
- prevents the opening-end heuristic from firing before the 20-ply model-line
  horizon; and
- then uses the existing learner-controlled opening transition instead of
  declaring success automatically.

The session retains its scenario identity for provenance and historical
questions. A separate `guided_segment_complete` state controls move policy.
Turn snapshots store this state so one undo across the boundary restores the
authored final question and removes both the milestone and the free coach reply.

## Consequences

The coach can teach a concrete response and immediately test whether the learner
can continue from the resulting position. The continuation may be less richly
authored than the fixed segment, but its chess truth remains grounded in the same
local theory, `python-chess`, and Stockfish layers used by free play.

This is deliberately not an automatic proof that the learner has mastered the
branch. The milestone states only that the prepared moves were completed. Future
spaced repetition can use the persisted interactions without reusing the word
“Geschafft” for a session that is still in progress.
