# ADR 0021: Teach a named Sicilian response before mixed practice

- Status: accepted
- Date: 2026-09-26
- Extends: ADR 0016
- Completion semantics amended by: ADR 0022

## Context

The learner has an Italian course for White, but `1...c5` prevents that setup.
The learner asked for the next opening to learn and approved the recommendation
to add a White response to the Sicilian Defense. The earlier `1.e4` foundations
PGN held a short Sicilian sketch, but it was deliberately unreachable under
ADR 0016 because appearing during Italian practice violated the course's
prerequisites.

## Options considered

1. Extend the Italian scenario selector to include `1...c5`. Rejected: the
   selected course would no longer match the position or taught plan.
2. Add a deep Open Sicilian repertoire with hidden random branches. Rejected:
   the learner first needs a small, named plan and a chance to recognize each
   black response.
3. Teach a separate, finite Sicilian course for White with visible named lines.
   Chosen as the smallest useful expansion of the learner's existing `1.e4`
   repertoire.

## Decision

The browser offers “Sizilianisch üben” beside Italian practice and free play.
The course introduces how `...c5` contests `d4`, then provides three named
exercises against `2...d6`, `2...Nc6`, and `2...e6`. Each begins with `1.e4`,
uses `2.Nf3` and the `d4` central break, and finishes after five White moves.
The board and feed explain both sides' moves, with the normal two hints and
third-attempt reveal. The initial prompt and a short board-side introduction
teach the purpose before the line is practised.

The three lessons use `LessonFamily=e4-white-foundations` and an explicit
selection allowlist. Their `RealisticWeight` remains zero. Italian selection
continues to filter only `italian-white`, and the Sicilian course has no hidden
mixed-opponent mode. The other five `1.e4` response sketches remain inaccessible
until separately reviewed and introduced.

## Consequences

The learner can now practise a response when Black leaves the Italian path on
move one. The course is intentionally shallow: after the central structure is
established, ordinary free play handles later moves (ADR 0022). It does not promise a
complete Sicilian repertoire or claim that the teaching lines are unique best
moves. Named branches can be extended in response to real learner questions.

The authored lines were reviewed for legal moves, concrete explanations, and
Stockfish plausibility. The dated evaluation records the checks and limits.
