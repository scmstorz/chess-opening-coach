# ADR 0016: Gate opponent variation by learner readiness

- Status: accepted
- Date: 2026-09-12
- Supersedes: the active curriculum boundary in ADR 0015

## Context

The learner's first real use of the new realistic mode selected `1...c5`. The
coach correctly explained that the Sicilian Defense makes an Italian Game
impossible. The statement was chessically true but pedagogically mistimed: the
learner had deliberately chosen “Italienisch üben” because no repertoire against
the Sicilian, French, or Caro-Kann had yet been learned.

The failure was therefore not move legality, engine quality, or wording. It was
curriculum selection. Technical variety had been mistaken for useful variation.
A beginner cannot practise transferring an Italian plan in a position where the
Italian opening never arose and no replacement plan has yet been taught.

## Options considered

1. Keep all scenarios but explain the opening switch. Rejected because naming an
   unfamiliar opening does not give the learner enough knowledge to play it.
2. Merely reduce the weights of early switches. Rejected because even a rare
   `1...c5` still violates the promise of the selected training mode.
3. Delete the six early-switch lessons. Rejected because their authored,
   legality-checked content remains useful for a later `1.e4` foundations course.
4. Give lessons an explicit curriculum family and select only scenarios whose
   prerequisites have been taught.

## Decision

Choose option 4. “Italienisch üben” now selects only seven scenarios sharing the
complete prefix `1.e4 e5 2.Nf3 Nc6 3.Bc4`:

- the quiet `3...Bc5` model line;
- `3...Nf6` (Two Knights);
- `3...Be7` (Hungarian);
- `3...f5` (Rousseau);
- `3...Nd4` (Blackburne-Shilling);
- a later early `...h6`;
- a later early `...a6`.

The model/realistic weights are normalized to 47/35/6/4/4/2/2. These remain
pedagogical weights, not empirical game frequencies. Both “Abweichung üben” and
“Realistischer Gegner” filter by `LessonFamily=italian-white`; the latter starts
at move one but cannot leave the learned opening before `3.Bc4`.

The Sicilian, French, Caro-Kann, Petroff, Philidor, and Damiano lessons are
retained under `LessonFamily=e4-white-foundations` with selection weight zero.
They will become available only through a separately named curriculum after the
learner has been introduced to the corresponding response plans.

The generic realistic-mode prompt now says that Black varies *within* the
Italian Game. It no longer asks the learner to detect an unprepared opening
switch. The Two Knights lesson goal was also rewritten because it accidentally
contained the target move `d3` before the learner answered.

## Consequences

The active mode is narrower but now matches its label and the learner's current
knowledge. Variety begins at the first meaningful Italian decision instead of
at the first legal reply to `e4`. The six inactive lessons remain tested as valid
data, but an explicit request to select one through the Italian API fails closed.

Curriculum family is now a prerequisite boundary rather than a loose thematic
tag. The future foundations mode needs its own introduction and selection UI;
changing a weight alone must not make those lessons appear under Italian
practice.

