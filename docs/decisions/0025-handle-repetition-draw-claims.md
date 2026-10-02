# ADR 0025: Separate claimable threefold repetition from automatic game end

- Status: accepted
- Date: 2026-10-02

## Context

The learner repeated a queen move while the coach repeated a king move. The
current interaction history showed four equivalent positions occurring three
times, with the same side to move and unchanged castling and en-passant rights,
but the coach continued. The service used `Board.is_game_over()` with its
default `claim_draw=False`. That correctly excludes a claimable threefold
repetition, but the product exposed no way for the learner to make the claim.

FIDE distinguishes a third occurrence, which the player to move may claim,
from a fifth occurrence, which ends the game automatically. Treating the third
occurrence as an unconditional automatic draw would hide that distinction and
remove the learner's option to continue.

## Decision

Expose a structured `draw_claim` when the current position has actually
occurred at least three times and the learner is the player to move. The browser
shows a **Remis beanspruchen** action but keeps the board playable. A dedicated
API endpoint validates the right again before recording a claimed `1/2-1/2`
game end.

Use `Board.outcome(claim_draw=False)` for automatic terminal states. Fivefold
repetition therefore ends immediately and is reported separately from the
learner's optional threefold claim. A structured session-level `game_end`
locks further moves and records the reason, result, explanation, and whether
the ending was automatic.

Store a full board copy, including its move stack, in every undo snapshot.
Restoring only a FEN is insufficient because the current position does not
encode how often it occurred.

## Consequences

The interface now teaches the actual distinction between claiming a draw and
an automatic draw. The learner may ignore a threefold opportunity and continue.
The coach does not claim on its own turn; the feature represents the learner's
right to claim. The implementation currently offers a claim once the repeated
position is on the board; it does not implement the over-the-board procedure of
declaring an intended move that would create the third occurrence.

Keeping complete board histories in snapshots uses slightly more memory, but
sessions are local, in-memory, and short enough that correctness outweighs the
small cost. Restarting the service still discards active games by design.
