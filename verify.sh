#!/bin/sh
# Build the catalogue and render the requested PDF pages to PNG.
#
# Usage: verify.sh [PAGE ...]
#   PAGE  1-based page number of the finished PDF. Defaults to 1.
#
# Output: /app/out/page-<N>.png plus /app/out/report.txt with the LaTeX
# statistics (page count, errors, undefined references, overfull boxes).
set -e

PAGES="$*"
[ -z "$PAGES" ] && PAGES=1

mkdir -p /app/out

echo "=== pipeline ==="
python3 src/main.py

echo
echo "=== rendering pages: $PAGES ==="
python3 - "$PAGES" <<'PY'
import sys
import pymupdf

pages = [int(p) for p in sys.argv[1].split()]
doc = pymupdf.open('/app/katalog_output.pdf')

for page in pages:
    if not 1 <= page <= doc.page_count:
        print(f'page {page}: out of range (1-{doc.page_count})')
        continue
    target = f'/app/out/page-{page}.png'
    doc[page - 1].get_pixmap(dpi=110).save(target)
    print(f'page {page}: {target}')
PY

echo
echo "=== report ==="
python3 - <<'PY' | tee /app/out/report.txt
import re

log = open('/app/latex_temp/catalog.log', encoding='utf-8', errors='replace').read()

written = re.search(r'Output written on [^\r\n]+', log)
print(written.group(0) if written else 'Output written: UNKNOWN')
print('errors:', len(re.findall(r'(?m)^!', log)))
print('undefined references:', len(re.findall(r'(?i)undefined', log)))
print('overfull hbox:', len(re.findall(r'Overfull \\hbox', log)))
print('overfull vbox:', len(re.findall(r'Overfull \\vbox', log)))
PY
