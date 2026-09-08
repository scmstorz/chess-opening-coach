# Cloud chess-explanation comparison: Kimi and DeepSeek

Date: 2026-09-08

## Question

Can a stronger cloud model turn verified Stockfish variations into a useful
medium- and long-term explanation without inventing chess claims?

The learner explicitly authorized one comparison using the locally configured
Kimi and DeepSeek accounts. GLM was excluded because that account currently has
no credit. Only FENs, focus moves, questions, evaluations, and principal
variations were sent. API keys remained in the local process and were neither
printed nor copied into this repository.

## Method

`benchmarks/cloud_chess_explanations.py` reconstructs three positions reported
by the learner:

1. `a4`, where the old answer listed pawn geometry but not its purpose;
2. `Nd5`, where the old template falsely implied that the central destination
   was not central;
3. `Ra6`, where a shallow analysis had made a cryptic move the teaching premise.

Each case receives a fresh Stockfish 18 comparison with four candidates and a
five-second deep budget. Both models receive the same evidence and are asked to
correct the premise if the focus move is not best, distinguish engine findings
from interpretation, avoid trivial pawn rules, and give a short German plan.

The provider model endpoints reported Kimi K3 and DeepSeek V4 Pro as the
strongest general models available on the configured accounts. Thinking mode
was disabled for the final comparison: with thinking enabled, 700 and even
2,500 output tokens could be consumed entirely by hidden reasoning, producing
empty or truncated learner-facing answers.

## Final latency

| Case | Kimi K3 | DeepSeek V4 Pro |
| --- | ---: | ---: |
| `a4` | 14.57 s | 6.96 s |
| `Nd5` | 6.48 s | 11.02 s |
| `Ra6` | 8.59 s | 7.66 s |

These measurements exclude the local Stockfish preparation. They support an
estimated rather than promised countdown.

## Quality findings

Both models substantially improved fluency and tried to answer the intended
question about plans. Both also correctly downgraded `Ra6` from “best move” to a
playable alternative when the deeper scores did not rank it first.

Neither model was safe enough to write directly into the product:

- Kimi described the a-file after `a4` or `Ra6` too freely and introduced plans
  beyond what the supplied principal variations established.
- Its `Nd5` answer selected a particular pawn recapture that was not established
  as the relevant continuation in the supplied evidence.
- DeepSeek's `Nd5` answer contained concrete board-history and pawn-blocking
  claims that do not follow from the FEN.
- DeepSeek's `Ra6` explanation invented coordination claims between the rook,
  queen, and queenside pieces that were not supported by the engine lines.

The result is not that cloud models are useless. They are good candidate-plan
generators and stylistic editors. The result is that eloquent strategic prose is
still probabilistic chess content and therefore needs claim-level verification
or trusted annotated source material.

## Decision

Cloud prose is not integrated into the runtime yet. The product keeps its
offline-first deterministic explanation path and adds a local `Tief erklären`
mode that exposes only board-verifiable patterns and labeled inferences across
multiple Stockfish lines.

A future cloud provider may propose structured claims such as `restrains_b5`,
`temporary_transfer_square`, or `prepares_d4`. The core must validate each claim
against board geometry, repeated principal variations, or curated repertoire
annotations before rendering it. A well-annotated opening source is likely more
valuable than asking a second unverified model to merge the first model's prose.
