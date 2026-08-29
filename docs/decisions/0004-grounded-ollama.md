# ADR 0004: Ollama may paraphrase but not originate chess verdicts

- Status: accepted after empirical failure
- Date: 2026-08-29

## Context

An initial live prompt gave Ollama structured engine and opening facts but asked
it to explain freely. It incorrectly described `1. e4 g6` as related to the
King's Gambit. The same experiment also showed substantial latency differences
and inconsistent JSON adherence across installed models.

## Decision

Generate a complete deterministic explanation first. Ask Ollama only to
paraphrase it for the learner. Reject generated output that adds opening
terminology or numeric facts outside the verified draft.

Use `qwen3.8:27b-mlx` as the preferred installed model unless an environment
variable explicitly selects another model.

## Consequences

The coach remains useful when Ollama is unavailable, slow, malformed, or
ungrounded. Some generated answers will intentionally fall back to deterministic
text. Future evaluation should expand semantic verification instead of relaxing
the boundary for smoother prose.

