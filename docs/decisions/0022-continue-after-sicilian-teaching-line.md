# ADR 0022: Continue play after a named Sicilian teaching line

- Status: accepted
- Date: 2026-09-26
- Amends: ADR 0021
- Reuses: ADR 0018

## Context

The learner played the new Sicilian course and found that the board locked
after the fifth White move. The implementation had used `mainline` style for
its named lessons, and the existing completion rule ended every non-realistic
guided session when its authored PGN ran out. In Italian “Realistischer Gegner”,
an exhausted script already becomes free opening play. The learner expected
the same continuation after the Sicilian learning segment.

## Options considered

1. Keep finite completion and require a new free game. Rejected because it
   discards the position the learner has just built and prevents practice of
   the next natural decisions.
2. Add a separate “continue” action to a completed lesson. Rejected for this
   course because the same transition already exists in the coach service and
   the extra action would interrupt a live opening.
3. Mark the named Sicilian segment complete, show a milestone, make a free
   coach reply, and continue with normal opening-phase play. Chosen.

## Decision

The three Sicilian lessons now use the existing `guided_segment_complete`
state when their authored moves run out. The coach emits a clear milestone and
then chooses the next Black reply through the ordinary theory and Stockfish
path. The learner can keep moving, ask questions, request suggestions, and
later choose whether to continue into the middlegame or create an opening
review. The normal opening-end detector does not run before 12 half-moves for
this course; the Italian realistic mode keeps its existing 20-half-move floor.

Undoing the final taught turn removes the free coach reply and milestone and
restores the last guided question. Italian model-line and direct branch drills
retain their finite completion behavior.

## Consequences

The Sicilian lesson is a taught segment inside a continuing game. Its five
White moves no longer mean the opening is over. The correction and feedback
policy switches from authored-move matching to ordinary engine-backed play at
the boundary. Tests replay all three lines through the first free turn and
verify undo across that boundary.
