# Explanation feedback loop — initial verification

- Date: 2026-09-09
- Scope: local capture, revision, review, and export of learner judgments
- Status: automated slice complete; live learner usability test pending

## Evaluation question

Can the learner flag an explanation without interrupting play, while preserving
enough exact context to reproduce and classify the problem later?

## Product hypothesis

A three-state control provides more actionable evidence than a binary rating:

- `Hilfreich` confirms perceived teaching value;
- `Unklar` identifies a pedagogy or missing-context problem without claiming the
  chess content is false;
- `Falsch` identifies a suspected factual or positional problem.

The interaction should take one click. A note should be available, especially
for negative ratings, but never required.

## Implemented evidence chain

1. Every feed message receives a stable session-local UUID and position FEN.
2. A click immediately writes one SQLite row or revises the existing row.
3. `Unklar` and `Falsch` reveal an optional note field; `Hilfreich` offers one
   after saving.
4. The stored snapshot includes move, opening, answer layers, Stockfish,
   knowledge status, public source metadata, and model.
5. The in-app review list shows negative snapshots; its API filters by rating
   and returns decoded structured payloads.
6. The export utility selects unclear and wrong cases by default and writes
   them under the Git-ignored `outputs/` directory.
7. Exported cases remain candidates until a human validates the diagnosis.

## Automated result

The API integration test created a position question, saved it as `unclear`
with a note, revised the same message to `wrong`, and verified that:

- only one record exists for the message;
- the revised label and note are present;
- FEN and focused UCI move match the questioned position;
- summary, expanded sections, and engine analysis survived as snapshots;
- filtered review returns the case;
- summary metrics count the current rating once; and
- a later chess-turn undo preserves the earlier explanation judgment.

The full backend suite reports 78 passing tests. Ruff, ESLint, and the production
web build pass. `EXPLAIN QUERY PLAN` confirms that filtered review uses
`idx_explanation_feedback_rating_updated` rather than scanning the table. These
checks establish data integrity and integration, not UI quality.

## Privacy and publication boundary

Feedback stays in `data/coach.db`, which is ignored by Git. The context contains
only rendered coach prose and public book-reference metadata, not retrieved
source passages or local PDF paths. Export output is ignored as well and must
not be treated as a publication-ready artifact.

## Required live follow-up

The learner should play normally and rate several different answer types:

- one routine move explanation as helpful;
- one long question answer as unclear, with a short reason;
- one suspected factual issue as wrong, then revise its note;
- one rated move response followed by `Zug zurück`.

Observe whether the controls clutter the already dense feed, whether the note
opens at the right moment, and whether “Unklar” versus “Falsch” feels natural.
Only live use can answer those questions.
