# ADR 0014: Add immediate-recall guided repertoire practice

- Status: accepted
- Date: 2026-09-10

## Context

Free opening play answers the learner's exploratory question: “What opening are
we entering, and how good was my move?” It does not reliably teach one coherent
opening, because the coach and learner may branch on every turn. The learner
wants both products: free play and deliberate practice of a named opening. At
approximately 700 rapid Elo, the immediate goal is not exhaustive theoretical
coverage but reaching a playable position in the first five to ten moves while
understanding the purpose of those moves.

The first deliberate lesson is the Italian Game from White. The learner chose
White and explicitly rejected a discovery-style preview: the board should ask
for the move immediately, without showing it first. Explanations still belong
after every learner and coach half-move. The existing two-hint, third-attempt
correction contract remains desirable.

## Options considered

1. Continue using the large opening graph and merely label a target opening.
   Rejected for the first slice because weighted opponent moves can leave the
   intended lesson before its key plan has been learned.
2. Generate a line dynamically from Stockfish. Rejected because an engine's
   current top line is not a stable human repertoire and its evaluation does not
   explain the teaching goal.
3. Build a new JSON lesson language. Rejected because PGN already represents
   legal move sequences, variations, and comments, and should remain the
   repertoire source of truth.
4. Add one authored, engine-checked PGN lesson with a fixed opponent line and a
   separate session mode. Ask first, explain after play, preserve optional
   explicit revelation through the existing suggestion control, and expand to
   variations only after this vertical slice is validated.

## Decision

Choose option 4. The initial tracked PGN teaches the quiet Italian sequence

`1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.d3 Nf6 5.O-O d6 6.c3 O-O 7.Re1 a6 8.Bb3 Ba7 9.Nbd2 Re8 10.h3 h6`.

Every half-move has an authored German explanation. Every White move also has
two progressive hints stored as PGN comment annotations. These comments were
written for this project; they are not copied from the private book corpus.
The parser accepts only one main line in this first version, validates every
move with `python-chess`, requires every move to have an explanation, and uses
the tracked PGN as the sole lesson source of truth.

Starting guided mode immediately creates an active White board and asks “Was
ist dein erster Zug?” The expected move is not exposed in the session payload.
If the learner plays the expected legal move, it is accepted, explained, and
followed by the fixed authored coach reply. A different legal move is analysed
by Stockfish but not played: the response states separately that the move is not
the target of this lesson and whether the engine considers it playable. The
first two attempts reveal one hint each; the third miss records the attempted
move, places the lesson move, explains it, and continues the line. An explicit
`Zug vorschlagen` request may reveal and highlight the target without moving it.

`theory_match` remains the answer to “is this move present in the broad local
opening graph?” A new `repertoire_match` field answers “is this the move in the
active lesson?” SQLite also stores `training_mode` and `lesson_id`. This avoids
turning a good non-lesson move into an objective chess error. The schema adds
these columns in place for existing local databases.

A turn snapshot includes the lesson ply. Undo removes both half-moves and the
associated feed entries, restores the prior lesson question, and can also reopen
the final turn after automatic lesson completion. Completion creates the same
grounded local session summary used by free play and adds the lesson identity.

## Consequences

The fixed reply line is intentionally deterministic. It supports recall and
causal explanations, but it does not yet teach transpositions or alternative
Black defenses. Free play remains available beside the lesson for exploration.
Later PGN variations will require an explicit policy for accepted learner
alternatives and coach reply selection; the first slice does not silently invent
that policy.

Authored explanations provide stable teaching content for the core lesson.
Stockfish still checks objective quality and supplies concrete analysis, but its
top-one choice does not replace the repertoire. A 0.5-second MultiPV check of
all 20 half-moves found a maximum loss of 0.16 pawns; the normal production
budget later measured 0.22 for `3.Bc4`. This small search-budget variation is
evidence for preserving the conceptual distinction rather than chasing a
volatile top move.

The default browser entry now opens this guided White lesson because it is the
active learning slice. The learner can switch to free play and choose White,
Black, or random. Both modes remain untimed.
