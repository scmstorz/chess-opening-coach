# ADR 0008: Test deep explanations against multiple opponent replies

Date: 2026-09-09

## Status

Accepted

## Context

A single principal variation can show one concrete future but cannot establish
why a move is useful in general. Earlier explanations consequently turned one
line into a strategic story, listed square geometry, or defended a false premise
such as “`Ra6` is the best move”. A stronger cloud model improved prose but did
not remove unsupported chess claims.

The second local book improves source quality, but many of its numbered lines
are abbreviated fragments that depend on a preceding branch. Attaching those
fragments to a guessed position would create authoritative-looking false
evidence.

## Decision

`Tief erklären` separates two engine questions:

1. compare the focus move with leading and explicitly named alternatives from
   one consistently rechecked root set;
2. after the focus move, analyze three plausible opponent replies and retain
   only own-side follow-ups that recur across at least two branches.

Recurring motifs are described as cautious evidence for a robust follow-up
plan, never as Stockfish's stated reason or a forced continuation. If an
inferior move has a plausible recovery line, that line is not presented as the
move's purpose. A question that assumes a move is best is corrected whenever
the deep comparison disagrees.

The book compiler may resolve an abbreviated line only from one unique legal
position inside the nearest already verified parent line. The parent must be in
the same chunk, or an adjacent chunk in the same section and on a nearby page.
The inferred parent line, method, and absolute ply range are stored. Only the
fragment's final position may anchor surrounding commentary. Unresolved and
ambiguous fragments stay quarantined. Diagram recognition is deliberately not
used as a position source until it can produce independently verified FENs.

Retrieval also requires an exact position when no opening identity is known.
A bare SAN token such as `c3` or `Nd5` is too ambiguous to search globally
across books.

The six learner-derived cases form a permanent executable quality corpus. Its
checks cover the focus move, forbidden stock phrases, required concrete facts,
false-premise correction, non-empty evidence, and duplication between the
visible summary and expanded sections.

## Consequences

- Deep analysis performs an additional Stockfish search and can take tens of
  seconds on a cold local run.
- The learned browser countdown remains an estimate rather than a promise.
- Explicit comparisons such as “`c3` versus `Ba4`” now analyze and discuss that
  named alternative instead of silently substituting Stockfish's current top
  candidate.
- The first contextual compiler pass safely resolves 79 of 3,516 abbreviated
  lines in *Fundamental Chess Openings* and adds six final-position anchors.
  The modest yield is intentional: precision is more valuable than coverage.
- The first full local run passes all six automated guardrail cases. This is a
  regression result, not a claim that human teaching quality is solved.

## Rejected alternatives

- Treating one long principal variation as the explanation.
- Asking an LLM or an ensemble to infer unrestricted strategic prose.
- Resolving every contextual book line from the nearest superficially matching
  variation.
- Globally retrieving book passages from a move token without a position or
  opening identity.
- Showing the summary verbatim again inside the expanded explanation.
