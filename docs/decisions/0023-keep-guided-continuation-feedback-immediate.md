# ADR 0023: Keep guided continuation feedback immediate

- Status: accepted
- Date: 2026-09-26
- Follows: ADR 0022

## Context

The first live `...e6` Sicilian lesson continued correctly after `5.Nc3`, but
the browser kept showing “Coach prüft den Zug” for several seconds after a
suggested move was played. The suggestion's Stockfish analysis was cached for
the played move. The new delay came from the ordinary free-play feedback path,
which asked Ollama to paraphrase the learner and coach messages synchronously.
The local health check reported that the most recent paraphrase failed
grounding and was discarded. In the recorded lesson, the first free coach
reply took about 11 seconds after the learner's move was recorded; later
replies took about 4 seconds. Both returned deterministic text.

## Decision

Once an authored guided segment becomes free play, automatic move feedback uses
the complete, verified deterministic draft directly. This applies to learner
feedback, correction messages, and coach replies. Stockfish still evaluates
moves and protects the coach's move choice. Explicit questions still use the
existing tutor and verified-fact flow. Ordinary free-play sessions retain their
existing paraphrase behavior.

The browser gives guided continuation its own five-second initial progress
estimate, including the turn that crosses the teaching boundary. Later local
measurements refine that estimate as before.

## Consequences

The continuation no longer waits for an optional rewrite that may be rejected.
Its move explanations remain the same verified summaries and details that were
previously shown on fallback. A regression test makes the tutor throw if
automatic feedback calls it, then plays the `...e6` lesson, requests a free
move suggestion, and plays it. An isolated real-Stockfish replay measured
0.48 seconds for the boundary hint and move, and 0.24 seconds for a suggested
free move and automatic reply; these are local measurements, not a guaranteed
response time on every machine or position.
