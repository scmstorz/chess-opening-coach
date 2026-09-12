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
35. Selecting a third owned book triggers a publication concern. The project
    avoids the false choice between abandoning open source and distributing
    protected content by splitting a public code core from a private local
    knowledge overlay.
36. The policy becomes executable: a fail-closed public runtime profile ignores
    private books, while a release gate scans Git history, private file types,
    and long source-text fingerprints without committing those fingerprints.
37. The Emms import validates the source choice but reveals another layout
    boundary: question-led prose is ideal for the learner, while isolated moves
    interleaved with prose yield only seven safe position anchors. Pedagogical
    quality and retrievability remain separate measurements.
38. Deterministic progressive reconstruction turns those isolated moves into
    candidate positions only when move number, color, legality, local parent,
    and a confirming continuation agree; 51 ambiguous chunks remain blocked.
39. An initially impressive jump from seven to 110 anchors fails a real `Ba4`
    test by attaching a later variation name. Text-block locality and
    intervening-move boundaries deliberately reduce final yield to 81 anchors.
40. Exact position evidence without an exact explanatory claim becomes another
    meaningful refusal: broad opening prose may no longer fill a known local
    evidence gap.
41. The LLM critic catches both an invented long-term conclusion and a reversed
    actor in a conditional pin explanation. Sentence-level rejection preserves
    supported output instead of choosing between unsafe display and total loss.
42. A final `Bb5` run combines exact Emms evidence, deterministic board effects,
    and reply-robust Stockfish plans, while a second-color game confirms the
    improvement did not hard-code one opening path.
43. Repeated learner objections become a product capability: a three-state,
    low-friction feedback loop preserves the complete explanation context while
    treating human ratings as review evidence rather than automatic chess truth.
44. A `c4` explanation demonstrates that provenance is still not relevance: a
    correctly cited plan for Black in a different “Defense” cannot answer why
    White's move is useful. Opening-family and actor gates prefer no evidence.
45. The learner's improvised `Kf3xKd4` notation reveals an unsafe fallback to a
    highlighted `Be3`. The coach now asks about the uniquely inferable `Nxd4`
    instead of silently guessing and teaches `K` versus `N` in context.
46. The confirmed position contains a one-ply answer—`...Bxd1` wins the queen.
    Deterministic tactical priority produces a shorter, better explanation than
    Stockfish plan extraction, book RAG, or a multi-model ensemble.
47. Three repetitive citation cards become one presentation aggregate per book,
    while claim-level references remain intact for audits and feedback.
48. Free exploration and deliberate repertoire practice become two explicit
    product modes instead of forcing one move policy to serve both learning jobs.
49. The learner rejects an answer preview for the first Italian lesson. The
    resulting loop tests recall immediately, gives two progressive hints, and
    reveals the move only on the third miss or an explicit suggestion request.
50. An annotated authored PGN wins over a new lesson DSL: it keeps legal moves,
    coach replies, explanations, and future variations close to chess's standard
    interchange format without placing private book content in the repository.
51. Broad opening-theory membership, exact lesson membership, and engine quality
    become separately persisted facts; a sound non-lesson move is no longer
    mislabeled as an objective chess error.
52. Real Stockfish ranks the defining `3.Bc4` slightly below its top choice under
    shallow budgets, demonstrating why a human repertoire must not be rewritten
    by volatile top-one engine output.
53. The learner immediately identifies the transfer problem in a fixed line:
    memorizing one cooperative Italian sequence does not prepare White for a
    different or inferior Black move.
54. A large repertoire tree, per-move engine randomness, and simulated 700-Elo
    errors are considered. Thirteen coherent authored scenarios are chosen as a
    smaller testable step because variation between sessions must not destroy
    causality within a session.
55. One scenario source now supports three distinct learning jobs: repeat the
    model, jump directly to a deviation, or discover a hidden opponent choice
    from move one.
56. Hiding only the initial title is insufficient: a Petroff scenario sharing
    `1...e5` must remain secret until `2...Nf6`. The API reveal rule therefore
    follows the first actual divergence, not a fixed move number.
57. A Stockfish audit improves curriculum rather than dictating it. The first
    Hungarian draft says “use more centre” but delays `d5`; aligning the move
    with the lesson concept lowers its measured loss and strengthens the causal
    story.
58. Thirteen production self-plays and 60 random branch starts verify 132
    half-moves, custom starting FENs, persistence, completion, and undo while
    explicitly leaving visual learning transfer for human evaluation.
59. The first learner session immediately disproves the initial curriculum
    grouping: `1...c5` is a valid and well-explained response, but a beginner who
    selected Italian practice has no Sicilian plan to recall.
