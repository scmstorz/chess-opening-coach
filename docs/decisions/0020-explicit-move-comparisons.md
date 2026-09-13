# ADR 0020: Preserve explicit move comparisons and explain castling safety concretely

- Status: accepted
- Date: 2026-09-13

## Context

A learner asked why their previous long castling move was better than short
castling. The answer said only that Stockfish preferred `O-O-O`, described the
generic effects of castling, and compared it with `h4`. Every individual
sentence was compatible with engine output, but the answer did not address the
question.

Two failures combined. The move resolver understood SAN, UCI, and coordinate
descriptions but not the natural German names “große Rochade” and “die kleine”.
It therefore found only the historical focus move `O-O-O`. The comparison layer
then selected the next engine candidate, `h4`, instead of the learner's intended
alternative `O-O`. A shallow forced-root fallback could also return an
evaluation for a non-leading move without enough principal variation to expose
the reason for the difference.

The position itself contained useful evidence. White's g-pawn had advanced to
`g4`. After `O-O`, Stockfish answered immediately with `...h5`, attacking that
pawn and preparing to open lines beside the king on `g1`. Black's queen on `c7`
also already attacked `h2`. After `O-O-O`, White's king was on `c1`, away from
that kingside lever. Both castlings connect the rooks, so that generic property
cannot explain the choice.

## Options considered

1. Let Ollama infer that “die kleine” means `O-O` and write the explanation.
   Rejected because legal move resolution and the comparison target are
   deterministic facts; delegating them would make a fluent answer hide another
   interpretation error.
2. Continue comparing the focus move with Stockfish's nearest top candidate.
   Rejected because the learner asked an A-versus-B question, not an open-ended
   best-move question.
3. Recognize natural castling names, force every explicitly named legal
   alternative into one deeper root comparison, and derive a narrow castling
   safety explanation from board geometry plus the verified engine line.
4. Always generate a broad strategic story for opposite-side castling.
   Rejected because the present evidence supports a concrete kingside pawn
   lever; a general story would again risk sounding useful without answering the
   actual position.

## Decision

Choose option 3.

The legal-move resolver maps German long/large/queenside and
short/small/kingside castling names to `O-O-O` and `O-O`, respectively. It still
accepts a move only when `python-chess` confirms that castling is legal in the
question's reconstructed position. Elliptical wording such as “die große ...
als die kleine” is supported when the sentence establishes that it is about
castling.

When a question names two legal moves, both become required roots in the
five-second, depth-24 comparison. This happens even without a separate click on
“Tief erklären”, because a shallow evaluation of the wrong alternative is not
an acceptable answer to an explicit comparison. The deeper follow-up-plan
analysis remains reserved for the explicit deep mode; only the common-root move
comparison is promoted automatically.

For the narrow case where long and short castling are compared, long castling
is objectively better, and the mover's g-pawn is already advanced, the service
constructs a direct verified explanation. It may cite an immediate opposing
h-pawn lever only when that reply occurs in the forced short-castling principal
variation and attacks the advanced g-pawn. Existing queen pressure on `h2`/`h7`
and the post-castling rook files are derived from the board. The output states
explicitly that connecting the rooks applies to both choices and therefore is
not the reason for preferring one.

The castling conclusion is the only fact eligible for the short answer. Because
the narrow path has no remaining content choice, it bypasses Ollama and book
retrieval just as a directly proved one-ply material loss does. A real Qwen test
selected the correct fact unchanged but added roughly 45 seconds without adding
information. The raw calculation prioritizes the focus move and the explicitly
requested alternative before other candidates, so neither disappears because
of a display limit.

## Consequences

Explicit comparisons take longer than ordinary shallow questions, but the
additional engine latency buys a common analysis depth and useful lines for both
named moves. The deterministic castling path avoids a second, much larger model
delay. The existing local duration history remains an estimate rather than a
guarantee; the response identifies this work as deep analysis.

The castling explanation is deliberately narrow. It does not claim that long
castling is generally safer, that an advanced g-pawn is always bad, or that an
engine score proves one unique strategic reason. Positions without the required
board and line evidence continue through the generic grounded comparison path.

The reported position is now a machine-readable regression in both the fast
explanation fixture suite and the end-to-end quality corpus. The regression
forbids the original `h4` substitution and generic “king safety/connect the
rooks” answer.
