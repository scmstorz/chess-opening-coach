# Guided Italian lesson: implementation and self-play evaluation

- Date: 2026-09-10
- Scope: first deliberate repertoire lesson, played as White
- Line: Italian Game, quiet `d3`/`c3` setup

## Product question

Could the existing free-play coach become a deliberate opening trainer without
collapsing repertoire truth into Stockfish truth or showing the answer before
the learner has tried to recall it?

The learner selected White and asked to be questioned immediately. A preview or
discovery step was explicitly declined. The lesson therefore begins on an
active board with a prompt, not a displayed move or a `Training starten` gate.

## Implemented vertical slice

- One annotated PGN is the move and explanation source of truth.
- The learner supplies each White move; the coach supplies a fixed Black reply.
- Both half-moves receive concise authored causal explanations.
- Two hints precede a third-attempt reveal.
- An explicit suggestion reveals the current target but does not play it.
- Legal non-target moves stay off the board while Stockfish quality and lesson
  membership are reported separately.
- Undo restores board, feed, lesson ply, and a completed lesson summary.
- SQLite persists broad theory membership and lesson membership independently.
- The browser exposes guided Italian and free play as two separate modes.

## Engine plausibility check

Stockfish was run locally with MultiPV 4 and 0.5 seconds per half-move over the
entire authored line. All moves were legal and the largest measured distance
from the engine's first choice was 0.16 pawns (`3.Bc4`). All other moves were
within 0.14 pawns. A second end-to-end run through the normal production service
used its shorter cached/default budget and reported 0.22 for `3.Bc4`; every
other learner move was between 0.00 and 0.04.

The discrepancy is expected for shallow opening searches and is pedagogically
important: `Bc4` is the defining Italian move and a sound repertoire choice,
even when one run ranks `Bb5` first by a small margin. The engine remains a
quality verifier, not the lesson author.

## End-to-end service self-play

The production service was started in process with the local 3,810-line opening
book, local SQLite configuration, and real Stockfish. The agent played all ten
expected White moves through the public service methods.

Observed behavior:

1. The initial response contained “Du spielst Weiß. Was ist dein erster Zug?”,
   progress 1/10, an empty move history, and no answer in the prompt.
2. Every White move was accepted as the lesson move and every fixed Black reply
   followed in the expected order.
3. The generic opening-to-middlegame detector did not interrupt the lesson.
4. After `10...h6`, the state contained 20 half-moves, phase `complete`, the
   expected final FEN, and a persisted session summary.
5. Automated fake-engine tests separately exercised two hints, third-attempt
   reveal, optional suggestion, question grounding, and undo from both an active
   and completed lesson.

The service self-play does not claim a visual browser interaction test. Visual
drag-and-drop remains a learner acceptance check once the app is running.

## Verification checkpoint

The final backend suite passed 91 tests, including eight guided-mode behavioral
checks. Ruff, frontend lint, the vinext production build, rendered HTML test,
and publication-safety check also passed during implementation.

## Follow-up evidence to collect

- Whether immediate recall feels motivating or too abrupt on the first use.
- Which of the two hints leads to successful recall at each position.
- Whether an accepted alternative should branch into another authored PGN line
  or remain a retry in a deliberately narrow lesson.
- Whether explanations after both half-moves help understanding or overload the
  ten-move sequence.
- Which positions the learner voluntarily marks `Unklar` or `Falsch`.
