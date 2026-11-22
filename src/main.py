#!/usr/bin/env python3
"""
Katalog Generator - Main orchestration script.

Pipeline:
1. data_processor.py  → reads CSV, produces structured JSON
2. generate_latex.py  → produces LaTeX files from JSON
3. render_pdf.py      → compiles LaTeX to PDF

Paths are resolved relative to the repository root, so the script can be
started from anywhere.
"""

import os
import sys
import subprocess


def paths():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(root, 'src')
    latex_dir = os.path.join(root, 'latex_temp')
    return {
        'root': root,
        'src': src,
        'csv': os.path.join(root, 'artefakte_export.csv'),
        'data': os.path.join(root, 'artifacts_data.json'),
        'latex_dir': latex_dir,
        'bilder': os.path.join(root, 'bilder'),
        'tex': os.path.join(latex_dir, 'catalog.tex'),
        'pdf': os.path.join(root, 'katalog_output.pdf'),
    }


def run_step(label, script, args, timeout):
    """Run one pipeline step; abort the pipeline if it fails."""
    print(f'\n{label}')
    try:
        result = subprocess.run(
            [sys.executable, script] + args,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f'ERROR: {os.path.basename(script)} timed out after {timeout}s')
        sys.exit(1)

    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        print(f'ERROR in {os.path.basename(script)}:')
        lines = [l for l in result.stderr.splitlines()
                 if l.strip() and 'File "' not in l and '  File ' not in l]
        for line in lines[-15:]:
            print(f'  {line.strip()}')
        sys.exit(1)


def main():
    p = paths()
    os.makedirs(p['latex_dir'], exist_ok=True)

    print('=' * 60)
    print('KATALOG GENERATOR')
    print('=' * 60)
    print(f'[main] Project root: {p["root"]}')

    if not os.path.isfile(p['csv']):
        print(f'[main] ERROR: input CSV not found: {p["csv"]}')
        sys.exit(1)

    run_step('[1/3] Processing CSV data...',
             os.path.join(p['src'], 'data_processor.py'),
             [p['csv'], p['data']], timeout=60)

    run_step('[2/3] Generating LaTeX document...',
             os.path.join(p['src'], 'generate_latex.py'),
             [p['data'], p['tex'], p['bilder']], timeout=120)

    if os.path.exists(p['tex']):
        print(f'[main] LaTeX file: {p["tex"]} '
              f'({os.path.getsize(p["tex"])} bytes)')

    run_step('[3/3] Rendering PDF...',
             os.path.join(p['src'], 'render_pdf.py'),
             [p['tex'], p['pdf'], p['latex_dir']], timeout=900)

    print('\n' + '=' * 60)
    if os.path.exists(p['pdf']):
        print(f'SUCCESS! PDF generated: {p["pdf"]}')
        print(f'Size: {os.path.getsize(p["pdf"]) / 1024:.1f} KB')
    else:
        print('FAILED: PDF not generated')
        sys.exit(1)
    print('=' * 60)


if __name__ == '__main__':
    main()
