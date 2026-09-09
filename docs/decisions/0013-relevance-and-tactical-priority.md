# ADR 0013: Clarify contradictory move notation and prioritize immediate tactics

- Status: accepted
- Date: 2026-09-09

## Context

Live use exposed three different ways for a technically grounded answer to miss
the learner's question.

First, broad full-text retrieval treated the generic word `Defense` as enough to
combine plans from unrelated opening families. A later answer about White's
`c4` then led with a plan explicitly written for Black. The source attribution
was correct, but neither opening-family relevance nor actor relevance was.

Second, the learner described a candidate as `Kf3xKd4`. In international
notation `K` means king and `N` means knight. The source and destination squares
nevertheless described the unique legal move `Nxd4`. Because the existing
resolver understood only valid SAN or UCI, it ignored the phrase and silently
fell back to an unrelated highlighted suggestion, `Be3`.

Third, the board itself contained a decisive answer: moving the knight from
`f3` opens the bishop diagonal `g4-f3-e2-d1`, after which Black can immediately
play `...Bxd1` and capture White's queen. A general plan, opening label, or long
engine comparison is inferior to that direct causal fact.

The source display also rendered one card per evidence fragment. Several
fragments from one book therefore consumed substantial feed space without
adding useful provenance.

## Options considered

1. Let the local LLM infer the intended move and select the best explanation.
   Rejected because both notation resolution and the immediate capture are
   deterministic, while silent model inference hides uncertainty.
2. Always interpret any unique source/target pair, regardless of contradictory
   piece letters. Rejected because the learner explicitly wants the coach to
   teach notation and ask rather than guess.
3. Reject every non-standard string and require a complete rewrite. Rejected
   because the board often supports a precise, friendly clarification.
4. Use staged deterministic gates: resolve coordinates through legality, ask
   about contradictory designators, detect immediate material consequences,
   and consult plans or books only when those stronger answers do not apply.

## Decision

Choose option 4.

Verbose coordinate descriptions such as `Nf3xNd4`, `f3-d4`, or `f3 nach d4`
may identify a legal move. If a supplied piece designator contradicts the piece
actually present on either named square, the service returns a clarification
instead of running Stockfish or book retrieval. It stores the proposed legal
move together with the current FEN. A simple affirmative answer confirms it
only while the board is unchanged; otherwise the pending interpretation is
discarded.

After a move is unambiguous, `python-chess` checks whether vacating its source
square creates an immediate legal opponent capture of the mover's previously
unattacked queen or rook. This narrow detector requires the vacated square to
lie between the capturing slider and its target. When it fires, the direct
tactical sentence becomes the short answer. LLM selection and book retrieval
are skipped, because they cannot improve the truth or relevance of a one-ply
board fact.

Broad book retrieval now requires the normalized opening-family name to occur
in the source section. Generic terms such as `Defense` can no longer bridge
French, Dutch, and Modern chapters. A second filter removes broad plan claims
for the opponent when the learner asks why their side's focused move is useful.
Actorless broad plans are also excluded from focus-move rationale questions;
exact-position evidence remains eligible. Explicit questions about the
opponent's plan continue to admit opponent-side claims.

The browser groups used references by stable book ID. Overlapping or adjacent
PDF ranges are merged, disjoint ranges remain visible, and the most conservative
validation status is shown once with the number of contributing passages. The
individual source references remain unchanged in the service response and
feedback snapshot.

## Consequences

The coach now distinguishes “I can infer one likely move” from “the notation is
consistent.” This adds one conversational step in a malformed case but prevents
a confident answer to the wrong move and teaches the notation at the moment it
matters.

Immediate material tactics become shorter and faster: they do not incur Ollama
or retrieval latency and cannot be diluted by an opening plan. The detector is
deliberately narrow. It does not claim to explain all tactics, discovered
attacks, combinations, or long-term evaluation differences.

Book recall decreases when compiler section titles do not expose the correct
opening family or a broad claim does not identify its actor. This is the intended
fail-closed result. Improving the compiler's position anchors is preferable to
recovering recall with a generic defense match.

One compact source card is a presentation aggregate, not a provenance rewrite.
Diagnostics and persisted feedback still retain the claim-level references
needed for reproduction.
