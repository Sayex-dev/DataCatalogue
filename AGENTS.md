# AGENTS.md

Instructions for AI agents working in this repository.

## Working rules

- Always use the tools provided by the IDE when possible (file view/edit,
  search, problems/diagnostics, terminal) instead of ad-hoc shell workarounds.

## Project

Generates a print-ready collection catalogue PDF from a CSV export of artifact
data. Python standard library only, plus LaTeX for rendering.

```
artefakte_export.csv    input data (CSV)
bilder/                 artifact image files
src/                    source code
latex_temp/             generated LaTeX (catalog_styling.tex, catalog.tex)
artifacts_data.json     generated intermediate data
katalog_output.pdf      final PDF
```

## Commands

Full pipeline (works from any directory):

```bash
python3 src/main.py
```

Individual steps (relative paths, from the project root):

```bash
python3 src/data_processor.py artefakte_export.csv artifacts_data.json
python3 src/generate_latex.py artifacts_data.json latex_temp/catalog.tex bilder
python3 src/render_pdf.py latex_temp/catalog.tex katalog_output.pdf latex_temp
```

Docker alternative: `docker compose up`.

## Code map

- `src/data_processor.py` — CSV parsing, column aliases (`COLUMN_ALIASES`),
  merging rows by `Object ID`, catalogue numbering.
- `src/generate_latex.py` — LaTeX generation: entry layout, metadata fields,
  image blocks, location history table.
- `src/render_pdf.py` — pdflatex invocation.
- `src/main.py` — orchestrates the three steps.

## Conventions

- Column names are resolved through `COLUMN_ALIASES` in
  `src/data_processor.py`; add an alias there when the export renames a column.
- Catalogue number format: `<Gattung>.<Objekttyp>.<Laufnummer>` (e.g. `1.4.2`).
- Missing image file (field `Bildreferenz` set, file absent) → placeholder with
  the file name. Empty `Bildreferenz` → no image, no placeholder.
- `Abbildungsnachweis` is `;`-separated and positionally aligned with
  `Bildreferenz` (reference 1 ↔ nachweis 1); it is printed below each image.
- Unmapped special characters are reported as `U+XXXX` at the end of step 2
  instead of crashing pdflatex.
