# Agenten-Briefing: Chess Knowledge Compiler

Stand: 2026-09-09  
Ziel-Repository: `/Users/storzs/Documents/repos/chess-opening-coach`  
Referenzbuch: `/Users/storzs/Documents/Books/Schach/Stewart, Clyde - Chess Openings For Beginners (2021).pdf`

## 1. Auftrag

Baue einen lokalen, inkrementellen **Chess Knowledge Compiler**, der Schachbücher offline in eine quellengebundene SQLite-Wissensbasis übersetzt. Der bestehende Coach soll zur Laufzeit wenige relevante Buchbelege abrufen können, ohne seine bereits implementierten Wahrheitsgrenzen für Legalität, Eröffnungstheorie und Enginebewertung zu verwässern.

Der Knowledge Compiler ist eine Erweiterung des vorhandenen Coach-Repositories, kein separates Produkt.

## 2. Vor der Implementierung lesen

- `README.md`
- `docs/architecture.md`
- `docs/project-journal.md`, insbesondere Wissensarchitektur und Benutzer-PDF
- `docs/decisions/0002-chess-truth-boundaries.md`
- `docs/decisions/0003-opening-data.md`
- `docs/decisions/0004-grounded-ollama.md`
- `backend/chess_coach/openings.py`
- `backend/chess_coach/storage.py`
- `backend/chess_coach/tutor.py`
- `backend/chess_coach/service.py`, besonders `answer_question()`, `_question_fallback()` und `_grounded()`
- `backend/chess_coach/api.py`
- `backend/chess_coach/config.py`

Das Projekt besitzt bereits:

- `python-chess` für Regeln, SAN/UCI und Brettzustand;
- einen aus Lichess-TSV aufgebauten, transpositionsfähigen Opening-DAG;
- Stockfish für objektive Bewertung und Kandidaten;
- Ollama mit harter Grounding-Grenze;
- SQLite für Lernhistorie, Session-Summaries und Engine-Cache;
- einen funktionierenden Fragepfad mit geprüften `answer_facts`.

Diese Komponenten wiederverwenden. Keine zweite Schachwahrheitsschicht bauen.

## 3. Verbindliche Wahrheitsgrenzen

Die vorhandene Leitlinie bleibt unverändert:

> Keep chess truth outside the LLM. The LLM explains verified facts; it does not define them.

| Quelle | Autorität | Keine Autorität für |
|---|---|---|
| `python-chess` | Legalität, SAN/UCI, Brettzustand, FEN | Pädagogik und Autorenmeinung |
| Lichess Opening Graph | ECO, Namen, vorhandene Theoriekanten | objektive Zugqualität |
| Stockfish | Kandidaten, Bewertungen, taktische Qualität | menschliche Erklärung und Autorenintention |
| Schachbuch | Autorenempfehlung, Plan, Erklärung, Warnung, historische Perspektive | Legalität, ECO-Wahrheit, Enginebewertung |
| Coach-Code | deterministische Synthese und Kennzeichnung | neue unbelegte Schachbehauptungen |
| Ollama | Auswahl bzw. streng begrenzte Bearbeitung geprüfter Fakten | neue Züge, Varianten, Zahlen oder Urteile |

Ein Buchsatz ist zunächst immer eine **quellengebundene Behauptung**. Selbst bei einem sachlich falschen Satz muss das System korrekt speichern können: „Dieses Buch behauptet X“, ohne X als Schachwahrheit zu übernehmen.

## 4. Einordnung des vorhandenen Spikes

Unter `/Users/storzs/Downloads/chess-knowledge-compiler` liegt ein isolierter technischer Spike. Er entstand ohne Kenntnis des echten Coach-Repositories. Er ist nicht die Zielarchitektur.

Gezielt wiederverwendbar:

- Poppler-basierte PDF-Extraktion mit Bounding Boxes;
- SQLite-FTS5/BM25;
- Buch-/Seiten-/Span-/Chunk-Provenienz;
- deutsche und englische Eröffnungsaliase;
- Claim- und Concept-Heuristiken;
- Qualitätsflags und idempotenter Import;
- Evidenzobjekte und Tests.

Nicht unverändert übernehmen:

