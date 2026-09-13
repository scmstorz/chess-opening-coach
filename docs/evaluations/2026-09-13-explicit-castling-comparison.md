# Explicit castling comparison regression — 2026-09-13

## Learner report

The learner asked:

> Warum war bei mir gerade eben die große Rochade besser als die kleine?

The application answered that Stockfish preferred `O-O-O`, repeated generic
castling properties, and compared `O-O-O` with `h4`. The learner judged the
answer to have practically no value because it never analyzed the named
alternative `O-O`.

## Reconstructed evidence

The persisted session gave this sequence:

```text
1. e4 c5 2. Nf3 e6 3. d4 cxd4 4. Nxd4 a6 5. c4 Qc7
6. Nc3 Be7 7. Be3 Nf6 8. Be2 Bb4 9. Qb3 Bc5 10. g4 h6
11. O-O-O
```

The position immediately before White's eleventh move was:

```text
rnb1k2r/1pqp1pp1/p3pn1p/2b5/2PNP1P1/1QN1B3/PP2BP1P/R3K2R w KQkq - 0 11
```

A longer Stockfish 18 check consistently separated the castlings by well over
one pawn, although exact values varied with each bounded run. Representative
lines were:

```text
O-O-O  about +1.0: O-O-O Nc6 h4 ...
O-O     below  0.0: O-O h5 gxh5 Nxh5 ...
```

The useful explanation is therefore causal and position-specific:

- White's g-pawn is already on `g4`, so short castling places the king on `g1`
  behind a pawn cover that has moved forward.
- Black can immediately use `...h5` to attack `g4` and prepare open lines on
  the same flank as that king.
- Black's queen on `c7` already sees `h2` along the diagonal.
- Long castling moves the king to `c1`, away from this lever; White can then use
  `h4` to restrain `...h5` without loosening the shelter of its own king.
- Both moves connect the rooks. That true statement does not distinguish them.

## Root cause and correction

The German phrase resolver found “große Rochade” but not the elliptical “die
kleine”. Without an explicit comparison target, the engine layer supplied its
next leading candidate, `h4`. The correction recognizes both natural castling
names through the legal move set, makes the second named move a required engine
root, and automatically uses the common depth-24 comparison for A-versus-B
questions.

A castling-specific fact builder then checks the advanced g-pawn, the verified
`...h5` reply, the queen attack on `h2`, and the rook files. Only its direct
conclusion may become the visible short answer. Focus and requested alternative
are shown before other engine candidates. A real `qwen3.8:27b-mlx` run selected
that same conclusion without error, but added roughly 45 seconds and no new
permitted information. The final narrow path therefore bypasses both LLM
selection and broad book retrieval.

## Verification

The machine-readable fixture requires the answer to mention the king squares,
the `g4` pawn, `...h5`, the `c7–h2` queen pressure, the rook on `d1`, and the
explicit `O-O` comparison. It forbids comparison with `h4`, the generic castling
template, and the former attacked-piece list.

The focused service suites pass 28 tests, and the complete backend suite passes
107 tests. A normal explicit-comparison run with Stockfish 18 produced a
depth-24 comparison in about 11.4 seconds on the development machine. Its short
answer identified the `g4`/`...h5`/`g1` contrast, and its raw candidate lines
displayed both `O-O-O` and `O-O`. The full deep quality benchmark also passed in
15.19 seconds; it additionally checked three plausible replies after `O-O-O`
and found `h4` in all three continuations. Exact centipawn values are not
asserted because bounded engine searches can vary. A final normal-path run with
an intentionally unreachable tutor still returned the complete answer in 10.18
seconds, recorded no tutor error, and reported
`explicit_castling_comparison_takes_priority`; this confirms that the LLM and
book layers are genuinely bypassed rather than merely ignored afterward.
