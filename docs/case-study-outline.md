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

## Evidence already captured

- Complete discovery decisions and rationale in `project-journal.md`
- Five architecture decision records
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

## Questions for later evaluation

- Does every-half-move explanation help or interrupt learning?
- Is 0.75 pawns an appropriate correction threshold at approximately 700 Elo?
- Which hint wording leads to successful second attempts?
- How often does the opening graph choose moves that are theoretically present
  but uncommon in 10+0 games at the learner's level?
- How often does the grounding validator fall back, and does that harm perceived
  quality?
- Does opening understanding transfer to fewer early errors in real games?
