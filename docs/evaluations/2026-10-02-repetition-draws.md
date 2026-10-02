# Repetition-draw regression check

- Date: 2026-10-02
- Rules authority: `python-chess` 1.11.2 and FIDE Laws of Chess articles 9.2 and 9.6.1

## Reported case

The most recent local interaction history contained a repeated
`Qh2–Kc7–Qh6+–Kc6` cycle. Comparing piece placement, side to move, castling
rights, and en-passant rights confirmed that four positions in the cycle each
appeared three times. Halfmove and fullmove counters differed, but those are
not part of position identity for repetition. The coach continued because all
game-over checks used the default `claim_draw=False` behavior and there was no
claim endpoint.

## Automated cases

The regression fixture uses the legal reversible cycle
`Nf3 Nf6 Ng1 Ng8` from the initial position:

- after the initial position's third occurrence, the response offers a
  `threefold_repetition` claim, leaves legal moves available, and does not mark
  the game over;
- claiming returns `1/2-1/2`, records a non-automatic structured game end,
  removes legal moves from the response, and emits a verified rules message;
- after the fifth occurrence, the response ends the game automatically with
  reason `fivefold_repetition`;
- undo restores a full board stack and still detects an already established
  threefold repetition;
- the FastAPI endpoint accepts a valid claim and rejects a second claim after
  the game is over.

## Verification

The focused service/API suite passed 31 tests. The complete backend suite
passed 121 tests. Ruff, frontend lint, the production browser build, the
rendered-shell test, `git diff --check`, and the publication guard also passed.

The in-app browser harness could not initialize in this environment because
its packaged client requested a restricted Node built-in. After the learner
explicitly approved discarding the in-memory game, the main local services
restarted with the new code. Live checks found the claim route in OpenAPI,
confirmed `game_end` and `draw_claim` in a fresh session, received the expected
409 for an early claim, and found the claim-button copy in the served frontend.
The automated fixtures cover the valid threefold visual state; a real learner
playtest remains useful for judging the banner in context.
