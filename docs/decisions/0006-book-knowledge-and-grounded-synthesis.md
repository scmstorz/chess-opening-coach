# ADR 0006: Build book compilation and grounded explanation as one staged capability

- Status: accepted
- Date: 2026-09-09

## Context

Repeated play showed that legal move descriptions, square lists, and deeper
Stockfish lines do not by themselves answer the learner's main question: what a
move is intended to achieve over the medium and long term. Cloud trials with
Kimi K3 and DeepSeek V4 Pro improved fluency but introduced unsupported or false
positional claims. A proposed Chess Knowledge Compiler therefore adds local,
page-level evidence from chess books without turning a book or an LLM into a new
source of legality, opening identity, or engine truth.

During planning, two possible first outcomes were separated:

1. compile an entire book into a reproducible, searchable, citable knowledge
   base; and
2. use that knowledge to make a concrete answer such as “Why is Bb5 useful?”
   materially more educational.

The learner explicitly requires both. A searchable corpus that merely appears
under an unchanged weak answer is not a sufficient product outcome. Conversely,
a one-off explanation path without a reliable compiler would not provide the
provenance and repeatability required for later books or for the case study.

## Decision

Deliver both outcomes through staged vertical integration:

1. Capture a baseline evaluation set from real explanation failures.
2. Compile the complete reference book into a local SQLite corpus with stable
   book/page/span/chunk provenance, FTS search, aliases, issues, idempotent
   import, verification, and removal.
3. Connect position-, opening-, move-, and question-aware retrieval to
   `CoachService.answer_question()` and show sources separately in the UI.
4. Add grounded synthesis that combines board facts, opening data, Stockfish
   evidence, and relevant book passages into a German teaching explanation.
5. Evaluate retrieval quality and educational improvement before adding OCR,
   embeddings, automatic diagram recognition, or multi-book consensus.

The local Ollama provider may automatically receive the small book excerpts
selected for the current question. It must not receive the entire book. This
processing stays on the learner's computer and requires no per-question
confirmation.

Book excerpts remain a distinct, untrusted evidence class. Source-only claims
must be attributable to the author; they do not become verified chess facts
because an LLM paraphrases them. Concrete moves, lines, evaluations, legality,
and opening membership remain constrained by the existing verified evidence
and grounding checks. The runtime must retain a deterministic fallback when the
model is unavailable or adds unsupported content.

The normal learner UI shows one German explanation, followed only by compact
source metadata such as book, author, year, page, and validation status. It does
not show the English source passage beside the German answer. The original text
remains available internally through the compiler, provenance chain, and
diagnostic tools. Verification is a system responsibility rather than a request
for the learner to compare two versions.

Generated explanation sentences must identify their supporting evidence. Hard
facts such as moves, lines, evaluations, opening names, and board effects are
checked deterministically. A second local model may act as an additional
entailment critic, but model agreement is not treated as proof. Unsupported or
insufficiently attributable strategic prose triggers a conservative fallback.
The learner explicitly considers this refusal behavior essential. The coach
must say that it lacks a sufficiently supported strategic explanation instead
of filling the gap with generic advice or plausible prose. Any independently
verified board or engine facts may still be presented alongside that limitation.

Cloud processing of book text is not enabled by this decision. Any later cloud
use requires a separate, explicit learner confirmation and must disclose what
excerpt would leave the local machine.

## Rationale

The sequence makes the full book useful as a durable local asset while exposing
the user-visible value early enough to evaluate it. It also isolates three
different failure modes: extraction can be wrong, retrieval can be irrelevant,
and synthesis can be unsupported. Each layer can therefore be tested and
reported independently.

Local excerpt processing matches the offline-first product direction and gives
Ollama richer pedagogical material without granting it authority over chess
truth. Deferring OCR, embeddings, and diagram reconstruction keeps the first
evaluation focused on whether cited prose actually improves explanations.

## Consequences

- The Knowledge Compiler is not considered finished merely because text is in
  SQLite; a measured improvement in at least the agreed explanation cases is a
  required outcome.
- The first schema and CLI must support the complete book, while advanced
  extraction features can remain explicit issues for later review.
- Runtime responses need separate fields for verified facts and attributed book
  evidence.
- Grounding validation must cover paraphrases derived from source passages, not
  only numbers and opening names.
- Source text remains available for diagnostics and tests but is not duplicated
  in the learner-facing explanation.
- Unsupported synthesis produces an explicit, machine-readable fallback reason
  and a candid learner-facing knowledge boundary.
- The case study will preserve baselines, design alternatives, decisions,
  failure cases, latency, retrieval results, and before/after explanations.
