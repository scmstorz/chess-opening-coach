# Progressive Emms reconstruction and production dogfood

- Date: 2026-09-09
- Source: *Discovering Chess Openings: Building opening skills from basic principles*
- Author: John Emms
- Local model: `qwen3.8:27b-mlx`
- Engine: Stockfish 18

## Question under test

Can a converted book layout of `move -> prose -> next move` improve the live
coach without guessing positions or asking the learner to verify the original
English passage?

The initial import answered “not yet”: it retained excellent searchable prose
but produced only seven trusted position anchors. The tested increment therefore
changed position reconstruction, claim binding, retrieval, and LLM criticism as
one measured path.

## Compiler experiment

The compiler now starts only from a nearby verified parent FEN, matches move
number and color, validates SAN with `python-chess`, and requires a sequence of
at least two numbered legal moves. It explores competing textual continuations
and rejects the chunk when the longest continuation is not unique or the branch
limit is reached.

The first permissive implementation looked promising numerically:

| Metric | Initial Emms import | First progressive pass |
| --- | ---: | ---: |
| Valid/context-resolved lines | 127 | 241 |
| Position evidence rows | 7 | 110 |
| Distinct reconstructed positions | 7 or fewer | 100 |
| Positioned claims | 0 | 33 |

Those numbers were not accepted as success. A fresh game reached the position
after `3...a6` and requested an explanation of `4.Ba4`. The exact result pointed
to a sentence that merely named a later Archangel variation. A compact line and
subsequent prose occupied the same large PDF chunk; “latest accepted move in the
chunk” was therefore too broad a relation.

The final rule adds three guards:

- transitions already represented inside a verified compact line are not
  duplicated as prose-separated moves;
- a claim must occur in the move's text block or the immediately following
  block; and
- another numbered move between the anchor and claim ends the relation unless
  the claim explicitly names the focus move.

Claims such as a sentence ending immediately before an ellipsis reply may be
joined only to the next verified numbered move and the first following source
sentence. This recovered the complete conditional `Bb5`/`...d6` explanation
without free completion.

## Final import

| Metric | Final result |
| --- | ---: |
| PDF pages | 363 |
| Searchable chunks | 160 |
| Claims | 435 |
| Valid/context-resolved lines | 212 |
| Flagged/contextual lines | 529 |
| Progressive half-moves | 73 |
| Position evidence rows | 81 |
| Distinct positions | 76 |
| Positioned claims | 13 |
| Safe positioned claims | 9 |
| Ambiguous progressive chunks | 51 |
| Open issues | 953 |

The lower yield than the first pass is an intentional quality correction. The
combined private database still contains three books and 1,559 synchronized
FTS chunks. Integrity, foreign keys, orphan checks, and indexed query plans pass.

## Retrieval and synthesis result

The position after `1.e4 e5 2.Nf3 Nc6 3.Bb5` now retrieves two exact,
legality-checked claims from Emms PDF pages 54-55. They describe the pressure on
the `c6` defender of `e5` and the conditional pin when Black supports `e5` with
`...d6`.

Exact progressive anchors now form a boundary: if no safe claim belongs to that
position, retrieval does not fill the gap with generic opening prose. This is
why the final `Ba4` lookup returns no book fact instead of either the unrelated
variation name or a vague beginner-book plan.

In the first real `Bb5` synthesis, Qwen added an unsupported long-term-pressure
sentence. The local critic identified only that sentence, but the old all-or-
nothing handler discarded four supported sentences as well. The handler now
removes only indexed unsupported sentences and their evidence links.

With both final Emms claims available, Qwen made a subtler error: it reversed
the actor in the conditional pin sentence. The critic again marked precisely
that sentence. The browser-facing result retained the correct book statement
about attacking the `c6` defender, the deterministic board explanation, the
recurring Stockfish continuation, candidate comparison, and one source entry
with empty warnings. The source status is `legality_checked`; no local file path
is exposed.

## Fixed quality regression

The production service path was run against the six learner-derived cases:

- `c3` ignoring the attacked bishop;
- `Na2` as a concrete exception to the rim heuristic;
- the long-term purpose of `a4`;
- `Nd5` as a central post;
- correction of the false “best `Ra6`” premise; and
- the Ruy Lopez `Bb5` plan.

All six passed the executable checks for deep mode, nonduplicate sections,
required concrete facts, forbidden platitudes, premise correction, engine
evidence, and position-scoped book use. The final two-claim `Bb5` rerun also
passed. Its local end-to-end latency was 26.97 seconds with cached engine data;
this remains evidence for an estimate, not a guaranteed countdown.

## Production-path games

The first white game followed `1.e4 e5 2.Nf3 Nc6`. The theory suggestion was
`3.Bb5`; a deep “why?” question returned the grounded Emms reference and the
multi-branch Stockfish explanation. After playing `Bb5`, the coach selected
`...a6`, identified the Morphy Defense, and suggested `Ba4`. This was the path
that exposed the over-broad claim anchor and caused the final compiler guards.

Undo then removed the learner's `Bb5`, the coach's `...a6`, and the later
`Ba4` question together, restored the position after `2...Nc6`, and preserved
the earlier `Bb5` question because it had been asked before the move. This is
the intended complete-turn and feed behavior.

A second game started with the learner as Black. The coach chose `1.Nf3` and
correctly said that this move begins the Zukertort Opening. After `...d5 2.g3`,
the suggestion endpoint returned theoretical `...c5` and identified the King's
Indian Attack: Sicilian Variation. This also confirmed that opening recognition
and suggestions were not coupled only to the Ruy Lopez test path.

## Conclusion

The experiment achieved a real source-backed improvement for `Bb5`, but its
most valuable result was the rejected `Ba4` citation. Legal reconstruction,
relevant claim binding, and faithful German synthesis are three separate gates.
The final system can pass the first two, catch an LLM failure at the third, and
still present the supported remainder rather than either inventing an answer or
discarding everything.
