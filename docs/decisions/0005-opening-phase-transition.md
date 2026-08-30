# ADR 0005: Treat the end of an opening as a learner-controlled probable transition

- Status: accepted
- Date: 2026-08-30

## Context

The learner wants the coach to announce when the opening phase is over and then
let them decide whether to continue the game or review the opening. A fixed move
number is misleading, while the absence of a local theory edge can merely mean
that the player chose an unusual but still early move. The product also needs a
closed learning loop instead of an indefinitely growing move feed.

## Decision

Combine local-theory coverage, minor-piece movement, castling history, central
pawn movement, and elapsed half-moves into a transparent heuristic. Describe the
result as “probably” rather than as chess truth. Pause the board at that point
and require an explicit learner choice.

Continuing changes the session to middlegame mode, where Stockfish supplies
coach moves and suggestions. Reviewing produces a deterministic summary from
the current board and persisted interaction records. Store the summary and any
review recommendation in local SQLite, but never start a review automatically.

## Consequences

An early departure from the opening dataset cannot prematurely end the lesson.
The UI can show exactly which signals fired, and the learner retains control of
the next action. The heuristic is intentionally measurable and replaceable as
real sessions reveal false positives or late detections. Opening-specific
strategic claims are not invented when the available data supports only general
center, development, king-safety, theory, and engine facts.
