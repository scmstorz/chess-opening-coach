# Third-party components and data

The MIT license in `LICENSE` applies to the original project code and authored
project material in this repository. Third-party software and data retain their
own licenses.

Important runtime and data dependencies include:

- [`python-chess`](https://github.com/niklasf/python-chess), licensed under
  GPL-3.0-or-later. It is installed as a dependency and is not vendored in this
  repository. Redistribution of a complete combined application may therefore
  carry GPL obligations in addition to the MIT grant for the original project
  code.
- [Stockfish](https://stockfishchess.org/), licensed under GPLv3. It is invoked
  as an external locally installed process and is not distributed in this
  repository.
- [`lichess-org/chess-openings`](https://github.com/lichess-org/chess-openings),
  made available under CC0. The included snapshot retains its source and license
  information in `data/openings/`.
- All remaining Python and JavaScript dependencies retain the licenses declared
  by their respective authors and packages.

Owned chess books, extracted passages, compiled claims, and the local book
knowledge database are private operator-supplied inputs. They are not included
in this repository and are not covered by the project's MIT license.