- eigene Position-Key-Logik;
- eigener paralleler Opening- oder Positionsgraph;
- eigene allgemeine SQLite-Runtime;
- separate Coach-CLI als Produktoberfläche;
- die Annahme, ein Buch sei primäre Eröffnungsquelle.

Für Positionsidentität ausschließlich `chess_coach.openings.position_key()` verwenden.

## 5. Produktziel des ersten Inkrements

1. Ein oder mehrere lokale PDFs werden durch einen expliziten Offline-Befehl importiert.
2. Der Import erzeugt eine reproduzierbare und pro Buch löschbare SQLite-Wissensbasis.
3. Der Coach funktioniert unverändert, wenn keine Buchdatenbank existiert.
4. `CoachService.answer_question()` kann zusätzlich passende Buchpassagen abrufen.
5. Buchbelege erscheinen als eigene Evidenzklasse mit Buch, Ausgabe, PDF-Seite und Status.
6. Buchwissen verändert niemals Legalität, Opening-Identität, Enginebewertung, Korrekturschwelle oder Zugwahl.
7. Ungeprüfte Statistiken und unsichere Varianten werden nicht zu normalen Coach-Fakten.

## 6. Nicht-Ziele des ersten Inkrements

Bewusst vertagen:

- Vektoren und Embeddings;
- Graphdatenbank;
- automatisches Diagramm-zu-FEN;
- freie Rekonstruktion unvollständiger Zugangaben aus Prosa;
- Engineanalyse aller Buchclaims;
- Multi-Autor-Konsens und Dissensradar;
- Theory Time Machine;
- Spaced Repetition und Vergessensmodell;
- Bibliotheksverwaltung im Browser;
- Cloud-Uploads, D1 oder R2;
- Volltextausgabe ganzer Kapitel;
- Veränderung der bestehenden Zugwahl oder Korrekturschleife.

## 7. Datenbankentscheidung

Standardmäßig zwei getrennte SQLite-Dateien verwenden:

```text
data/coach.db             # persönliche Historie, Summaries, Engine-Cache
data/book_knowledge.db    # reproduzierbares Buchwissen
```

Begründung:

- persönliche Daten und Buchkorpus haben verschiedene Lebenszyklen;
- `book_knowledge.db` kann bei Schemaänderungen neu erzeugt werden;
- Bücher müssen einzeln vollständig entfernbar sein;
- die App muss ohne Buchkorpus starten können;
- abgeleitete bzw. urheberrechtlich sensible Daten werden nicht mit Lernbackups vermischt.

`book_knowledge.db` und importierte PDFs gehören nicht ins Git-Repository und nicht ins Deployment.

Neue optionale Konfiguration:

```text
CHESS_COACH_BOOK_DATABASE=/absolute/path/to/book_knowledge.db
CHESS_COACH_BOOKS_ENABLED=true
```

Standardpfad: `PROJECT_ROOT / "data" / "book_knowledge.db"`. Fehlt die Datei, verwendet die Anwendung einen Null-Provider. Der Sites-Worker sowie D1/R2 bleiben unverändert; die lokale FastAPI liest SQLite.

## 8. Empfohlene Paketstruktur

```text
backend/chess_coach/book_knowledge/
├── __init__.py
├── models.py
├── schema.py
├── pdf_extract.py
├── compiler.py
├── chess_extract.py
├── retrieval.py
└── cli.py

backend/tests/book_knowledge/
├── fixtures/
├── test_compiler.py
├── test_retrieval.py
├── test_chess_extract.py
└── test_service_integration.py
```

Voraussichtlich anzupassen:

```text
backend/chess_coach/config.py
backend/chess_coach/api.py
backend/chess_coach/service.py
app/page.tsx
.env.example
.gitignore
README.md
docs/architecture.md
docs/project-journal.md
```

Das Feature als klar begrenzten Adapter neben `OpeningBook`, `StockfishService`, `OllamaTutor` und `SQLiteStore` halten.

## 9. Offline-CLI

Bevorzugter Aufruf:

```bash
.venv/bin/python -m chess_coach.book_knowledge.cli ingest \
  "/path/book-1.pdf" \
  "/path/book-2.pdf"
```

Diagnosebefehle:

