# Publication safety

## Boundary

The Chess Opening Coach is publishable as an open-source application, but its
private book corpus is not part of that application distribution.

| Asset | Public repository | Private local runtime |
| --- | --- | --- |
| Application and compiler code | yes | yes |
| Database schema and synthetic fixtures | yes | yes |
| Lichess CC0 opening data | yes | yes |
| Owned chess-book PDFs or e-books | no | yes |
| Extracted chunks and claims | no | yes |
| `book_knowledge.db` | no | yes |
| Generated explanation using short retrieved evidence | no precompiled corpus | yes |

Bibliographic metadata and a source checksum may remain public. They make a
private import reproducible without distributing the source or its text.

## Runtime profiles

The local profile is the development default:

```bash
CHESS_COACH_RUNTIME_PROFILE=local npm run coach
```

It permits local book retrieval only when `CHESS_COACH_BOOKS_ENABLED` is also
true. Retrieved excerpts may go to the configured loopback Ollama service, but
not to a cloud model.

The public profile fails closed:

```bash
CHESS_COACH_RUNTIME_PROFILE=public npm run coach
```

It installs a null book provider regardless of `CHESS_COACH_BOOKS_ENABLED` or
whether a private database happens to exist. Stockfish, `python-chess`, opening
data, and deterministic explanations continue to work.

Any future hosted service must use only original, public-domain, or suitably
licensed knowledge. A translation or LLM paraphrase is not treated as an
automatic substitute for permission.

## Publication gate

`npm run check:publication` checks the Git index and every path in Git history.
It rejects:

- anything below private book or derived-knowledge directories;
- PDF and common e-book formats;
- SQLite and generic database files; and
- private database sidecar files.

When `data/book_knowledge.db` is locally available, the gate builds temporary,
non-reversible hashes of every 24-word sequence in the private chunks and scans
both indexed and current tracked text. A match is reported by source reference,
without printing the passage. The hashes exist only in process memory.

`npm run check:publication:release` additionally fails if that local overlap
scan cannot run. This is the release-owner check; a clean public clone can run
the ordinary gate without possessing any private content.

## Release procedure

1. Confirm that every private source was obtained lawfully and is permitted for
   the intended local use. Do not bypass DRM or other technical controls.
2. Review case-study quotations manually for a genuine citation purpose and
   minimal necessary length.
3. Run the complete test suite and `npm run check:publication:release`.
4. Confirm with `git status --ignored` that books and local databases remain
   ignored rather than tracked.
5. Publish from a Git commit or `git archive`, never by uploading a copy of the
   working directory containing ignored local assets.
6. Run any public demonstration with `CHESS_COACH_RUNTIME_PROFILE=public`.

## Limits

The gate is a defense-in-depth engineering control, not a legal opinion or
license audit. It cannot decide whether a short quotation is justified, detect
all paraphrases, or prove lawful source acquisition. The 24-word overlap check
deliberately detects substantial verbatim leakage rather than ordinary chess
terminology. Human pre-publication review remains required.

## Legal references considered

The project policy was informed by the German Copyright Act's treatment of
protected works ([UrhG section 2](https://www.gesetze-im-internet.de/urhg/__2.html)),
public availability
([section 19a](https://www.gesetze-im-internet.de/urhg/__19a.html)), text and data
mining ([section 44b](https://www.gesetze-im-internet.de/urhg/__44b.html)),
quotation ([section 51](https://www.gesetze-im-internet.de/urhg/__51.html)), and
private reproduction
([section 53](https://www.gesetze-im-internet.de/urhg/__53.html)). These links
record the design input; they are not a conclusion that a particular source or
use is licensed. The engineering policy intentionally stays conservative and
requires legally obtained sources plus human review.
