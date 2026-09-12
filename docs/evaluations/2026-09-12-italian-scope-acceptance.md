# Italian curriculum scope acceptance

- Date: 2026-09-12
- Trigger: first learner session in the varied-opponent mode

## Observed failure

The first Black reply was `1...c5`, followed by the correct statement that the
Italian Game was no longer possible. This tested opening recognition, but not
the selected learning goal. The learner had not learned a Sicilian response and
could therefore neither recall nor understand the expected continuation.

## Acceptance boundary

Every scenario reachable from “Italienisch üben” must contain the common prefix
`1.e4 e5 2.Nf3 Nc6 3.Bc4`. Variation may begin with Black's third move or later.
Early switches to other opening families must remain unavailable until a
separately named curriculum teaches them.

## Automated checks

- Random realistic selection returns exactly seven active Italian scenarios.
- The Sicilian lesson still loads from PGN but has family
  `e4-white-foundations`, weight zero, and cannot be explicitly selected through
  Italian practice.
- Direct deviation drills begin no earlier than after Black's third move.
- A hidden Two Knights scenario remains unnamed through `1...e5` and `2...Nc6`,
  then reveals itself after `3...Nf6`.
- A later `...h6` scenario remains hidden through the shared `3...Bc5` reply.
- The first branch prompt contains neither its answer nor a lesson goal that
  spells out that answer.

No chess moves were changed in this correction, so the Stockfish 18 move audit
from 2026-09-11 remains applicable. The changed boundary concerns prerequisite
knowledge and product semantics rather than objective move quality.

## Verification result

The real service then played all seven active scenarios to completion with
Stockfish 18. All 80 half-moves were accepted and persisted, and every line
began with the required five-ply Italian prefix. One hundred hidden realistic
selections and 60 random branch starts selected only active Italian lessons;
all branch contexts started after Black's third move or later. The six parked
`1.e4` foundation lessons still loaded, but none entered either Italian mode.

The final automated checkpoint passed 99 backend tests, Ruff, frontend lint,
the vinext production build, the rendered-shell contract, and the whitespace
check. The release publication guard checked 104 tracked and 104 historical
paths against 111 private-corpus text variants without finding a leak.
