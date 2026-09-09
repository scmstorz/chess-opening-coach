# ADR 0011: Reconstruct progressive annotated moves only from unique verified context

- Status: accepted
- Date: 2026-09-09

## Context

John Emms' *Discovering Chess Openings* is unusually useful pedagogically, but
its converted PDF often alternates one numbered move, explanatory prose, the
next numbered move, and a diagram. The existing compiler could validate compact
move lists and some adjacent fragments. It found only seven high-confidence
position anchors in the 363-page book and therefore could not safely connect the
strong explanation of `3.Bb5` to the position after that move.

Increasing full-text recall would not solve the problem. A passage can mention
the right opening and move while describing another position or variation. An
LLM can make that association sound convincing but cannot prove the underlying
board transition.

## Options considered

1. Retrieve nearby prose by opening name and SAN alone. Rejected because
   lexical relevance is not position identity.
2. Ask the LLM to infer missing moves and positions. Rejected because this
   would make the model a source of chess truth.
3. Reconstruct every diagram before using the prose. Deferred because reliable
   diagram recognition is a separate, larger capability.
4. Add a narrow deterministic parser for progressive annotated moves and fail
   closed whenever context is not unique.

## Decision

Choose option 4.

An isolated numbered move is accepted only when:

- an already verified line in the same chunk or immediately preceding chunk
  supplies its starting FEN;
- move number and side to move exactly match that board;
- `python-chess` parses the SAN as a legal move;
- at least one further numbered legal move confirms a sequence rather than a
  lone mention; and
- the longest legal continuation is unique. Equal alternatives, search-limit
  exhaustion, or competing parents create an issue instead of an anchor.

Every accepted transition stores its parent line, start and end FEN, UCI and
SAN, absolute ply range, source offset, PDF page, and the explicit context
method `progressive_annotated_move`.

Claims are bound more narrowly than chunks. A claim may use the position after
the most recent accepted move only within the same PDF text block or the next
block. Intervening numbered moves break that relation unless the claim
explicitly names the focus move. A sentence ending in an ellipsis before the
next move may be joined to that verified reply and the first following sentence;
this preserves constructions such as “if Black reinforces with ... 3...d6”
without inventing the missing move.

Position-bound claims are returned only for their exact position. If an exact
progressive anchor has no safe claim, retrieval does not replace it with broad
opening prose. Multiple distinct plan claims may be supplied for one exact
position, but broad retrieval retains its stricter deduplication.

The local LLM remains downstream. Its deterministic anchor checks run first,
then a second local critic reviews every generated sentence. If the critic
marks one sentence unsupported, only that sentence and its evidence links are
removed; supported sentences survive. If nothing book-supported remains, the
whole synthesis is rejected.

## Consequences

The final Emms import contains 73 accepted progressive half-moves, 81 position
evidence rows representing 76 distinct positions, and 13 position-bound claims,
of which nine are safe for normal tutor use. Fifty-one chunks remain explicitly
ambiguous. These lower final numbers are preferable to an earlier permissive
iteration with 102 progressive moves and 110 anchors.

That permissive iteration attached an Archangel-variation naming sentence to
`Ba4` merely because both occurred later in one large text block. Production
dogfooding exposed the mistake. Transition deduplication, text-block distance,
and intervening-move boundaries removed the false claim while retaining the
verified `Ba4` position itself.

The `Bb5` quality case now retrieves two exact, legality-checked Emms claims from
PDF pages 54-55. Qwen once reversed the actor in the conditional pin explanation;
the sentence-level critic rejected precisely that sentence. The remaining
book explanation, deterministic board effects, and Stockfish plan branches stay
visible and source-linked.
