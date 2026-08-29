# ADR 0001: Local browser UI with a Python sidecar

- Status: accepted
- Date: 2026-08-29

## Context

The learner wants a graphical drag-and-drop board, local Stockfish, local Ollama,
SQLite learner history, and robust handling of already occupied development
ports.

## Decision

Use a React browser UI and a separate local FastAPI process. A launcher chooses
free loopback ports and the web server proxies `/api` to Python.

## Rationale

The browser provides a lower-effort cross-platform GUI than a native desktop
tool. Python has mature chess, UCI, and SQLite support. Keeping the engine and
database outside browser code preserves the truth boundaries and local access.

## Consequences

Two processes run locally, but one command manages them. The frontend build can
be validated independently. Hosting is deliberately not supported by this
architecture because local engine and model access are product requirements.

