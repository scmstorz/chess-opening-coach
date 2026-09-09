# Dogfooding the learning loop

Date: 2026-09-09

## Why this came before a third book

After the two-book quality cycle, the next proposed increment was another
source. The learner suggested that the agent should instead play the product.
This was the higher-value experiment: more text can improve coverage, but it
cannot reveal whether the existing interaction binds questions to the right
position, repeats itself, teaches a causal idea, or undoes a complete turn.

The test used the production FastAPI endpoints on the fixed local ports with
Stockfish 18, `qwen3.8:27b-mlx`, the Lichess opening graph, and the two-book
knowledge database. The local Browser control plugin failed before page control
because its bundled runtime imported a module rejected by the current tool
runtime. The product itself remained healthy. The same HTTP flows used by the
browser UI were exercised directly; visual drag-and-drop remains outside this
specific run.

## Scenarios played

### White: Ruy Lopez and an intentional learner mistake

The line began `1.e4 e5 2.Nf3 Nc6`. The theory-first suggestion returned
`3.Bb5`, and the deep question asked for its medium- and long-term purpose.
`4.Na3` was then played deliberately. Stockfish measured a 1.34-pawn loss and
the coach kept the original position for the first correction hint. A later
`b3` was accepted as an inaccuracy and the coach replied.

The first deep `Bb5` answer was factually safer than the earlier product
versions, but it repeated the c6-defender explanation several times across the
book, concrete-effect, and generic geometry layers. More importantly, the
question “Why was `b3` inaccurate?” produced an answer about `Bxc6`. The live
board had advanced past `b3`; the resolver found no current legal `b3` and
silently fell back to a current theory suggestion.

### Regression: a past `d3` question

A fresh game reached `1.e4 e5 2.d3 d5`. The first fixed run correctly rebuilt
the position before `2.d3`; it no longer discussed a different current move.
That run also exposed a pedagogical gap: the answer could compare evaluations
but did not state the simple reason `d3` is playable.

Board-derived support and development facts were added. The final deep answer
began:

> `d3` supports the own pawn on `e4`. The move opens new development squares
> for the bishop on `c1`.

It then kept the smaller engine preference for `Nf3`, a recurring `Nc3`
follow-up across two of three reply branches, and the raw lines in separate
layers. The question target was `d3`, and the live game remained unchanged.

### Black perspective and undo

A black session began with coach move `1.e4`. Its first message correctly said
that the opening begins with that move. The learner answered `1...c5`; the
coach classified it as theoretical and objectively strong, then played `2.Nf3`.
Undo removed both `...c5` and the coach reply, restored Black to move after
`1.e4`, removed both associated feed messages, and left the initial coach move
intact.

### Final Ruy Lopez regression

The final suggestion for `Bb5` contains the c6-defender explanation once, not
twice. The deep answer now separates:

- an attributed opening-level book plan;
- `Ba4`, castling, and `d4` as a model continuation;
- castling recurring after all three plausible replies;
- the concrete pressure on the `c6` defender of `e5`;
- a comparison with `Bc4`; and
- three raw reply branches.

The generic “direct central squares” comparison was removed because it had
repeatedly produced true but unhelpful geometry instead of a plan. If the main
line captures the moved piece immediately, temporary square control and attacks
from its destination are now suppressed.

## Retrieval finding

The last `Bb5` run listed a second citation from *Fundamental Chess Openings*
about the Schliemann/Jaenisch Gambit even though that claim was not shown. A
broad FTS move match had found another sub-variation inside the Ruy Lopez
section. Retrieval now admits recommendations and warnings only from exact
position matches. Broad opening, move, and question matches can return only
general plan claims. A direct database regression leaves one relevant general
Ruy Lopez plan and removes the Schliemann recommendation.

## Result

The run found one critical reference bug, two teaching-quality defects, and one
retrieval precision defect before adding any new source:

| Severity | Finding | Outcome |
| --- | --- | --- |
| Critical | Past `b3` question answered as current `Bxc6` | historical transition replay |
| High | `d3` lacked its pawn-support and bishop-development purpose | deterministic board facts |
| Medium | `Bb5` defender effect repeated across layers | specificity preference and sentence deduplication |
| Medium | broad Ruy section exposed unrelated Schliemann citation | exact-position rule for recommendations/warnings |

The deep calls observed variable local latency from roughly 28 seconds to over
one minute when generation or critique needed another pass. This supports the
existing rolling estimate and “one more moment” state rather than a promised
exact countdown.

Automated verification after the fixes:

- 67 backend tests pass;
- ESLint passes;
- the production browser build passes; and
- the rendered product-shell test passes.

## Remaining limits

- This run did not visually revalidate drag-and-drop or scroll behavior because
  the external Browser control plugin failed before page interaction.
- The broad beginner-book Ruy Lopez plan is correctly attributed but remains a
  weaker source than a position-specific annotated explanation.
- Historical replay currently assumes a normal initial chess position.
- A legal move rejected into the three-attempt correction loop is resolved on
  the unchanged current board rather than being mistaken for the last accepted
  historical move.
- Human judgment is still required to decide whether the improved wording is
  memorable, not merely correct.

## Next source candidate

If the next increment returns to books, John Emms' *Discovering Chess Openings:
Building Opening Skills from Basic Principles* is the strongest local candidate.
It complements the encyclopedic breadth of *Fundamental Chess Openings* with
principle- and explanation-oriented teaching. It should first be sampled on the
existing `d3`, `Bb5`, `Na2`, and `a4` evaluation positions before committing to
a full import.
