# Local book sources

Place locally owned chess-book PDFs in this directory. The Chess Knowledge
Compiler treats these files as import sources and stores reproducible derived
data in `data/book_knowledge.db`.

PDF files are intentionally ignored by Git and must not be deployed. The public
repository contains only compiler code, synthetic test fixtures, and source
metadata produced by the local import.

## Local source registry

| File | SHA-256 | Imported |
| --- | --- | --- |
| `Stewart, Clyde - Chess Openings For Beginners (2021).pdf` | `b8a5dfb39bab9d8aaa972f4d13eb5b23afeda1ce4d36a3a5c93e86107c884fbe` | 2026-09-09 |
| `Fundamental Chess Openings - Paul van der Sterren.pdf` | `cbbce0cd22bf4a7a060104ad55c21c865f30713e1bbb217e9dd792c37c32d355` | 2026-09-09 |
| `John Emms - Discovering Chess Openings.pdf` | `4b11602cfeb5040546750a9365f2786d1f9c21b9f62cff9e2d63473bcdc12b85` | 2026-09-09 |

For every later book, copy the owned PDF into this directory and add its
filename, checksum, and import date here. The checksum makes the private local
source reproducible without committing or distributing its contents.

Only this metadata registry is public. The PDF files and compiled text remain
an operator-owned local overlay and are rejected by the publication guard if
they ever enter Git.
