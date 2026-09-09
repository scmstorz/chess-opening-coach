# Publication boundary and John Emms import

- Date: 2026-09-09
- Source: *Discovering Chess Openings: Building opening skills from basic principles*
- Author: John Emms
- Publication year: 2006, stated in the book front matter
- Local SHA-256: `4b11602cfeb5040546750a9365f2786d1f9c21b9f62cff9e2d63473bcdc12b85`

## Why the work paused

The source was found in the learner's local `Documents/Books/Schach` library.
It had already been selected as the best next pedagogical complement when the
learner noticed a publication risk: an open-source repository must not become a
distribution channel for owned books or their compiled text.

The response was architectural rather than abandoning publication. A public
code product and a private local knowledge overlay are now explicit runtime and
release concepts. No PDF or database appears in the Git index or existing Git
history. A strict release check also found no 24-word source overlap in tracked
text.

## Source inspection

The original filename ended in `(2020)`, while the copyright page states that
the book was first published in 2006. Renaming the durable private copy without
the misleading suffix allowed the compiler to infer the supported year from
the front matter.

Rendered samples included the contents, introduction, central-control and
development material, early `Bb5` teaching, a Ruy Lopez `a4` pawn break, a main
Ruy Lopez overview, and an Open Sicilian example. Text and diagrams were clear.
The book's own stated audience and question-led method match this product more
closely than another opening encyclopaedia: it teaches how to reason when known
theory ends.

## Import result

| Metric | Result |
| --- | ---: |
| PDF pages | 363 |
| Positioned spans | 795 |
| Detected sections | 4 |
| Searchable chunks | 160 |
| Extracted claims | 352 |
| Valid or context-resolved book lines | 127 |
| Quarantined/contextual book lines | 445 |
| High-confidence final-position anchors | 7 |
| Detected likely board diagrams | 342 |
| Review issues | 859 |

The combined database now contains three books and 1,559 searchable chunks.
SQLite integrity, foreign keys, FTS synchronization, orphan checks, and indexed
query plans all pass.

## What the numbers mean

The source is pedagogically promising but exposes a new extraction layout. Many
pages alternate one move, explanatory prose, another move, and a diagram inside
one positioned PDF block. The current parser safely recognizes complete move
sequences but does not stitch isolated, interleaved half-moves through prose.
This explains the mismatch between 342 diagrams and only seven trusted position
anchors. The 859 issues are predominantly quarantined context, not claims that
the author's chess is wrong.

The book already improves broad full-text coverage for concepts such as the
timing of `c3`, pawn breaks, rapid development, and concrete purposes of `Bb5`.
It cannot yet be credited with improving the live `Bb5` answer because the
relevant page is not anchored to the position after `3.Bb5`. Treating nearby
excellent prose as exact evidence would repeat the retrieval mistake found in
the previous dogfooding cycle.

## Decision and next test

Keep the book in the private local corpus, but do not loosen retrieval merely to
make it appear useful. The next compiler increment should recognize progressive
annotated move sequences only when each isolated move is uniquely legal from
the preceding verified position. It must then rerun the existing `d3`, `Bb5`,
`Na2`, and `a4` cases before any claim of pedagogical improvement.

An immediate regression run used Stockfish 18, explicit
`qwen3.8:27b-mlx`, the three-book database, and the production service path for
the existing `Bb5`, `Na2`, and `a4` fixtures. All three retained every automated
guardrail. None exposed an Emms reference, which is the correct conservative
result while the relevant progressive lines lack exact position anchors. The
run proves no regression; it does not yet prove an explanation improvement from
the new source. Engine results were already cached, so the observed sub-second
times are not representative cold latency.

The proposed progressive increment has since been implemented and evaluated.
Its accepted and rejected intermediate results are recorded in
`2026-09-09-progressive-emms-and-dogfood.md`; ADR 0011 defines the final
fail-closed reconstruction and claim-binding rules.