```bash
.venv/bin/python -m chess_coach.book_knowledge.cli books
.venv/bin/python -m chess_coach.book_knowledge.cli search "Spanische Partie"
.venv/bin/python -m chess_coach.book_knowledge.cli issues --severity warning
.venv/bin/python -m chess_coach.book_knowledge.cli verify
.venv/bin/python -m chess_coach.book_knowledge.cli remove BOOK_ID
```

Der App-Start scannt keine Ordner und startet keine OCR-, Embedding- oder LLM-Jobs. Der Import ist explizit und offline.

## 10. PDF-Importpipeline

Poppler nur im Importpfad verwenden:

- `pdfinfo` für Metadaten und Seitenzahl;
- `pdftotext -bbox-layout` für Text, Seiten und Blockkoordinaten;
- `pdfimages -list` für Bilder und Diagrammkandidaten.

Pipeline:

1. Pfad auflösen, PDF prüfen und SHA-256 bilden.
2. Stabilen `book_id` aus dem Inhaltshash erzeugen.
3. Metadaten aus PDF und Dateinamen kombinieren.
4. Text seiten- und blockweise extrahieren.
5. wiederholte Header/Footer erkennen;
6. Cover, Frontmatter und Inhaltsverzeichnis speichern, aber nicht normal durchsuchen;
7. mehrzeilige Überschriften zusammenführen;
8. Abschnitte und semantische Chunks bilden;
9. Claims, Konzepte, explizite PGN/SAN-Linien und Bildkandidaten extrahieren;
10. unklare Inhalte als Issues speichern, nicht raten;
11. ein Buch vollständig in einer Transaktion aktualisieren;
12. `PRAGMA optimize` nach dem Import ausführen.

Wenn eine Inhaltsseite kaum Text enthält, `sparse_page_text` oder `ocr_required` erzeugen. Im ersten Inkrement keine OCR automatisch ausführen.

Die Provenienzkette muss erhalten bleiben:

```text
Coach-Antwort
  -> BookFact
  -> Claim oder Chunk
  -> Textspan und Bounding Box
  -> PDF-Seite
  -> PDF und SHA-256
```

## 11. Chunking

Zuerst Dokumenthierarchie erkennen:

```text
Buch
└── Kapitel
    └── Eröffnung / Unterabschnitt
        ├── erklärender Absatz
        ├── Empfehlung oder Warnung
        ├── Variante
        └── Diagrammunterschrift
```

Danach benachbarte Blöcke derselben Sektion auf ungefähr 1.200 bis 1.800 Zeichen bündeln. Niemals über eine klare Abschnittsüberschrift hinweg. Jeder Chunk erhält:

- `book_id`, Section-ID und Überschriftenpfad;
- erste und letzte PDF-Seite;
- geordnete Span-IDs;
- Originaltext und Text-Hash;
- stabile `source_ref`;
- Zeichen- und grobe Tokenzahl.

FTS5 indexiert `title`, `section_path` und `text`. IDs bleiben `UNINDEXED`.

## 12. Logisches SQLite-Schema

```text
knowledge_meta
books
pages
spans
sections
chunks
chunks_fts
chunk_spans
claims
concepts
chunk_concepts
book_lines
book_position_evidence
diagrams
issues
aliases
```

### Bücher und Quellen

`books` speichert stabilen Inhaltshash, Titel, Autor, Jahr, lokalen Quellpfad, Dateigröße, Seitenzahl, Extraktionsversion und Importzeitpunkt.

`pages` und `spans` speichern PDF-Seitennummer, Seitentyp, Text, Reihenfolge und Bounding Boxes. Die PDF-Seite ist maßgeblich; eine gedruckte Seitennummer kann zusätzlich nullable gespeichert werden.

### Abschnitte und Suche

`sections` bildet die Hierarchie. `chunks` speichert die Evidenzeinheiten. `chunk_spans` erhält die genaue Rückverfolgbarkeit. `chunks_fts` ermöglicht FTS5/BM25.

### Claims

Mindestens folgende Typen:

- `recommendation`
- `warning`
- `plan`
- `definition`
- `history`
- `statistic`

Pflichtfelder: Quelltext, Seite/Span, Extraktionsmethode, Konfidenz und `validation_status`.

Statuswerte:

- `source_only`
- `unverified`
- `legality_checked`
- `engine_checked`
- `rejected`

Optionale Bindungen: `position_key`, Fokuszug und Opening-Identität.

