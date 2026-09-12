# Realistic continuation regression

- Date: 2026-09-12
- Trigger: learner report from an actual Italian practice session

## Reproduced sequence

The stored interaction history confirmed two attempts at the same scenario:

`1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.d3 Bc5 5.O-O d6 6.c3`

This is the curated Two Knights scenario. Its later move order reaches a familiar
Italian setup, but the scenario PGN ends after White's `6.c3`. The old service
therefore treated an exhausted branch as a completed realistic session and
showed the learner a premature success message.

## Acceptance criteria

- `6.c3` is accepted as the final authored move.
- The session remains in the opening phase and the board remains playable.
- The fixed training progress disappears because there is no longer a hidden
  authored answer to count.
- A clearly worded milestone says that the prepared segment—not the game—ended.
- Black immediately supplies a legal theory/engine continuation.
- A subsequent legal White move and Black reply are appended normally.
- No response says “Geschafft”.
- Undo removes `6.c3`, Black's continuation, and the milestone together, then
  restores the sixth guided question.
- If the realistic opponent follows the full 20-ply model line, the service
  offers the ordinary opening-phase decision rather than lesson success.

## Automated regression

`backend/tests/test_guided.py` now contains the exact Two Knights sequence, a
free-continuation assertion, a boundary undo assertion, and a full realistic
model-line assertion. Existing tests preserve the intentional finite completion
behavior of direct `Grundlinie` and `Abweichung üben` sessions.

A production-service check repeated the reported sequence with the full local
3,810-line opening graph and Stockfish 18, while keeping persistence in memory.
The response remained in `opening`, contained 12 plies, played the legal reply
`6...h6`, emitted the message kinds `move`, `milestone`, `move`, contained no
“Geschafft”, and returned control to White on an active board.

The repository-wide checkpoint passed 104 backend tests, Ruff, frontend lint,
the production build, the rendered-shell test, and the whitespace check. The
public-release scan then checked 113 staged paths and 111 historical paths
against 113 private-corpus text variants without finding a leak.
