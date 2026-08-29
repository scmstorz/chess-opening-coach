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

## Evidence already captured

- Complete discovery decisions and rationale in `project-journal.md`
- Four architecture decision records
- Exact opening-data provenance and license
- Dependency locks for Python and JavaScript
- Automated backend, rendered-page, lint, and build checks
- Measured local-model behavior and real end-to-end examples
- A concrete course correction from unsafe generation to verified paraphrasing

## Questions for later evaluation

- Does every-half-move explanation help or interrupt learning?
- Is 0.75 pawns an appropriate correction threshold at approximately 700 Elo?
- Which hint wording leads to successful second attempts?
- How often does the opening graph choose moves that are theoretically present
  but uncommon in 10+0 games at the learner's level?
- How often does the grounding validator fall back, and does that harm perceived
  quality?
- Does opening understanding transfer to fewer early errors in real games?

