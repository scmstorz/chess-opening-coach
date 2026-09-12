# ADR 0017: Publish the original project code under MIT

- Status: accepted
- Date: 2026-09-12

## Context

The learner created the public repository
`https://github.com/scmstorz/chess-opening-coach` and requested a simple,
permissive license. The source repository is intended both as a usable hobby
project and as evidence for a later case study. The private book corpus must not
be licensed or published accidentally.

The direct Python dependency `python-chess` declares GPL-3.0-or-later. Stockfish
is also GPLv3 software, although this project launches a separately installed
binary rather than distributing it. The included Lichess opening snapshot is
CC0. A project-level license therefore needs to distinguish original code from
third-party components and operator-supplied private content.

## Options considered

1. Leave the repository without a license. Rejected because public visibility
   alone grants no clear reuse rights and therefore would not meet the intended
   open-source goal.
2. License all original code under GPL-3.0-or-later. This aligns most directly
   with `python-chess`, but is more restrictive than the requested permissive
   grant for independently reusable project code.
3. License the original project code under MIT and explicitly document the
   separate licenses and possible obligations of combined distributions.

## Decision

Choose option 3. The standard MIT license applies to Sacha Storz's original
project code and authored repository material. `THIRD_PARTY_NOTICES.md` names
the important separate dependencies and data sources. Project metadata also
declares MIT.

MIT is GPL-compatible, so the original code can participate in a GPL-covered
combination. The permissive project license does not remove any GPL obligations
that may apply when someone redistributes the application together with
`python-chess` or Stockfish. This engineering record is not a legal opinion.

The private PDFs, extracted passages, compiled knowledge database, and learner
database remain ignored local inputs and are outside the MIT grant. The
fail-closed `public` runtime profile and the publication gate from ADR 0010
remain mandatory release controls.

## Consequences

GitHub can recognize the repository as MIT-licensed while visitors also see the
important GPL and CC0 boundaries. Reusers may use the project's original code
under MIT, but they remain responsible for the licenses of the dependencies and
the form in which they redistribute a complete application.

Public releases must continue to originate from Git, never from a copy of the
working directory containing ignored private files. A human source and license
review remains part of the release procedure even when the automated gate
passes.
