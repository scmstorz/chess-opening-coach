# ADR 0012: Capture low-friction human explanation feedback as evidence, not truth

- Status: accepted
- Date: 2026-09-09

## Context

Automated checks can prove that a move is legal, that an engine payload is
internally consistent, and that a generated sentence is linked to allowed
evidence. They cannot prove that an explanation actually helps this learner
understand a position. Several important defects in the project—duplicate
details, the false `Na2` centre claim, and explanations aimed at immediate
geometry instead of long-term purpose—were found only through live learner
objections.

Relying on chat recollection makes those observations hard to reproduce. Saving
only a thumbs-down count would identify dissatisfaction but lose the exact
position, answer, engine result, source, and model needed to diagnose its cause.

## Options considered

1. Use a binary thumbs-up/thumbs-down control. Rejected because it cannot
   distinguish a likely factual error from a correct but unhelpful explanation.
2. Require a written report for every weak answer. Rejected because it would
   interrupt a turn-by-turn learning loop and suppress useful feedback.
3. Use a five-star scale. Rejected because the middle values do not map cleanly
   to the next engineering action.
4. Add `Hilfreich`, `Unklar`, and `Falsch`, plus an optional note, and preserve
   the complete explanation context locally.

## Decision

Choose option 4.

Every coach-feed message has a session-unique UUID and a position FEN. One click
immediately upserts one of three ratings. `Unklar` and `Falsch` automatically
open a note field because these cases benefit most from a reason; the note
remains optional. `Hilfreich` stays a true one-click action but also permits a
note.

The local `explanation_feedback` table stores the rating and note together with
snapshots of:

- session, message, timestamp, position, opening, question, and move;
- short answer, expanded sections, source, and model;
- Stockfish payload, knowledge status, and public book-reference metadata.

It deliberately does not copy private source passages or PDF paths. One record
per `(session_id, message_id)` is revisable. Its creation time remains fixed and
its update time records the latest judgment.

The in-app review list shows unclear and wrong snapshots, and the local endpoint
can filter ratings. An export script writes those cases to the Git-ignored
`outputs/` directory. Export does not promote
anything automatically: a human must decide whether a case demonstrates wrong
chess content, poor pedagogy, inadequate source coverage, context resolution,
or preference before changing a regression expectation.

Feedback survives a later chess undo. Undo removes the turn and visible response
from the active session, but the rating remains evidence about an artifact that
was genuinely shown. Its snapshot is sufficient for later reproduction.

SQLite remains the source of truth. Browser storage and cloud persistence were
rejected for these records because the product is offline-first, single-user,
and already has a local learner database. The hosting configuration therefore
keeps its D1 binding unset.

## Consequences

The quality loop is now part of the product rather than an informal exchange:
play, read, judge, review, reproduce, fix, and only then add a regression case.
The three states also create distinct useful metrics: perceived utility,
pedagogical ambiguity, and suspected factual failure.

The learner can still misclassify an answer. A `wrong` click must never override
python-chess, Stockfish, repertoire data, or grounded book evidence without
review. Conversely, a `helpful` click is not proof that every claim is true.

Active sessions are still in memory and are not resumable. Ratings persist, but
the interface does not yet include a visual review dashboard or a workflow for
accepting an exported candidate into the regression corpus.
