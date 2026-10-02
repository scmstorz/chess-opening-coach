# ADR 0026: Teach the Caro-Kann Advance as the fourth guided course

- Status: accepted
- Date: 2026-10-02
- Extends: ADR 0021 and ADR 0024
- Reuses continuation behavior: ADR 0022 and ADR 0023

## Context

The learner has guided White courses against `1...e5`, `1...c5`, and `1...e6`
and asked for another opening. Caro-Kann is the remaining major first-move
response already represented by an inactive foundations sketch. That sketch
used the Classical line `3.Nc3 dxe4 4.Nxe4 Bf5`, but it offered only one short
sequence and remained inaccessible by design.

## Decision

Give Caro-Kann its own named White course and teach the Advance setup
`1.e4 c6 2.d4 d5 3.e5`. Three visible exercises present `3...Bf5`, `3...c5`,
and `3...e6`. Against the active bishop, White develops `Nf3` and `Be2`; against
the immediate pawn break, White exchanges on c5 and develops instead of trying
to keep the temporary extra pawn; against the slower `...e6`, White develops
`Nf3` and supports d4 with `c3` after `...c5`.

Every move has a position-specific explanation and every White move has two
hints. Each script contains five White decisions and a fifth Black move, then
emits a course-specific milestone and continues as free opening play. The
lessons have zero realistic-selection weight and can be selected only by their
explicit IDs in mainline style. The old inactive Classical Caro-Kann sketch is
removed from the Italian PGN rather than maintained as a duplicate.

## Consequences

The guided White repertoire now gives the learner a coherent first answer to
the four principal replies `...e5`, `...c5`, `...e6`, and `...c6`. The Advance
is a teaching choice, not a claim that `3.e5` is uniquely best. The `...e6`
exercise deliberately prepares the learner for a playable but passive reply
that concedes more than the active `...Bf5` line in short engine analysis.
Petroff, Philidor, and Damiano foundations sketches remain inactive, and mixed
hidden practice remains a separate future product decision.
