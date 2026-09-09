# Case study outline

## Working title

**Keep the Chess Truth Outside the LLM: Building a Local AI Opening Coach**

## Narrative arc

1. A broad AI chess tutor idea is narrowed through one-question/one-answer
   discovery.
2. An early implementation starts too soon, is challenged by the user, and is
   removed before product decisions continue.
3. The learning experience is defined around every-move explanations, gentle
   correction, progressive hints, and learner control.
4. Deterministic chess tools and probabilistic pedagogy receive explicit
   boundaries.
5. A local browser architecture combines a usable board with Python chess tools.
6. Real model benchmarks expose latency and formatting trade-offs.
7. A live hallucination despite structured facts validates the grounding rule
   and changes the implementation.
8. The first vertical slice proves a full move cycle and records evidence for
   future learning features.
9. Hands-on use first improves an explicit start gate, then shows that the gate
   has no product value and removes it in favor of immediate play.
10. A requested move hint becomes another example of verified AI architecture:
    theory proposes, Stockfish checks, and the learner retains agency.
11. The hint immediately triggers a natural “why?” question, turning a disabled
    UI placeholder into the next grounded vertical slice.
12. Continued play exposes a product boundary disguised as a data boundary:
    ending local opening coverage must switch the hint to a clearly labeled
    Stockfish suggestion, not end the learner's access to help.
13. A technically longer expanded comment proves pedagogically empty when it
    repeats the summary; exact board effects and engine-line contrasts replace
    generic prose before considering a multi-model ensemble.
14. `Na2` exposes that even deterministic prose can be false when its template
    is too broad. Geometry derived from the live board reveals the real
    double-purpose move, while free Qwen and Ornith explanations demonstrate
    why LLM fluency still needs claim-level grounding.
15. A focused explanation-quality sprint turns isolated fixes into a reusable
    comparison pipeline: deeper MultiPV, forced analysis of the questioned
    move, board-effect deltas, structured evidence sections, and a growing
    regression corpus built from actual learner objections.
16. The first closed learning loop treats the end of an opening as a probable,
    explainable transition rather than a fixed move count: the learner chooses
    to continue or receives a grounded, locally persisted review.
17. Longer real play exposes a new failure mode: mechanically true square lists
    still do not answer a learner's long-term “why?”. A separate deep mode now
    compares future plans, while stable move selection prevents shallow engine
    choices from becoming bad teaching premises.
18. Kimi K3 and DeepSeek V4 Pro produce more fluent strategic prose, but both
    add unsupported or false positional claims. The benchmark rejects direct
    cloud prose as ground truth and preserves claim-level grounding.
19. The response to weak model explanations is not another model ensemble but a
    local knowledge compiler. Planning distinguishes a searchable, citable book
    corpus from the separate product outcome of better teaching, then makes both
    part of one staged and measurable capability.
20. The learner rejects side-by-side English evidence as a hidden verification
    chore. The product must show one grounded German explanation while retaining
    the original passage internally for automated checks and diagnostics.
21. An explicit refusal becomes a first-class quality feature: verified facts
    may survive, but the coach must admit when the long-term purpose is not
    sufficiently supported instead of hiding the gap behind chess platitudes.
22. The first real book import reveals that “source of truth” needs a qualifier:
    the PDF is authoritative for authorial provenance, but its arithmetic and
    chess prose contain errors, so truth must be assigned claim by claim.
23. A second LLM critic accepts an over-generalized `Bb5` explanation. A
    deterministic rule—not model consensus—finally separates the book's general
    opening plan from the move's verified board effect.
24. A respected second book validates the knowledge strategy but breaks the
    first parser assumption: its move tables are visual columns rather than PGN.
25. Normalizing those tables initially creates a subtler false positive when an
    embedded Panov comparison is attached to an early Queen's Gambit position.
    Final-position-only anchors turn the failure into a tested retrieval rule.
26. The second book produces both a positive result (`2...e6` gains a grounded
    centre-and-development explanation) and an honest negative result (its Ruy
    Lopez introduction still does not directly explain the purpose of `Bb5`).
27. The first six-case runner rejects two incorrectly transcribed FEN fixtures
    before Stockfish starts, demonstrating that evaluation data needs the same
    legality boundary as production input.
