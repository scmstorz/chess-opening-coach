# Deep-explanation quality cycle

Date: 2026-09-09

## Goal

Turn the six explanation failures reported during real use into a repeatable
acceptance test, then improve book context, engine evidence, local-model use,
and the learner-facing detail layer against the same cases.

## Test corpus

The executable corpus is
`benchmarks/fixtures/explanation_quality_cases.json`:

| Case | Original risk | Required outcome |
| --- | --- | --- |
| `c3` | generic pawn prose; ignored attacked bishop | compare the explicitly named `Ba4`, show the unresolved attack and `...Nxb5` |
| `Na2` | false central-development claim | explain the attack on `c3`, counterattack on `b4`, and temporary square |
| `a4` | trivial pawn irreversibility | connect `a4` to restraining `...b5` and distinguish it from near-equal alternatives |
| `Nd5` | attacked-square list without purpose | identify the central post and whether a pawn can drive it away |
| `Ra6` | false “best move” premise | correct the premise and admit when no long-term purpose is supported |
| `Bb5` | vague Ruy Lopez association | separate the attributed opening plan from the verified attack on the `c6` defender of `e5` |

Two initially transcribed FENs made their focus move illegal. The runner rejected
them before analysis, and the fixtures were corrected from the documented source
positions. This is evidence that evaluation inputs need the same deterministic
verification as product inputs.

## Changes under test

- Contextual book lines are reconstructed only from one auditable nearby legal
  parent. The first pass resolves 79 fragments in *Fundamental Chess Openings*;
  3,437 context-dependent and 14 invalid lines remain blocked. High-confidence
  final-position anchors rise from 55 to 61.
- Deep Stockfish analysis now compares root moves and independently analyzes
  three plausible replies after the focus move. Recurring own-side moves are
  labeled as model-plan evidence, not engine-authored reasons.
- An explicitly named alternative is forced into the consistent comparison.
- Inferior moves no longer receive a post-hoc “plan” merely because Stockfish
  finds a recovery continuation.
- Without an opening identity, only exact position evidence may reach the book
  synthesizer. This removed irrelevant but superficially sourced `c3` and `Nd5`
  passages from unrelated openings.
- Ollama may select exactly one summary-eligible verified fact. Expanded
  sections remove verbatim summary duplication. Trivial newly opened slider
  squares are no longer promoted as teaching points.

## Runtime and result

The final acceptance run used Stockfish 18, local
`qwen3.8:27b-mlx`, the two-book SQLite corpus, and the production service path.
All six cases passed every automated guardrail. A cold run with local synthesis
observed roughly 22–42 seconds per case; cached engine evidence reduced the
repeated `c3` run to 10.43 seconds. These measurements justify the existing
learned estimate and “noch einen Moment” fallback rather than an exact timer.

Selected outcomes:

- `c3`: the summary says Stockfish prefers `Ba4`; the comparison explains that
  `c3` saves the pawn but leaves the more valuable bishop attacked, and a checked
  reply branch contains `c3 Nxb5`.
- `Na2`: the rim heuristic is explicitly treated as non-absolute; all three
  answer branches later reroute the same knight, and `Nc1` recurs.
- `a4`: the explanation says the pawn controls `b5`, making `...b5` answerable,
  while the engine difference to another strong move remains practically tiny.
- `Nd5`: the coach calls `d5` a central post and verifies that no opposing pawn
  can challenge it immediately.
- `Ra6`: the coach corrects “best move” to `...b5` and exposes a knowledge
  boundary instead of inventing a rook plan.
- `Bb5`: the book claim remains attributed; board logic separately explains
  pressure on the `c6` knight and therefore on the defense of `e5`.

## Interpretation and remaining limit

“6/6” means the known failure modes are now executable and guarded. It does not
mean every generated explanation is already ideal for every learner. In
particular, recurring moves can show that a follow-up is robust but not prove
that it is the sole purpose of the focus move. Human feedback remains the final
pedagogical signal, and new unsatisfying answers should become new corpus cases.

## Reproduce

```bash
.venv/bin/python benchmarks/explanation_quality.py
```

The benchmark uses local resources only. It writes no learner interactions;
only normal Stockfish cache entries may be reused.
