# ADR 0001: Local browser UI with a Python sidecar

- Status: accepted
- Date: 2026-08-29

## Context

The learner wants a graphical drag-and-drop board, local Stockfish, local Ollama,
SQLite learner history, and clear handling of already occupied development
ports.

## Decision

Use a React browser UI and a separate local FastAPI process. A launcher uses
stable loopback ports and the web server proxies `/api` to Python. The default
browser URL is `http://localhost:53687/`; explicit environment variables allow
a deliberate change.

## Rationale

The browser provides a lower-effort cross-platform GUI than a native desktop
tool. Python has mature chess, UCI, and SQLite support. Keeping the engine and
database outside browser code preserves the truth boundaries and local access.

## Consequences

Two processes run locally, but one command manages them. The frontend build can
be validated independently. Hosting is deliberately not supported by this
architecture because local engine and model access are product requirements.

## Amendment, 2026-08-30

The first implementation selected fresh free ports at every launch. Manual
browser testing showed that avoiding all conflicts this way made ordinary page
reloads and bookmarks unnecessarily frustrating. Stable high ports now take
priority. Availability is still checked before processes start, preserving a
clear failure mode without silently changing the URL.