### Varianten und Positionen

`book_lines` nimmt nur explizit parsebare PGN/SAN-Linien auf und behält Rohtext, normalisierte SAN/UCI-Linie sowie Validierungsstatus.

`book_position_evidence` verknüpft die belegte Zielstellung einer am Chunkanfang
angezeigten, vollständig validierten Linie über den vorhandenen
`position_key(board)` mit Chunk, Seite und Linie. Eine frühere Idee, jeden
Halbzug-Präfix zu verknüpfen, wurde nach einem realen Cross-Opening-Fehltreffer
verworfen; siehe ADR 0007. Keine eigene konkurrierende Positionstabelle ist
erforderlich.

### Diagramme und Issues

`diagrams`: Seite, Bildnummer, Abmessungen, Encoding, `likely_board`, `recognition_status`, optionale Orientierung/FEN.

`issues`: Buch, Chunk, Seite, Typ, Schweregrad, Nachricht, Kontext und Reviewstatus.

### Erforderliche Indizes

Nur reale Abfragen optimieren:

- `books(sha256)` unique;
- `pages(book_id, page_number)` unique;
- `chunks(book_id, page_start)`;
- `claims(chunk_id, validation_status)`;
- `book_position_evidence(position_key)`;
- `issues(book_id, status, severity)`;
- FTS5 für Chunks.

Keine redundanten Indizes auf `INTEGER PRIMARY KEY`. Repräsentative Abfragen mit `EXPLAIN QUERY PLAN` prüfen.

## 13. Schachnotation und Positionsidentität

```python
from chess_coach.openings import position_key
```

Regeln:

- SAN und UCI speichern;
- alle Züge mit `python-chess` auf einem echten Brett ausführen;
- intern nach jedem Halbzug den bestehenden `position_key(board)` berechnen,
  aber nur die belegte Zielstellung einer führenden Diagrammlinie als
  Runtime-Evidenz verknüpfen;
- Zugrecht, Rochaderechte und en-passant-Feld erhalten;
- Halbzug- und Zugzähler ignorieren;
- ein Fragment ab beispielsweise `8...` nur mit bekannter Ausgangsstellung validieren;
- unvollständige Prosa wie „pawn to e4, knight to f3, bishop to b5“ nicht als vollständige Variante interpretieren;
- niemals fehlende gegnerische Züge erfinden.

## 14. Claim- und Qualitätsregeln

Konservative Kandidatenerkennung:

- `%`, `percent`, `probability`, `win rate` → `statistic`, `unverified`;
- `should`, `recommended`, `consider` → `recommendation`, `source_only`;
- `avoid`, `mistake`, `flaw` → `warning`, `source_only`;
- `goal`, `purpose`, `plan`, `strategy` → `plan`, `source_only`.

Verwendung:

- `source_only`: nur als „Das Buch beschreibt/empfiehlt …“;
- `unverified`: nicht als normale Antwortbehauptung; bei expliziter Quellenfrage nur mit Warnung;
- `legality_checked`: Zugfolge legal, aber nicht automatisch gut;
- `engine_checked`: Enginekonfiguration und Zeitpunkt nachvollziehbar speichern;
- `rejected`: nie an den Coach ausliefern.

## 15. Mehrsprachigkeit

Das Referenzbuch ist Englisch, der Coach Deutsch. Eine testbare Alias-Tabelle ist Pflicht:

```text
Spanische Partie <-> Ruy Lopez <-> Spanish Game
Italienische Partie <-> Italian Game
Damengambit <-> Queen's Gambit
Sizilianische Verteidigung <-> Sicilian Defense
Französische Verteidigung <-> French Defense
Königsindische Verteidigung <-> King's Indian Defense
```

Im ersten Inkrement keine freie LLM-Übersetzung als verifizierten deutschen Fakt ausgeben. Sicherer UI-Umfang:

- deterministische deutsche Einleitung;
- deutsche, evidenzgebundene Wiedergabe ohne parallelen Originalausschnitt;
- Buch, Autor/Jahr und PDF-Seite als knappe Quellenangabe;
- Status „Buchquelle, nicht unabhängig geprüft“;
- bestehende deutsche Engine-/Brett-Erklärung separat.

