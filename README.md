# Katalog-Generator – Bedienungsanleitung

Erstellt aus einer CSV-Datei mit Artefaktdaten einen strukturierten, druckfertigen
Sammlungskatalog als PDF.

## Voraussetzungen

- **Python 3.10+**
- **LaTeX** (TeX Live, mindestens `texlive-latex-recommended`,
  `texlive-latex-extra`, `texlive-lang-german`, `texlive-fonts-recommended`)
- **Python-Pakete** (siehe `requirements.txt`)

### Installation der Abhängigkeiten

```bash
# LaTeX (Debian/Ubuntu)
sudo apt-get install texlive-latex-recommended texlive-latex-extra \
  texlive-lang-german texlive-fonts-recommended texlive-pictures

# Python-Pakete
pip install -r requirements.txt
```

## Ordnerstruktur

```
/opt/hermes/work/
├── artefakte_export.csv    ← Eingabedaten (CSV)
├── bilder/                  ← Bilddateien der Artefakte
├── src/                     ← Quellcode
│   ├── data_processor.py
│   ├── map_generator.py
│   ├── generate_latex.py
│   ├── render_pdf.py
│   ├── main.py
│   └── requirements.txt
├── latex_temp/              ← Temporäre LaTeX-Dateien
│   ├── catalog_styling.tex  ← Layout/Styling
│   └── maps/                ← Generierte Standortkarten
└── katalog_output.pdf       ← Finales PDF
```

## Ausführung

### Komplettpipeline (empfohlen)

```bash
cd /opt/hermes/work
python3 src/main.py
```

Das Skript führt alle vier Schritte nacheinander aus und erzeugt
`katalog_output.pdf`.

### Einzelschritte

Falls du nur einen bestimmten Schritt wiederholen willst:

```bash
# 1. CSV einlesen und strukturieren → artifacts_data.json
python3 src/data_processor.py \
  /opt/hermes/work/artefakte_export.csv \
  /opt/hermes/work/artifacts_data.json

# 2. Standortkarten generieren → latex_temp/maps/
python3 src/map_generator.py \
  /opt/hermes/work/artifacts_data.json \
  /opt/hermes/work/latex_temp/maps \
  /opt/hermes/work/bilder

# 3. LaTeX-Dokument erzeugen → latex_temp/catalog.tex
python3 src/generate_latex.py \
  /opt/hermes/work/artifacts_data.json \
  /opt/hermes/work/latex_temp/catalog.tex \
  /opt/hermes/work/bilder \
  /opt/hermes/work/latex_temp/maps

# 4. PDF kompilieren → katalog_output.pdf
python3 src/render_pdf.py \
  /opt/hermes/work/latex_temp/catalog.tex \
  /opt/hermes/work/katalog_output.pdf \
  /opt/hermes/work/latex_temp
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
| `Object ID`, `Name`, `ID` | Identifikation des Artefakts |
| `Gattung`, `Objekttyp` | Klassifikation (für Sortierung und TOC) |
| `Material`, `Grösse`, `Datierung`, `Kulturkreis` | Objektdaten |
| `Künstler`, `Erhaltung` | Zusätzliche Metadaten |
| `Beschreibung extern`, `Beschreibung durch MIE` | Beschreibungstexte |
| `Katalog Fischer`, `Annotationen Kataloge` | Referenzen Auktionskatalog |
| `Referenz in Literatur`, `Vergleiche` | Literaturangaben |
| `Bild` | Dateiname des Bildes (im `bilder/`-Ordner) |
| `[Fundort] *` | Fundort-Subfelder (Geometrie, Name, Datum) |
| `[in collection] *` | Sammlungs-Subfelder (Standort, Sammler, Zeitraum) |

Mehrere Zeilen mit derselben `Object ID` werden automatisch zu einem
Artefakt zusammengeführt (flache Datenstruktur für zeitliche Verläufe).

## Katalognummerierung

Format: `<Gattung>.<Objekttyp>.<Laufnummer>` (z. B. `1.4.2`)

- **Erste Ziffer**: Alphabetische Position der Gattung
- **Zweite Ziffer**: Position des Objekttyps innerhalb der Gattung
- **Dritte Ziffer**: Laufende Nummer innerhalb des Objekttyps

## Fehlerbehandlung

- **Fehlendes Bild** (Feld `Bild` belegt, Datei nicht vorhanden):
  Platzhalter mit Dateinamen wird eingefügt.
- **Leeres Bildfeld**: Kein Bild, keine Meldung.
- **Abweichende Dateiendung** (z. B. `.jpg.jpg` statt `.jpg`):
  wird automatisch gefunden.
- **Fehlende Geometrie-Daten**: keine Standortkarte für dieses Artefakt.
