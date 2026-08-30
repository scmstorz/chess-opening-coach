# Local Ollama chess-model comparison — 2026-08-29

## Question

Do the locally installed Glimmer or Ornith models show more useful chess-opening
knowledge than the current `qwen3.8:27b-mlx` default?

This is an exploratory benchmark, not a definitive model ranking. Its purpose is
to catch obvious weaknesses and decide which models deserve broader evaluation.

## Models

- `muse-glimmer:30b-mlx`
- `ornith-1.5:35b`
- `qwen3.8:27b-mlx`
- `gpt-oss:20b` (follow-up run on 2026-08-30)

All inference ran locally through Ollama. No network source or retrieval context
was used.

## Method

The reproducible runner is `scripts/benchmark_ollama_chess.py`. It uses three
small tests:

1. Identify six common openings and state one central idea.
2. Answer seven objectively checkable multiple-choice questions about opening
   concepts. One question explicitly challenges the false premise that
   `1. e4 g6` is a King's Gambit line.
3. Rewrite the same verified feedback through the application's real grounded
   tutor adapter.

The knowledge prompts use temperature 0 and disable thinking. The production
rewrite keeps the application's current settings, including its JSON schema,
240-token output budget, and validator. Opening-name scoring accepts standard
English and German aliases after punctuation and accent normalization.

An initial benchmark version used an Ollama JSON schema for the knowledge test.
Glimmer and Qwen returned empty visible content for that combination, while a
plain JSON-instruction prompt worked. The knowledge prompt was therefore made
provider-neutral. Schema behavior remains represented by the real adapter test.

## Results

| Model | Opening names | Concepts | Current grounded adapter | Representative timing |
| --- | ---: | ---: | --- | --- |
| `muse-glimmer:30b-mlx` | 6/6 | 7/7 | Fallback; no parseable JSON within the current budget | 22.27 s identification including 7.59 s load; 23.85 s warm concepts |
| `ornith-1.5:35b` | 5/6 | 7/7 choices recovered from malformed JSON | Fallback; validator rejected the rewrite | 5.24 s warm identification; 4.67 s warm concepts |
| `qwen3.8:27b-mlx` | 6/6 | 6/7 | One accepted and one rejected run in this comparison | 13.88 s identification including 5.72 s load; 11.93 s warm concepts |
| `gpt-oss:20b` | 6/6 | 7/7 | Fallback; no visible JSON from the schema-constrained adapter | 21.90 s identification including 6.65 s load; 15.09 s warm concepts |

The multiple-choice total alone overstates answer quality. Manual review remains
necessary because a model can select the right option and then add a false
reason.

## Manual review

### Glimmer

Glimmer produced the strongest objective score and correctly rejected the
King's Gambit false premise. It also knew the standard names in all six lines.
However, some free explanations were imprecise: it said the Ruy López bishop
"pins" the c6 knight in this position and elsewhere described the knight as
being pushed back. Its Najdorf prose once claimed that `...a6` prevents
`...Nb4`, although the relevant square controlled by the a6-pawn is b5.

Glimmer is therefore the most promising candidate for a larger chess benchmark,
not yet a source of chess truth. Its verbosity and current structured-output
behavior need adapter tuning before it can replace the default.

### Ornith

Ornith selected all seven multiple-choice answers correctly, including the false
premise trap, but emitted malformed JSON. Its unconstrained explanations showed
more serious warning signs:

- an unsupported `Aix-la-Chapelle-Verteidigung` alias for `1. e4 g6`;
- the nonsensical phrase `Königsflängelhügel`;
- the false claim that Najdorf `...a6` controls c4;
- a malformed Queen's Gambit name;
- a misleading King's Indian description centered on a Black queenside pawn
  attack.

The local opening source contains an unrelated Aachen Gambit after
`1. e4 Nc6 2. d4 d5 3. exd5 Nb4`; it does not support Ornith's alias for the
Modern Defense. Ornith is fast when warm, but is currently the riskiest of the
three for learner-facing explanations.

### Qwen

Qwen was concise, followed JSON best overall, and remains the closest fit for
the current adapter. It nevertheless answered one concept question incorrectly:
in the French Advance, it said `...c5` attacks e5 instead of d4. In the separate
free-answer test it described this same idea correctly, demonstrating that one
successful prompt is not sufficient evidence of stable knowledge.

This adds to the already documented `1...g6`/King's Gambit hallucination from an
earlier live integration test.

### GPT-OSS follow-up

GPT-OSS produced valid JSON, recognized all six openings, and selected all seven
concept answers correctly. Its reasons also handled the tested squares and pawn
breaks accurately, including `...a6` controlling b5, `...c5` attacking d4, and
the false premise around `1.e4 g6`. This is the strongest combined raw score in
the benchmark, tied with Glimmer's 13/13 objective total but with valid JSON.

The real grounded adapter nevertheless returned no visible JSON content and
fell back to the deterministic answer after 0.47 seconds. This likely requires
model-specific investigation of schema and reasoning-output behavior before it
can be compared fairly as the production explainer. The result supports further
adapter work; it does not justify an immediate model switch.

## Provisional decision

Keep `qwen3.8:27b-mlx` as the application default for now because the grounded
adapter was tuned around it and it has the best current structured-output fit.
Treat `muse-glimmer:30b-mlx` and `gpt-oss:20b` as the leading candidates for
deliberate follow-up work and a possible model switch after:

- expanding the test to more openings and adversarial false premises;
- checking free-form explanations against curated reference concepts;
- testing several runs per prompt;
- tuning output budget and structured-output behavior;
- measuring complete per-move latency in the browser app.

Do not use any model's parametric chess knowledge as ground truth. Opening data,
python-chess, and Stockfish retain that responsibility.