Der englische Originaltext bleibt intern über `BookFact`, `source_ref` und die
Compiler-Diagnose nachvollziehbar, wird dem Lernenden im normalen Coaching-Flow
aber nicht zusätzlich zur deutschen Erklärung vorgelegt. Die Anwendung darf
nicht die inhaltliche Kontrolle auf den Lernenden abwälzen, indem sie ihn beide
Fassungen vergleichen lässt.

## 16. Runtime-Provider

```python
class BookKnowledgeBase:
    def status(self) -> dict[str, object]: ...

    def retrieve(
        self,
        *,
        question: str,
        board: chess.Board,
        opening: OpeningIdentity | None,
        focus_move: chess.Move | None,
        limit: int = 3,
        max_chars: int = 2500,
    ) -> BookEvidence: ...
```

Modelle:

```python
@dataclass(frozen=True, slots=True)
class BookCitation:
    book_id: str
    title: str
    author: str | None
    publication_year: int | None
    source_path: str
    page_start: int
    page_end: int
    source_ref: str

@dataclass(frozen=True, slots=True)
class BookFact:
    id: str
    text: str
    claim_type: str
    validation_status: str
    citation: BookCitation
    warnings: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class BookEvidence:
    facts: tuple[BookFact, ...]
    query_method: str
    truncated: bool
```

Die Runtime öffnet die DB read-only bzw. setzt `PRAGMA query_only = ON`. Bei fehlender oder inkompatibler DB liefert ein Null-Provider leere Evidenz und einen Health-Grund.

## 17. Retrieval

Deterministische Reihenfolge:

1. exakter `position_key` nach dem legalen Fokuszug;
2. exakter aktueller `position_key`;
3. aktuelle Opening-Identität mit Aliasexpansion;
4. legaler Fokuszug in SAN/UCI;
5. FTS5/BM25 über Frage, Titel, Pfad und Text;
6. benachbarte Chunks erst nach Primärtreffer.

Sobald exakte Positionsevidenz mit sicheren Claims gefunden wurde, wird nicht
mit breiten Opening- oder Texttreffern aufgefüllt. Ein reiner Opening-Treffer
darf allgemeine Pläne liefern, aber keine variantenbezogenen Warnungen oder
Empfehlungen.

Treffer vereinigen und deduplizieren. Keine rohen Scores verschiedener Kanäle addieren. Lexikographisch sortieren:

```text
exakte Position
vor Opening-Treffer
vor reinem Texttreffer
vor problembehaftetem Claim
danach BM25
danach stabile source_ref
```

Standard: höchstens drei diverse Treffer und insgesamt 2.500 Buchzeichen. Pro Buch und Abschnitt zunächst höchstens ein Treffer, sofern keine Vergleichsfrage vorliegt.

## 18. Integration in `CoachService`

`CoachService` erhält einen injizierbaren `BookKnowledgeBase`-Provider. Tests verwenden Null- oder Fake-Provider.

Erste Integrationsstelle ausschließlich `answer_question()`. Nach Auflösung des legalen Fokuszugs sowie der bestehenden Opening-/Engine-Fakten:

```text
question + board + opening + focus move
  -> BookKnowledgeBase.retrieve()
  -> BookEvidence
  -> separat an Message anhängen
```

Im ersten Inkrement Buchpassagen nicht ungeprüft in die vorhandenen Ollama-`answer_facts` geben. Diese bleiben aus Brett, Theorie und Engine abgeleitet. Buchmaterial erscheint separat als `references`.

Empfohlene Response:

```json
{
  "message": {
    "summary": "bestehende geprüfte deutsche Antwort",
    "details": "bestehende geprüfte deutsche Details",
    "references": [
      {
        "kind": "book",
        "title": "Chess Openings For Beginners",
        "author": "Stewart, Clyde",
      "year": 2021,
      "pdf_page_start": 19,
      "pdf_page_end": 20,
      "source_ref": "book_...:p19-p20:c0011",
      "status": "source_only",
      "warnings": ["unverified_statistic"]
      }
    ]
  }
}
```

Keinen absoluten Dateipfad an den Browser senden.

## 19. API und Frontend

`QuestionRequest` bleibt zunächst unverändert. Den Healthcheck ergänzen:

```json
{
  "books": {
    "available": true,
    "book_count": 1,
    "chunk_count": 105,
    "reason": null
  }
}
```

