# ADR 0003: Local Lichess opening graph with explicit provenance

- Status: accepted for MVP
- Date: 2026-08-29

## Decision

Build opening recognition and local theory candidates from the CC0
`lichess-org/chess-openings` TSV files. Retain the exact source commit and
license in the repository.

## Rationale

The dataset supplies machine-readable ECO codes, names, move sequences, and
transposition-oriented named positions. It is more reliable for identity than
LLM memory and small enough for offline startup.

## Consequences

Line coverage is only a proxy for move popularity. A later, consent-based online
refresh or cached Opening Explorer snapshot can add rating- and time-control-
aware frequencies. Stockfish filters selected candidates in the meantime.

