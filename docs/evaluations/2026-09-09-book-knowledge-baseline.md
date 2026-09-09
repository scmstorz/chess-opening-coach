# Book-knowledge baseline and first vertical-slice evaluation

- Date: 2026-09-09
- Source: *Chess Openings For Beginners*, Clyde Stewart (2021)
- Local source SHA-256: `b8a5dfb39bab9d8aaa972f4d13eb5b23afeda1ce4d36a3a5c93e86107c884fbe`
- Runtime model: `qwen3.8:27b-mlx` through local Ollama
- Engine: Stockfish 18

## Why this evaluation exists

The learner asked for both a durable whole-book knowledge compiler (outcome A)
and noticeably better answers to actual “why?” questions (outcome B). The two
outcomes are evaluated separately so a technically successful import cannot
hide weak teaching, and a good one-off answer cannot hide missing provenance.

## Before-state cases

The regression set comes from live learner objections rather than synthetic
prompts:

| Case | Observed failure | Required improvement |
| --- | --- | --- |
| `c3` | Expanded detail repeated the summary and an unexplained phrase about permanently fixing squares. | State one concrete, position-relevant consequence or admit that no useful causal explanation is known. |
| `Na2` | Claimed the rim knight develops toward central squares although `Na2` attacks none of the four center squares. | Derive geometry from the board and explain the immediate positional purpose. |
| `a4` | Listed pawn attack squares and generic irreversibility without a longer-term lesson. | Explain the intended structure or plan, not a rule the learner already knows. |
| `Nd5` | Enumerated attacked squares and pieces but did not explain why the outpost matters. | Relate concrete effects to a stable purpose and distinguish fact from interpretation. |
| `Ra6` | Said only that the rook moves to `a6`, controls no center square, and is Stockfish's best move. | Explain a verified continuation or state the knowledge boundary. |
| `Bb5` | Engine facts did not connect the move to the Ruy Lopez's central pressure. | Combine a cautiously attributed opening plan with the board fact that `Bb5` questions the defender of `e5`. |

Each answer is assessed on strategic relevance, source faithfulness, board
consistency, actionable learning value, and honesty when evidence is
insufficient. Evaluation numbers alone do not define success; the exact output
and rejection reason are retained as evidence.

## Outcome A: whole-book compiler

The first real import completed without OCR:

- 122 PDF pages
- 962 positioned spans
- 67 reconstructed sections
- 100 searchable chunks and 100 synchronized FTS rows
- 399 extracted claims
- 1 valid numbered chess line, yielding 3 exact position-evidence rows
- 38 extracted images, 31 classified as likely board diagrams
- 70 review issues instead of silent promotion of uncertain material

Integrity checks reported `ok`, no foreign-key errors, no orphaned position
evidence, synchronized FTS content, and indexed position and issue queries.
Repeated import is idempotent in the synthetic integration test.

The Ruy Lopez query retrieves the exact section on PDF pages 18–20 before the
Italian and Scotch sections. The safe plan prefix on PDF page 20 is retained as
`source_only`; the full sentence containing natural-language move fragments is
separately retained as `unverified`.

## Source-quality finding

The first source inspection disproved the assumption that a chess book can be a
single undifferentiated “source of truth”. It is authoritative for what the
author wrote, but some content is not reliable chess truth. Examples discovered
during visual and text inspection include arithmetic that combines 38% and 25%
into a claimed 75% chance, and malformed opening descriptions such as “King's
pawn to e2”. These findings justify claim-level status, issue quarantine, and
separation from `python-chess`, the opening graph, and Stockfish.

## Outcome B: first grounded `Bb5` explanation

The initial local synthesis exposed three successive grounding failures:

1. the model produced truncated or malformed JSON under a too-small output
   budget;
2. it cited a book fact for the concrete `Bb5` anchor without citing the
   verified board fact;
3. after anchor repair, it over-generalized an opening-level book purpose into
   the direct claim that `Bb5` itself disrupts the opponent's pawn structure.
4. it later placed a supported translation and an unsupported strategic
   expansion into the same nominal JSON field; the critic correctly rejected
   the block, revealing that schema fields are not the same thing as sentences.

The second LLM evidence critic accepted the third formulation. This is negative
evidence against treating model agreement as proof. The implementation now
enforces actual sentence splitting plus deterministic constraints: source-only prose needs explicit
attribution, an opening-level claim cannot be attached to a move notation, and
concrete anchors need an unambiguous verified fact.

The first accepted local synthesis separates both layers:

> Das Buch beschreibt, dass die Eröffnung zwei Hauptzwecke verfolgt: die
> Bauernstruktur des Gegners zu stören und schnell das zentrale Territorium zu
> übernehmen.

The separate verified board explanation says that `Bb5` attacks the knight on
`c6`, which also defends the pawn on `e5`; this questions a defender of the
central pawn without claiming that the pawn is won automatically. The browser
shows the German explanation plus title, author, year, PDF page, and validation
status, but not the English excerpt or a local filesystem path.

This is a meaningful improvement for the `Bb5` case, not yet proof of general
quality across the six-case set. `c3`, `Na2`, `a4`, `Nd5`, and `Ra6` remain in
the evaluation corpus for the next source and retrieval iterations. When no
supported plan is available, an explicit knowledge-boundary response is the
correct result.

The final full-path check—real retrieval, Stockfish, local Qwen generation,
sentence filtering, critic, and response serialization—returned `grounded`,
used only `book:claim:48`, and exposed the source as Stewart (2021), PDF page 20.
Retrieval facts are atomic claims rather than concatenated chunk summaries, so
the weak page-18 phrase “keep blacks at a disadvantage” was not mixed into the
accepted page-20 plan.

## Deferred work

- human rating of all six before/after answers;
- more reliable sources and multi-book comparison;
- OCR only for pages whose text layer is inadequate;
- diagram-to-FEN reconstruction;
- embeddings after FTS and aliases have a measured recall failure;
- cloud processing of book excerpts, which is not authorized by the current
  privacy decision.