Frontend:

- `CoachMessage` um optionale `references` erweitern;
- unter einer Frageantwort einen eingeklappten Bereich „Buchquellen“ zeigen;
- Titel, Autor/Jahr, PDF-Seite und Status darstellen, aber nicht denselben Inhalt
  noch einmal als englischen Originalausschnitt;
- Quellen nicht mit Legalität/Theorie/Engine vermischen;
- keine PDF-Datei über den Webserver ausliefern;
- ohne Treffer keinen leeren Quellenbereich rendern.

## 20. Datenschutz und Lebenszyklus

- PDFs bleiben am lokalen Ursprungsort.
- Keine vollständigen Kapitel in Prompt oder API.
- harte Zeichenbudgets für Ausschnitte;
- lokale Pfade nur Backend/CLI, nie Browser;
- `remove BOOK_ID` löscht alle abgeleiteten Daten dieses Buchs einschließlich FTS;
- Inhaltshash, Schema-/Extraktionsversion und Importzeitpunkt speichern;
- PDF-Inhalt nicht an Cloudmodelle senden;
- Dokumenttext als untrusted input behandeln;
- weder PDF noch Knowledge-DB committen oder deployen.

## 21. Befunde aus dem Referenzbuch

Der Spike hat das konkrete PDF vermessen. Die Zahlen sind Engineering-Hinweise, kein fachlicher Goldstandard:

- 122 PDF-Seiten;
- 962 Textblöcke;
- 63 Abschnitte nach Zusammenführung mehrzeiliger Überschriften;
- 105 Such-Chunks;
- 482 heuristische Claims;
- 38 Bilder, davon 31 wahrscheinliche Brettdiagramme;
- nur eine vollständig parsebare nummerierte Kurzlinie: `1. d4 d5`;
- 32 statistische Aussagen mit notwendigem Warnstatus;
- sieben textarme Inhaltsseiten.

Das Buch beschreibt Züge meist in Prosa und lässt gegnerische Zwischenzüge aus. Der Compiler darf diese Lücken nicht auffüllen.

Regressionstest:

```text
Frage: „Warum spielt Weiß in der Spanischen Partie Bb5?“
Quelle: Ruy-Lopez-Abschnitt, PDF-Seiten 18 bis 20
Status: source_only
Nebenaussagen mit Prozentwerten: unverified
```

## 22. Automatische Tests

Tests dürfen nicht vom privaten PDF außerhalb des Repositories abhängen. Kleine XML-/Text-Fixtures und temporäre SQLite-Dateien verwenden.

### Import

- Metadaten-Fallback aus Dateinamen;
- Seiten-/Bounding-Box-Reihenfolge;
- mehrzeilige Überschrift wird eine Section;
- TOC wird nicht als normaler Treffer priorisiert;
- gleicher Hash wird idempotent aktualisiert;
- Reimport eines Buchs lässt andere unberührt;
- `remove` entfernt auch FTS-Zeilen;
- textarme Seite erzeugt Issue;
- inkompatible Schemaversion scheitert verständlich.

### Schach

- legale nummerierte Linie wird normalisiert;
- illegaler Zug wird markiert;
- späteres Fragment erfordert Ausgangsstellung;
- Positionsschlüssel entspricht `openings.position_key()`;
- Move-Counter ändern Identität nicht, Rochaderechte schon;
- unvollständige Prosa erzeugt keine erfundene Position.

### Retrieval

- „Spanische Partie“ findet „Ruy Lopez“;
- Positionstreffer steht vor FTS;
- Fokuszug verbessert passende Treffer;
- Zeichenbudget wird eingehalten;
- Statistik wird nicht als normaler BookFact ausgeliefert;
- Treffer werden diversifiziert;
- fehlende DB bzw. kein Treffer ergibt leere Evidenz;
- `EXPLAIN QUERY PLAN` bestätigt die vorgesehenen Indizes.

### Service/API/UI

- Frageantwort ohne Buchdatenbank unverändert;
- relevante Quelle erscheint in `references`;
- Quelle verändert weder `theory_match` noch Enginewerte oder Zugwahl;
- Ollama erhält keinen unkontrollierten Buchtext;
- Healthcheck meldet Status;
- API leakt keinen Pfad;
- Referenzfelder sind rückwärtskompatibel;
- UI ohne References unverändert;
- Quellenbereich nur bei Treffern, zugänglich und responsive.

