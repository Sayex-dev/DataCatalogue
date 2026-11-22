# Katalog-Generator – Bedienungsanleitung

Erstellt aus einer CSV-Datei mit Artefaktdaten einen strukturierten, druckfertigen
Sammlungskatalog als PDF.

## Schnellstart mit Docker (empfohlen)

Keine manuelle Installation von LaTeX oder Python-Abhängigkeiten nötig:

```bash
docker compose up
```

Beim ersten Start wird das Image gebaut (einmalig, ~1.5 GB).
Danach liegt das PDF unter `katalog_output.pdf`.

Falls Docker nicht installiert ist, folge der manuellen Installation unten.

## Voraussetzungen (manuelle Installation)

- **Python 3.10+** (nur Standardbibliothek, keine externen Pakete)
- **LaTeX** (TeX Live, mindestens `texlive-latex-recommended`,
  `texlive-latex-extra`, `texlive-lang-german`, `texlive-fonts-recommended`,
  `tex-gyre`)

### Installation der Abhängigkeiten

```bash
# LaTeX (Debian/Ubuntu)
sudo apt-get install texlive-latex-recommended texlive-latex-extra \
  texlive-lang-german texlive-fonts-recommended tex-gyre texlive-pictures
```

## Ordnerstruktur

```
<projekt>/
├── artefakte_export.csv    ← Eingabedaten (CSV)
├── bilder/                  ← Bilddateien der Artefakte
├── src/                     ← Quellcode
│   ├── data_processor.py
│   ├── generate_latex.py
│   ├── render_pdf.py
│   └── main.py
├── latex_temp/              ← Temporäre LaTeX-Dateien
│   ├── catalog_styling.tex  ← Layout/Styling
│   └── catalog.tex          ← Generiertes Dokument
├── artifacts_data.json      ← Zwischendaten (generiert)
├── katalog_output.pdf       ← Finales PDF
└── requirements.txt
```

## Ausführung

### Komplettpipeline (empfohlen)

```bash
python3 src/main.py
```

`main.py` ermittelt den Projektordner über seinen eigenen Pfad, du kannst es
also aus jedem Verzeichnis starten. Es führt alle drei Schritte nacheinander
aus und erzeugt `katalog_output.pdf`.

### Einzelschritte

Falls du nur einen bestimmten Schritt wiederholen willst (relative Pfade,
vom Projektordner aus):

```bash
# 1. CSV einlesen und strukturieren → artifacts_data.json
python3 src/data_processor.py artefakte_export.csv artifacts_data.json

# 2. LaTeX-Dokument erzeugen → latex_temp/catalog.tex
python3 src/generate_latex.py \
  artifacts_data.json latex_temp/catalog.tex bilder

# 3. PDF kompilieren → katalog_output.pdf
python3 src/render_pdf.py \
  latex_temp/catalog.tex katalog_output.pdf latex_temp
```

## Pfade anpassen

Das Tool ist so gebaut, dass es mit beliebigen Pfaden funktioniert.
Passe die Aufrufargumente einfach an deine Verzeichnisstruktur an.
Die Datei `artefakte_export.csv` muss **unverändert** bleiben – das Tool
liest nur daraus.

## CSV-Format

Die CSV-Datei muss folgende Spalten enthalten (flache Struktur mit
Subobjektfeldern in `[Klammern]`):

