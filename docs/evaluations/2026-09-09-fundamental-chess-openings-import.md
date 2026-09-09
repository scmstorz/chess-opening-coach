# Fundamental Chess Openings: import and first grounded evaluation

- Date: 2026-09-09
- Book: *Fundamental Chess Openings*
- Author: Paul van der Sterren
- Publication year: 2009 (explicitly stated in the PDF's publisher note)
- Local SHA-256: `cbbce0cd22bf4a7a060104ad55c21c865f30713e1bbb217e9dd792c37c32d355`
- Runtime model: `qwen3.8:27b-mlx` through local Ollama
- Engine: Stockfish 18

## Hypothesis

The second book has a strong reputation and appears far more systematic than the
first beginner source. The evaluation treats that as a hypothesis: better prose
should yield more precise long-term explanations, but only when the compiler can
attach it to the right position.

## Import result

| Metric | Result |
| --- | ---: |
| PDF pages | 1,252 |
| Positioned spans | 13,102 |
| Sections | 991 |
| Searchable chunks | 1,299 |
| Extracted claims | 2,268 |
| `source_only` claims | 712 |
| Quarantined claims | 1,556 |
| Legal complete lines | 213 |
| High-confidence final-position anchors | 55 |
| Recorded review issues | 5,508 |

The issue count does not mean the book contains 5,508 chess errors. Most are
valuable but contextual material that the first compiler deliberately refuses
to guess about: 3,516 variations require a prior position, 1,548 claims contain
unpositioned SAN, 263 natural-language move descriptions need context, and 158
legal embedded comparison lines are intentionally not position anchors. Only 14
detected lines are actually illegal from their assumed start.

The combined two-book database contains 1,399 chunks; FTS synchronization,
foreign keys, orphan checks, integrity checks, and indexed query plans all pass.

## Visual inspection

Ruy Lopez PDF pages 642-647 and Queen's Gambit Declined pages 17-18 were rendered
and inspected. Text, tables, page headings, diagrams, side-to-move labels, and
printed page numbers are legible and correctly aligned. PDF page numbers are two
pages ahead of printed page numbers in these sections, so citations continue to
use unambiguous PDF page numbers.

The visual layout explains the extraction challenge: move numbers and White and
Black moves occupy separate table columns, while the following prose comments on
the resulting diagram. The compiler now normalizes the displayed table but does
not pretend that later fragments have a known starting board.

## Retrieval failure that changed the design

The first table-normalization pass associated a legal embedded comparison from a
Panov Attack paragraph with the position after `1 d4 d5 2 c4`. That paragraph
then appeared as exact Queen's Gambit evidence even though its surrounding
commentary addressed a different opening.

The repair stores only the final position of a leading displayed line and asks
retrieval for the position after the learner's focus move. Exact facts terminate
the search before broad opening matches are added. The Panov paragraph no longer
appears.

## Positive end-to-end case: `2...e6`

Position: `1 d4 d5 2 c4`, asking why Black should play `2...e6`.

The displayed line on PDF page 17 ends after `2...e6`. The adjacent paragraph
states that Black holds ground in the centre and establishes a natural
development plan. The complete local path - position reconstruction, exact
retrieval, Stockfish, Qwen synthesis, sentence grounding, and source
serialization - returned `grounded` with one source claim.

The German explanation connected the attributed book plan to deterministic
facts: `e6` controls `d5` and `f5`, frees the bishop on `f8`, and permits a model
development with `...Nf6`, `...Be7`, and `...Nbd7`. The UI reference identifies
Van der Sterren, 2009, PDF pages 17-18, without showing the English excerpt or a
local path.

## Honest negative case: initial `Bb5`

The typeset Ruy Lopez table on PDF page 642 is now reconstructed correctly as
`1 e4 e5 2 Nf3 Nc6 3 Bb5`. However, its introductory prose mainly explains the
opening's history and the alternatives after `3 Bb5`; it does not directly give
a safe, specific long-term purpose for `Bb5` itself. The second book therefore
does not replace the existing board-derived explanation in this exact case.

This negative result is useful. A strong book is not automatically relevant to
every learner question, and retrieval must not substitute a nearby high-quality
paragraph for missing evidence.

## Recommended next increment

Do not add a third book yet. First reconstruct variation fragments from the most
recent verified diagram or displayed parent line. This should unlock much more
of Van der Sterren's strategic material while preserving exact position
provenance. Then rerun the real `c3`, `Na2`, `a4`, `Nd5`, `Ra6`, and `Bb5`
evaluation set before deciding which knowledge gaps actually require another
source.
