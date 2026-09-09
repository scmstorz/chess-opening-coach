# ADR 0007: Anchor book commentary only to verified displayed positions

- Status: accepted
- Date: 2026-09-09

## Context

The second local source, Paul van der Sterren's *Fundamental Chess Openings*, is
a 1,252-page Kindle-oriented PDF with 13,102 positioned text blocks, many
diagrams, and move tables typeset as separate columns. The first compiler
recognized its prose and section hierarchy but no exact positions because the
tables use `1 e4 e5 2 Nf3` rather than PGN punctuation.

Normalizing these tables made 213 complete lines legal from the initial
position. A naive implementation attached the surrounding chunk to every prefix
of every legal line. This produced a dangerous false retrieval: a Panov Attack
paragraph containing an embedded comparison to `1 d4 d5 2 c4` appeared as an
exact source for the early Queen's Gambit position.

The book also contains thousands of reasonable variation fragments whose start
position is supplied by a diagram or previous page. Without reconstructing that
context, their SAN may be syntactically clear but is not tied to a unique board.

## Decision

- Normalize typeset leading move tables to PGN-like notation and validate them
  with `python-chess`.
- A legal line creates one position anchor: its final position. It does not
  create anchors for every prefix.
- Only a displayed line beginning within the first 80 characters of a chunk can
  anchor that chunk. Legal embedded comparison lines remain searchable but are
  recorded as non-anchoring information.
- Concrete SAN found in prose is retained as `unverified` until its starting
  position can be reconstructed. It is not normal tutor evidence merely because
  the move is plausible.
- Retrieval checks the position after the questioned move before the current
  position. If exact-position claims are available, it stops before adding
  broader opening or keyword matches.
- A section-wide opening match may provide a general plan, but not a
  variation-specific recommendation or warning.
- Books remain separate evidence sources. An exact source outranks agreement by
  vaguely related passages from several books.

## Rationale

The text immediately following a displayed diagram line normally explains the
resulting position. Its earlier prefixes merely reconstruct how the diagram was
reached. Treating every prefix as the subject of the prose creates convincing
but contextually false explanations - the exact failure this project is
designed to prevent.

The final-position rule loses some recall, but its failures are visible and
honest. The alternative silently converts layout coincidence into chess truth.
Context-aware continuation parsing can later recover more positions without
weakening the safety boundary.

## Consequences

- The second book contributes 55 high-confidence final-position anchors from 213
  legal complete lines in the first compiler pass.
- 3,516 fragments requiring a previous position and 158 legal embedded lines
  are retained for later contextual reconstruction rather than discarded.
- A tested Queen's Gambit Declined position retrieves Van der Sterren's exact
  page-17/18 development explanation and ignores a superficially matching Panov
  paragraph.
- The initial `Bb5` position is recognized from the typeset Ruy Lopez table, but
  the introductory passage does not provide a sufficiently specific safe plan
  claim for `Bb5`; the coach must not pretend otherwise.
