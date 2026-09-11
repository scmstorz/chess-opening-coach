# ADR 0015: Teach opponent variation through curated hidden scenarios

- Status: accepted
- Date: 2026-09-11
- Supersedes: the single-line limitation recorded in ADR 0014

## Context

The first Italian lesson deliberately used one fixed Black line. That made the
recall loop predictable, but the learner identified its central transfer
problem: memorizing one cooperative sequence does not teach what to do when a
real opponent chooses another sound defense, an offbeat move, or a mistake.
This matters especially at roughly 700 rapid Elo, where early deviations are
common and recognizing a changed problem is more useful than recalling a long
main line.

The product must support all three learning jobs without confusing them:

1. repeat one model setup until its logic is familiar;
2. start directly after a known opponent deviation and practise the response;
3. begin from move one without knowing which defense the coach will choose.

The third job must not reveal the selected scenario in the API or UI before
Black has actually played the first move that distinguishes it from the model
line.

## Options considered

1. **Encode a full branching repertoire tree immediately.** This is the
   eventual expressive model, but it would require policies for transpositions,
   several accepted White moves, branch-specific completion, and comments on
   every edge before the first transfer question could be tested.
2. **Ask Stockfish to choose every Black move dynamically.** This creates varied
   play, but engine top moves are not a stable human curriculum. Independent
   choices can also leave the authored lesson after each half-move and cannot by
   themselves explain the intended teaching point.
3. **Generate weak moves to imitate a 700-Elo opponent.** Without a local game
   frequency dataset this would pretend to know what is common at that rating.
   Random engine degradation could produce nonsense rather than instructive
   mistakes.
4. **Author several complete, linear PGN scenarios and select one per session.**
   The same legal, explainable scenario can power a direct deviation drill or a
   hidden full-game path. The scenario remains coherent while the selection
   varies between sessions.

## Decision

Choose option 4 as the next vertical slice. Keep annotated PGN as the source of
truth and add scenario metadata rather than a second repertoire language:

- `LessonFamily` groups scenarios into the Italian-from-White curriculum.
- `DrillStartPly` identifies the first White decision after the deviation.
- `OpponentCategory` distinguishes established, solid, slow, dubious, trap, and
  mistake scenarios for audit purposes.
- `RealisticWeight` controls local random selection.

The 13-scenario family contains the original quiet Italian model line plus
Sicilian, French, Caro-Kann, Petroff, Philidor, Damiano, Two Knights, Hungarian,
Rousseau, Blackburne-Shilling, early `...h6`, and early `...a6` responses. The
first three alternatives explicitly teach that White cannot force the Italian
after `1...c5`, `1...e6`, or `1...c6`; the task is to recognize the new opening
and adopt a suitable plan.

The browser exposes three guided styles:

- **Grundlinie:** always start at move one in the original model line.
- **Abweichung üben:** choose a non-mainline scenario and reconstruct the board
  directly at `DrillStartPly`. Earlier moves are visible as muted context, not
  counted as moves played in the current exercise.
- **Realistischer Gegner:** choose one weighted scenario but start at move one.
  Its title, ID, goal, opening label, and scenario-specific length remain generic
  until Black's first differing reply is on the board. Shared prefix moves do
  not reveal a later deviation.

One scenario is selected for the whole session. This is variation between
games, not independent randomness between half-moves. It preserves a legal,
authored path and makes every coach explanation correspond to the position that
will actually follow.

The weights total 100 for easy inspection, but are explicitly pedagogical
weights, not claimed chess.org frequencies. No network or external player
database was consulted. Established alternatives receive most of the mass;
slow moves, dubious gambits, and outright mistakes remain possible but rare.

`lesson_style` is persisted beside `lesson_id`, `training_mode`, broad
`theory_match`, and exact `repertoire_match`. A branch session also stores its
initial FEN and context history so historical questions and full-turn undo
reconstruct the correct position. A lesson may end after the learner's move;
the service no longer requires a final coach reply.

## Consequences

The learner can now repeat the canonical plan, isolate a branch, or test
recognition under uncertainty. The default guided experience is the realistic
style; the other two remain one-click choices. The free-play mode remains the
escape hatch for moves outside the curated family.

This is not exhaustive opponent modelling. Each scenario currently teaches one
authored White response at each position. A different legal move is still
analysed separately by Stockfish and may be reported as objectively playable,
but it does not silently branch into unauthored curriculum. Future work may add
accepted alternatives and transpositions after real use shows where they are
needed.

Stockfish 18 audited all 43 White learning decisions from their relevant drill
starts with a 0.35-second, depth-at-most-20 search. The maximum measured loss was
0.27 pawns; established scenarios stayed within 0.10. The Hungarian scenario
was changed during the audit because its first version said “use more centre”
but postponed the available `d5` advance. All 13 complete scenarios, 132
half-moves in total, then passed a real-engine production-service self-play.
Sixty random branch starts also reconstructed legal White-to-move positions.