## 23. Verifikation

```bash
.venv/bin/pytest
.venv/bin/ruff check backend scripts
npm run lint
npm test
git diff --check
```

Zusätzlich:

```text
PRAGMA integrity_check;
PRAGMA foreign_key_check;
Anzahl chunks == Anzahl FTS-Dokumente;
keine verwaiste Positionsevidenz;
EXPLAIN QUERY PLAN für Positions- und Issue-Abfragen;
```

Manueller Akzeptanztest:

1. Referenzbuch importieren.
2. `books`, `issues` und `verify` prüfen.
3. nach „Spanische Partie“ und „Sizilianische Verteidigung“ suchen.
4. Coach starten und Ruy-Lopez-Stellung erreichen.
5. „Warum spielt Weiß hier Bb5?“ fragen.
6. Engine-/Brettantwort muss unverändert bleiben.
7. Buchbeleg muss separat mit PDF-Seiten erscheinen.
8. Prozentwerte dürfen nicht als Coach-Wahrheit erscheinen.

## 24. Abnahmekriterien

- Coach funktioniert ohne Buchdatenbank unverändert.
- PDFs können idempotent importiert, gesucht und entfernt werden.
- Jede Passage hat Buch-ID, Titel, Seite und stabile `source_ref`.
- deutsche Aliasfrage findet den englischen Abschnitt.
- Buchpositionen verwenden denselben Key wie der Opening-DAG.
- unvollständige oder illegale Varianten werden nicht erfunden.
- ungeprüfte Statistiken werden nicht zur Coach-Wahrheit.
- `answer_question()` liefert Quellen separat.
- Buchwissen beeinflusst keine Zugwahl, Korrektur oder Enginebewertung.
- API leakt keine lokalen Pfade.
- Textbudgets werden eingehalten.
- Tests, Lint und Build sind grün.
- Architektur, Konfiguration und Datenherkunft sind dokumentiert.

## 25. Implementierungsreihenfolge

### Phase A: Offline-Compiler

1. Modelle und versioniertes Schema.
2. Poppler-Adapter.
3. Layout, Sections und Chunks.
4. FTS5, Aliase und Issues.
5. konservatives PGN/SAN-Parsing mit bestehendem `position_key()`.
6. CLI `ingest`, `books`, `search`, `issues`, `verify`, `remove`.
7. isolierte Tests und realer Referenzimport.

Noch keine Runtime-/UI-Änderung, bis dieser Teil stabil ist.

### Phase B: Runtime-Retrieval

1. `BookKnowledgeBase` und Null-Provider.
2. Konfiguration und Healthcheck.
3. Positions-/Alias-/FTS-Retrieval mit Budgets.
4. Integration nur in `answer_question()`.
5. API-Referenzen ohne Pfad.
6. Backend-Regressionstests.

### Phase C: UI

1. optionale `references` im TypeScript-Modell;
2. eingeklappter Bereich „Buchquellen“;
3. knappe Quellenmetadaten mit Seite und Status, ohne doppelten Quelltext;
4. responsive/zugängliche Darstellung;
5. Frontend-, Build- und Integrationstests.

### Phase D: Evaluation

Vor weiterer Technik messen:

- Trefferquote relevanter Buchstellen;
- Korrektheit der Seitenangaben;
- redundante oder nutzlose Belege;
- zusätzliche Latenz;
- pädagogischer Mehrwert;
- häufigste Ursachen fehlender Treffer.

Erst danach über Embeddings, Diagramm-FEN, strukturierte Übersetzung oder umfassende Claim-Validierung entscheiden.

## 26. Arbeitsweise und spätere Anschlussfähigkeit

- Vor Änderungen Git-Status prüfen und Nutzeränderungen erhalten.
- Bestehende Architektur erweitern, nicht ersetzen.
- In kleinen vertikalen Inkrementen arbeiten und jede Phase testen.
- reale Fehlerfälle als Regressionstest und im Project Journal festhalten;
- keine automatische Veröffentlichung: local-first;
- bei echten Produktentscheidungen mit großer Auswirkung den Benutzer fragen;
- technische Details innerhalb dieses Briefings selbständig entscheiden.

