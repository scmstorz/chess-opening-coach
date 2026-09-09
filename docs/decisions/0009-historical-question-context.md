# ADR 0009: Bind follow-up questions to verified historical positions

Date: 2026-09-09

## Status

Accepted

## Context

The coach normally replies immediately after a learner move. The live board is
therefore already two plies beyond the position in which the learner made that
move. During a dogfooding game, the learner played `b3` and then asked why `b3`
was inaccurate. Because `b3` was no longer legal on the live board, the question
resolver silently selected the current suggestion `Bxc6` and produced a deeply
analyzed, cited answer about the wrong move.

This failure passed all chess, engine, book-provenance, and synthesis checks.
The facts were grounded in a position; the position itself was not the position
the learner had asked about. Adding another book or a stronger language model
would not repair that reference error.

## Decision

Accepted move messages remain the auditable transition history for an active
session. For a question that names a previous learner SAN/UCI move, or clearly
refers to the learner's last move, the service replays those verified
transitions from the initial position. It then runs theory, Stockfish, book
retrieval, and explanation generation on the board immediately before the
matched learner move.

An explicit UI focus move still applies to an unchanged current position. The
historical reconstruction does not change the live game, learner log, or undo
stack. If replay cannot establish a legal historical position, the resolver
fails closed and retains the current-position behavior instead of guessing.
A legal move rejected during the three-attempt correction loop is resolved on
the unchanged current board before historical lookup; it has not become a past
position merely because its feedback uses past-tense language.

The same dogfooding cycle also established two related precision rules:

- deterministic pawn explanations may state support of an existing pawn and
  newly freed bishop development when `python-chess` proves both effects;
- recommendation and warning claims from books require an exact reconstructed
  position. Broad opening, SAN, and question matches may contribute only
  attributed general plans.

## Consequences

- Natural questions such as “Why was `d3` sensible?” now refer to the actual
  earlier `d3` position even after the coach has replied.
- The answer can explain that `d3` supports `e4` and frees the bishop on `c1`
  without asking an LLM to invent the relationship.
- Active sessions still start at the normal initial position. A future custom-
  position training mode must persist an explicit initial FEN before historical
  replay can support it.
- Book retrieval becomes deliberately more conservative; some relevant but
  unpositioned recommendations will be withheld until their variation context
  is compiled.

## Rejected alternatives

- Analyze every follow-up against the current board and let the LLM infer what
  the learner meant.
- Use the most recent engine suggestion whenever a named move is no longer
  legal.
- Add a third opening book before testing the existing end-to-end learning loop.
- Treat an FTS match for a move name inside an opening chapter as sufficient
  evidence for a variation-specific recommendation.
