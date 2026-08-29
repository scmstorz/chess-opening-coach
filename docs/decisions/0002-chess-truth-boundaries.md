# ADR 0002: Separate legality, theory, and engine quality

- Status: accepted
- Date: 2026-08-29

## Decision

Store and communicate legality, opening-theory membership, and Stockfish quality
as independent facts. Never collapse them into one `correct` boolean.

## Rationale

A move can be legal and objectively strong without appearing in the current
opening data. Conversely, a theoretical move can be less preferred by a shallow
engine search. The learner must understand these distinctions rather than being
punished for harmless deviations.

## Consequences

Only materially relevant engine loss triggers forced correction. The UI can say
"playable but unusual" without calling the move bad. Interaction logs remain
useful for later analysis of theoretical knowledge versus chess mistakes.

