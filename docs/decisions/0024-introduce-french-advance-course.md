# ADR 0024: Teach the French Advance pawn chain as the third guided course

- Status: accepted
- Date: 2026-09-26
- Extends: ADR 0021
- Reuses continuation behavior: ADR 0022 and ADR 0023

## Context

After playing the Italian and Sicilian courses, the learner asked for more
opening breadth and approved French Defense practice with White. The old
inactive French sketch under `italian-white.pgn` showed a Classical French
line with `3.Nc3 Nf6 4.e5 Nfd7 5.f4`. It was legal but offered one line and
an early `f4` pawn move without first teaching the recurring pawn-chain idea.
It remained inaccessible inside Italian practice by design.

## Decision

Give French its own named course. The first lesson teaches the Advance plan:
`1.e4 e6 2.d4 d5 3.e5 c5 4.c3`. White learns that `d4` supports the advanced
`e5` pawn, `...c5` attacks the base on `d4`, and `c3` supports it. Three visible
exercises show `4...Nc6`, `4...Qb6`, and `4...cxd4`. White develops `Nf3` in
the first two and recaptures `cxd4` in the third. Every move has an authored
position-specific explanation and every White move has two hints.

The old Classical sketch is removed from the Italian PGN. The three French
lessons live in `french-white.pgn`, carry zero realistic-selection weight, and
are available only by explicit lesson ID in mainline style. After the fifth
White decision and a scripted Black fifth move, the lesson emits a milestone
and becomes free opening play. Undo returns to the final taught decision.
Italian realistic selection remains Italian-only; the remaining Caro-Kann,
Petroff, Philidor, and Damiano sketches stay inactive.

## Consequences

The third course expands the learner's `1.e4` coverage without exposing an
untaught defense inside another course. The Advance is a teaching choice, not
a claim that `3.e5` is uniquely best. The three lines are short examples, not
a full French repertoire. The scripted fifth Black move gives White a clear
position from which to request a suggestion, ask a question, or continue.
The dated evaluation records legal replay, engine plausibility, and service
checks. A first guided course for Black remains a future product decision.
