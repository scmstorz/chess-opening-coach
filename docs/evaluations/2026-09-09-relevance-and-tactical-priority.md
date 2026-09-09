# Relevance and tactical-priority regression

- Date: 2026-09-09
- Scope: source-card aggregation, book relevance, move clarification, and direct tactics
- Status: implemented and verified

## Learner observations

Three source cards for passages from the same book made the expanded answer
look more authoritative but did not help the learner. In a separate `c4`
question, the first book sentence described Black's Dutch Defense strategy even
though the learner was White. The persisted pre-move FEN later identified this
as a Modern Defense position, confirming that the failure crossed both opening
family and side-to-move boundaries.

The sharper failure occurred after:

```text
1. e4 g6 2. d4 Bg7 3. Nf3 d6 4. c4 Bg4
5. Nc3 Nc6 6. d5 Nd4
```

The learner asked why `Kf3xKd4` was not good. The service failed to parse this
non-standard, internally contradictory notation and instead explained the
unrelated suggestion `Be3`. Even that longer answer missed the position's
decisive fact: `Nxd4` vacates `f3`, so `...Bxd1` wins the white queen.

## Failure classification

- The source-card issue was information architecture, not provenance loss.
- The `c4` issue combined overly broad FTS fallback with missing actor/perspective
  filtering.
- The `Kf3xKd4` issue was unsafe focus fallback after a parse failure.
- The weak tactical answer was a priority error: plan synthesis ran before an
  immediate board consequence had been promoted to the answer.

Adding another LLM would not address any of these causes.

## Implemented checks

1. Broad retrieval must retain the normalized opening family after FTS search.
2. Broad plan claims must match the focused side, unless the question explicitly
   asks about the opponent.
3. Actorless broad plans cannot justify a concrete focused move without an exact
   position anchor.
4. Coordinate-resolvable notation with contradictory piece letters produces a
   confirmation question.
5. Confirmation is tied to the same FEN and may be answered with a simple `ja`.
6. A newly opened immediate capture of the queen or rook overrides book and LLM
   layers.
7. Source references are grouped by book only at rendering time.

## Production-path result

The exact position was reconstructed with the real local opening graph,
Stockfish adapter, and book database. The first request returned:

```text
Meinst du Nxd4 – also, dass dein Springer von f3 den Springer auf d4 schlägt?
```

After `ja`, the response was:

```text
Nach Nxd4 kann Schwarz sofort mit Bxd1 deine Dame schlagen. Dein Springer auf
f3 hatte bis dahin die Diagonale g4–f3–e2–d1 blockiert.
```

The response was deterministic, contained no book reference, and recorded
`immediate_tactic_takes_priority` as its knowledge-path reason.

The earlier persisted `c4` FEN was also queried against the actual three-book
database with the opening family set to Modern Defense. The repaired path
retrieved zero claims rather than reusing the French, Bogo-Indian, or Dutch
passages that had appeared previously. This is an honest evidence gap and the
desired result.

Targeted backend tests cover the unrelated-defense exclusion, side filter,
explicit opponent-plan exception, clarification, affirmative continuation, and
queen-loss answer. The complete suite and frontend production build are run as
the final checkpoint for this increment. The final result is 83 passing backend
tests, a passing Ruff check, frontend lint, rendered-page test, production build,
and publication-safety scan. The latter checked 95 current and historical paths
and compared tracked text against 105 private-corpus variants without finding a
publication-boundary violation.