| Feld | Beschreibung |
|---|---|
| `Object ID`, `Name` | Identifikation des Artefakts (Pflicht) |
| `Materialgattung` (alt: `Gattung`) | Klassifikation (für Sortierung und TOC) |
| `Objektgattung` (alt: `Objekttyp`) | Zweite Klassifikationsebene |
| `Materialien` (alt: `Material`), `Grösse`, `Datierung`, `Kulturkreis` | Objektdaten |
| `Künstler`, `Erhaltung` | Zusätzliche Metadaten |
| `Beschreibung Katalog Fischer`, `Beschreibung extern`, `Beschreibung durch MIE` | Beschreibungstexte |
| `Lot-Nr. Katalog Fischer 1936` (alt: `Katalog Fischer`), `Anmerkungen` (alt: `Annotationen Kataloge`) | Referenzen Auktionskatalog |
| `Referenz in Literatur`, `Vergleiche`, `Auktionen und Verkäufe` (alt: `Auktionen`) | Literatur- und Auktionsangaben |
| `Provenienz`, `aktueller Standort`, `aktuelle Eigentümer:in` (alt: `Eigentümer`), `Status` | Bestand / Steckbrief |
| `Inv. Nr. Archäologische Sammlung UZH`, `Platzierung in Haus` | Steckbrief |
| `Bild`, `Bildreferenz`, `Bildquelle` | Bilder (`;`-getrennt), Bildbeschreibung, Bildherkunft |
| `[Fundort] *` | Fundort-Subfelder (Geometrie, Name, Datum) |
| `[in collection] *` | Sammlungs-Subfelder (Standort, Sammler, Zeitraum) |

**Spalten umbenannt?** Alle Zugriffe laufen über `COLUMN_ALIASES` in
[src/data_processor.py](src/data_processor.py). Genügt ein Eintrag dort, und
der neue Export funktioniert wieder. Fehlt eine Pflichtspalte oder eine
optionale Spalte ganz, meldet das Skript das beim Start mit Klartext.

Mehrere Zeilen mit derselben `Object ID` werden automatisch zu einem
Artefakt zusammengeführt (flache Datenstruktur für zeitliche Verläufe).

Datumswerte dürfen `-∞` (unbekannter Anfang) und `∞` (andauernd) enthalten;
beide werden zu Sortierschlüsseln und Anzeigetexten normalisiert.

## Katalognummerierung

Format: `<Gattung>.<Objekttyp>.<Laufnummer>` (z. B. `1.4.2`)

- **Erste Ziffer**: Alphabetische Position der Gattung
- **Zweite Ziffer**: Position des Objekttyps innerhalb der Gattung
- **Dritte Ziffer**: Laufende Nummer innerhalb des Objekttyps

Ist `Objekttyp` bei einem Objekt leer (im aktuellen Export der Normalfall),
landet es im Bucket `1` — die Nummer bleibt dadurch eindeutig.

## Fehlerbehandlung

- **Fehlendes Bild** (Feld `Bild` belegt, Datei nicht vorhanden):
  Platzhalter mit Dateinamen wird eingefügt.
- **Leeres Bildfeld**: Kein Bild, keine Meldung.
- **Abweichende Dateiendung** (z. B. `.jpg.jpg` statt `.jpg`):
  wird automatisch gefunden.
- **Fehlende Geometrie-Daten**: kein Standortverlauf für dieses Artefakt.
- **Unbekannte Sonderzeichen**: werden, soweit möglich, nach LaTeX übersetzt
  (`š` → `\v{s}`, `×` → `\times`, `∞` → `\infty`). Alles ohne Zuordnung wird
  am Ende von Schritt 2 mit `U+XXXX` gemeldet, statt pdflatex abstürzen zu
  lassen.

## Bekannte Einschränkungen des aktuellen Exports

Diese Punkte sind Datenlieferungen, nicht Code-Fehler:

- **Tafel-Angaben fehlen**: `Katalog Fischer` enthielt früher Lot *und*
  Tafelverweis (z. B. `210. Taf. 39`). Die neue Spalte
  `Lot-Nr. Katalog Fischer 1936` enthält nur die Nummer und ist nur bei
  wenigen Objekten gefüllt.
- **Material (Stoff) fehlt**: Werte wie `Marmor, weiss` oder `Ton` sind im
  neuen Export nicht mehr enthalten; `Materialien` ist nur bei wenigen
  Objekten befüllt.
- **Objekttyp praktisch leer**: `Objektgattung`/`Obergattung` sind nur bei
  einem Bruchteil der Objekte gesetzt.
- **Bilder**: `bilder/` enthält nur einen Teil der im CSV referenzierten
  Dateien; der Rest wird als Platzhalter gerendert.
