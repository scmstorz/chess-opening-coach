# ADR 0010: Publish the code, not the private book corpus

- Status: accepted
- Date: 2026-09-09

## Context

After a third owned chess book had been selected for local compilation, the
learner questioned whether book-backed RAG made the entire coach impossible to
publish. The concern exposed two different products that had previously shared
one working directory: a reusable application and one person's private source
library.

PDFs, extracted chunks, and the derived SQLite corpus can reproduce substantial
parts of a protected source. LLM translation or paraphrase does not create a
safe publication assumption. Conversely, the compiler, verification pipeline,
and synthetic tests do not need any private source to be useful or publishable.

## Options considered

1. Keep the complete project private. This is simple but unnecessarily prevents
   publication of reusable engineering work.
2. Publish the derived database but omit the PDFs. This was rejected because a
   searchable corpus still contains the protected prose.
3. Publish paraphrased knowledge as a static dataset. This was rejected because
   systematic close paraphrase is not treated as a rights-clearing mechanism.
4. Split the public core from an operator-supplied private knowledge overlay.

## Decision

Choose option 4.

- Git, releases, and deployments contain application code, open data,
  bibliographic metadata, and synthetic fixtures only.
- Owned books, extracted content, and the knowledge database remain ignored,
  local, and operator supplied.
- `local` and `public` runtime profiles make the boundary executable. `public`
  always disables the private provider, even if another flag attempts to enable
  it.
- A publication gate checks the current Git index and repository history for
  private paths and formats.
- When the private corpus is present, the release gate also checks tracked text
  against in-memory 24-word source fingerprints.
- Publicly hosted knowledge must be original, public-domain, or explicitly
  licensed. Book excerpts remain unavailable to cloud models under the current
  privacy decision.

## Consequences

The open-source application can be published without distributing the learner's
books. A clone works without them and reports the missing capability honestly.
Local users may opt into their own sources.

Release owners must publish from Git rather than zipping the working directory,
because ignored private files intentionally coexist with the code locally. The
gate reduces accidental leakage but cannot replace a source-license audit or a
manual review of short case-study quotations.