28. Conservative parent-line reconstruction resolves 79 contextual fragments
    and adds six position anchors, while leaving 3,451 invalid or unresolved
    lines blocked. The low coverage is accepted as the price of trustworthy RAG.
29. A seemingly grounded `c3` answer cites an unrelated book discussion because
    SAN-only retrieval has no position identity. Disabling global move-token
    search without an opening turns a fluent error into a tested retrieval rule.
30. The final local Stockfish/Qwen run passes all six executable guardrail cases.
    The report explicitly distinguishes regression success from subjective
    teaching quality and invites every future learner complaint into the corpus.
31. Before importing a third book, the agent dogfoods both colors and discovers
    a new truth boundary: a fully grounded answer can still be wrong when it is
    grounded in the current position instead of the learner's historical one.
32. Replaying verified move transitions fixes the reference error, while a
    second run shows the next pedagogical gap: `d3` needs the concrete support of
    `e4` and freed `c1` bishop development, not merely an evaluation comparison.
33. Specific causal facts replace duplicate piece geometry, and temporary
    attacks are suppressed when the main line immediately removes the moved
    piece.
34. An unrelated Schliemann citation from a broad Ruy Lopez text match proves
    that provenance and relevance are different checks; variation-specific book
    advice now requires an exact position.

## Evidence already captured

- Complete discovery decisions and rationale in `project-journal.md`
- Eight architecture decision records
- Exact opening-data provenance and license
- Dependency locks for Python and JavaScript
- Automated backend, rendered-page, lint, and build checks
- Measured local-model behavior and real end-to-end examples
- A concrete course correction from unsafe generation to verified paraphrasing
- A concrete example where richer verified inputs mattered more than adding more models
- A position-level regression from a real learner challenge (`Na2` versus the rim heuristic)
- A machine-readable explanation-quality corpus seeded from two real failures
- A persisted session-review schema and tested multi-signal phase heuristic
- Comparable local chess benchmarks for Qwen, Glimmer, Ornith, and GPT-OSS
- Reproducible cloud comparison of Kimi K3 and DeepSeek V4 Pro on three failures
- Measured countdown inputs for standard, deep, local, and cloud operations
- A whole-book versus explanation-value design trade-off, including the
  learner's decision to require both
- Explicit consent and privacy boundary for automatic local processing of short
  retrieved book passages
- A learner-facing decision against duplicate source text and the resulting
  stronger requirement for sentence-level evidence attribution and fallback
- Explicit learner confirmation that an honest, measurable refusal is preferable
  to an unsupported strategic explanation
- A reproducible first whole-book import with 122 pages, 100 FTS chunks, 399
  claims, 70 quarantined issues, and integrity/index verification
- A documented three-step grounding failure sequence culminating in an accepted
  attributed `Bb5` explanation
- A second 1,252-page source with 13,102 positioned spans, 1,299 FTS chunks,
  213 legal complete lines, and 55 conservative position anchors
- A real cross-opening retrieval false positive and the final-position-only rule
  that removed it
- A successful grounded answer sourced from the exact `2...e6` Queen's Gambit
  position, plus a documented negative Ruy Lopez result
- A six-case end-to-end quality runner using the actual local engine, model, and
  two-book retrieval path
- Cold and cached latency observations for reply-robust deep explanations
- An auditable contextual-line parent relation with conservative yield metrics
- A documented white/black production-path dogfooding session covering hints,
  deep questions, corrections, historical questions, and complete-turn undo
- A regression showing the same past-move question before and after historical
  position reconstruction
- A retrieval example where a legitimate citation is removed because it belongs
  to the wrong sub-variation

## Questions for later evaluation

- Does every-half-move explanation help or interrupt learning?
- Is 0.75 pawns an appropriate correction threshold at approximately 700 Elo?
- Which hint wording leads to successful second attempts?
- How often does the opening graph choose moves that are theoretically present
  but uncommon in 10+0 games at the learner's level?
- How often does the grounding validator fall back, and does that harm perceived
  quality?
- Does opening understanding transfer to fewer early errors in real games?
- Does cited book evidence improve the learner's explanation rating compared
  with deeper Stockfish evidence alone?
- Which failures originate in extraction, retrieval, or synthesis, and how can
  they be distinguished in evaluation?