Spätere Erweiterungen nur anschlussfähig halten, nicht jetzt bauen:

- Diagramm-zu-FEN mit Konfidenz und Review;
- positions-/konzeptbewusste Vektorsuche;
- strukturierte deutsche Coaching-Karten;
- Engineprüfung ausgewählter Claims;
- Multi-Buch-Konsens und Dissens;
- Verknüpfung eigener Fehler mit Buchstellen;
- Repertoire-Linter und adaptive Wiederholung.

Die aktuelle Priorität lautet: **Buchwissen zuverlässig, sparsam, zitierbar und ohne Autoritätsvermischung in den bestehenden Coach bringen.**

## 27. Nachbesprechung: deutsche Ausgabe und lokale Verarbeitung

Am 2026-09-09 bestätigte der Lernende zwei Produktentscheidungen:

1. Kurze, für die aktuelle Frage abgerufene Buchpassagen dürfen automatisch
   durch das lokale Ollama-Modell verarbeitet werden. Das Buch verlässt den
   Rechner nicht; das ganze Buch wird nie in einen Prompt gegeben.
2. Der englische Ausgangstext soll nicht parallel zur deutschen Erklärung in
   der normalen Oberfläche erscheinen. Der Lernende soll nicht zweimal lesen
   oder die Übersetzungs- und Grounding-Prüfung selbst übernehmen müssen.

Die Synthese muss deshalb jeden ausgegebenen Erklärungssatz auf Evidenz-IDs
zurückführen. Zugnotation, Varianten, Zahlen, Opening-Namen und Brettbehauptungen
werden deterministisch gegen die bereits vorhandenen Fakten geprüft. Eine
zweite lokale Modellprüfung darf zusätzliche Fehler finden, gilt aber nicht als
Beweis. Wenn eine strategische Paraphrase nicht hinreichend auf die ausgewählte
Buchpassage zurückgeführt werden kann, muss der Coach konservativ formulieren
oder auf eine sichere Antwort zurückfallen. Originaltext und Bounding Boxes
bleiben für Tests, Compiler-Diagnose und spätere redaktionelle Prüfung erhalten.

Der Lernende hat diesen Fallback ausdrücklich als sehr wichtige Produktregel
bestätigt. Eine geeignete Formulierung lautet beispielsweise:

> Ich kann den Zug schachlich bewerten, habe aber noch keine ausreichend
> belegte Erklärung für seinen langfristigen Zweck.

Bereits verifizierte Legalitäts-, Brett-, Eröffnungs- oder Enginefakten dürfen
daneben weiterhin erscheinen. Die Wissenslücke darf jedoch weder durch eine
allgemeine Schachfloskel noch durch eine frei erzeugte strategische Behauptung
verdeckt werden. Dieser Fall benötigt einen eigenen maschinenlesbaren
Fallback-Grund und einen Regressionstest.

## 28. Implementierungsnachtrag: kontextuelle Linien und Relevanzgrenze

Der erste Zwei-Bücher-Qualitätslauf ergänzt zwei verbindliche Regeln:

1. Eine abgekürzte Linie darf nur aus genau einer legalen Position der nächsten
   bereits verifizierten Elternlinie rekonstruiert werden. Eltern-ID, Methode,
   Start-FEN und absolute Ply-Grenzen bleiben gespeichert. Nur die Endposition
   des rekonstruierten Fragments ist ein Evidenzanker. Diagramme bleiben ohne
   unabhängig prüfbare FEN reine Inventardaten.
2. Wenn keine Eröffnung erkannt wurde, sind globale SAN- und Fragesuchen
   verboten. Ein Treffer zu `c3` in irgendeinem anderen Kapitel ist zwar
   zitierbar, aber nicht relevant für die aktuelle Stellung. Dann ist nur ein
   exakter Positionsanker zulässig.

`benchmarks/fixtures/explanation_quality_cases.json` ist ab jetzt der minimale
Abnahmekorpus für `c3`, `Na2`, `a4`, `Nd5`, `Ra6` und `Bb5`. Neue reale
Beschwerden werden als weitere Fälle ergänzt. ADR 0008 und die Evaluation
`2026-09-09-deep-explanation-quality-cycle.md` dokumentieren Methode, verworfene
Optionen, Latenz und verbleibende Grenzen.