60. Lower probability would not repair a broken prerequisite. Curriculum family
    becomes an enforceable selection boundary: Italian variation starts only
    after `1.e4 e5 2.Nf3 Nc6 3.Bc4`.
61. Six already-authored opening switches are retained with zero weight for a
    later `1.e4` foundations course. Narrowing the current lesson does not require
    discarding verified future content.
62. A regression finds a second, smaller spoiler: the Two Knights goal itself
    names `d3`. Testing absence from the prompt must include goals and metadata,
    not just the visible question sentence.
63. A real Two Knights session then exposes a state-machine error: reaching the
    end of an 11-ply authored branch says the whole realistic exercise is
    “Geschafft,” even though the 20-ply model line and opening phase continue.
64. Scenario mastery, opening completion, and game completion become three
    separate meanings. Realistic mode now treats the authored boundary as an
    `Etappenziel`, releases the fixed line, and continues with theory/Stockfish.
65. Undo must restore policy as well as pieces. The turn snapshot therefore
    records whether guided play had already changed into free opening play.
66. The learner observes that coach-move countdowns are consistently low. The
    nominally operation-specific average still pools fast authored replies with
    slow free replies and estimates the center rather than the upper runtime.
67. Timing becomes workload-aware: scripted and adaptive move profiles retain
    separate recent histories, and a conservative 80th-percentile estimate
    replaces the pooled exponential mean.

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
- A learner-triggered countdown correction separating scripted engine work from
  adaptive Ollama-backed coach turns
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
- An explicit public-core/private-knowledge decision with two tested runtime
  profiles
- A publication gate covering the Git index, full path history, private formats,
  and 24-word local-corpus fingerprints
- A clean-history result proving that no PDF or knowledge database had entered
  the repository before publication planning
- A third private source import with 363 pages, 160 chunks, 127 verified lines,
  seven conservative position anchors, and a documented parser limitation
- A three-case post-import regression in which `Bb5`, `Na2`, and `a4` remain
  correct and deliberately expose no unanchored Emms citation
- Before-and-after progressive compiler metrics, including the rejected
  high-recall intermediate and the lower conservative final yield
- A production `Ba4` false-anchor example that changed both claim locality and
  exact-position fallback behavior
- Two exact, legality-checked Emms claims for `3.Bb5`, with source pages and an
  accepted German synthesis after sentence-level critic filtering
- A final six-case guardrail pass plus white- and black-side API dogfooding
- A local explanation-feedback schema with revisable ratings, optional notes,
  exact FEN/move/engine/source/model snapshots, filtered review, and ignored
  fixture-candidate export
- A documented distinction between “factual error” and “did not help me
  understand,” derived directly from the learner's earlier objections
- A persisted real-world FEN showing a cross-opening, wrong-side `c4` retrieval
  failure and a repaired fail-closed result with zero irrelevant claims
- A full malformed-notation confirmation regression tied to an unchanged FEN
- A deterministic `Nxd4 ...Bxd1` queen-loss regression that bypasses book and LLM
  layers because immediate tactics have higher explanatory priority
- A compact one-card-per-book source display that preserves internal references
- A complete ten-move Italian White self-play through the production service,
  plus engine-loss measurements for every authored half-move
- An ADR connecting the learner's “ask immediately” preference to PGN-backed
  recall, hint, correction, suggestion, persistence, and undo semantics
- A 13-scenario opponent curriculum with explicit non-empirical selection
  weights, first-divergence secrecy, and separate model/branch/realistic modes
- A Stockfish 18 audit of 43 learner decisions plus complete real-service
  self-play of all 132 authored half-moves
- A real learner counterexample separating technically correct opening breadth
  from readiness-appropriate curriculum variation
- An enforceable prerequisite boundary with seven active Italian scenarios and
  six preserved but inaccessible `1.e4` foundations lessons
- A real-session regression separating the end of a prepared opponent branch
  from the later learner-controlled end of the opening phase
- A public-repository licensing decision that separates MIT-licensed original
  code, GPL/CC0 third-party components, and an unlicensed private book overlay
- A public-clone onboarding audit that converts an implicit developer setup into
  platform-specific quickstarts, degraded-mode expectations, and executable
  documentation contracts

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
- How often do `unclear` and `wrong` judgments lead to different root causes and
  therefore different fixes?
- Does the one-click control remain unobtrusive enough to use after every move?
- Which curated deviations actually recur in the learner's 10+0 games, and how
  should observed frequency change the explicitly non-empirical starting weights?
- When does a sound non-target White move deserve to become an accepted
  repertoire alternative rather than remain a retry?
