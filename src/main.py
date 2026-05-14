#!/usr/bin/env python3
"""
Katalog Generator - Main orchestration script.

Pipeline:
1. data_processor.py  → reads CSV, produces structured JSON
2. map_generator.py   → generates location maps
3. generate_latex.py  → produces LaTeX files from JSON
4. render_pdf.py      → compiles LaTeX to PDF
"""

import os
import sys
import subprocess
import json


def main():
    # Paths
    base = '.'
    src = os.path.join(base, 'src')
    csv_path = os.path.join(base, 'artefakte_export.csv')
    data_path = os.path.join(base, 'artifacts_data.json')
    latex_dir = os.path.join(base, 'latex_temp')
    map_dir = os.path.join(latex_dir, 'maps')
    bilder_dir = os.path.join(base, 'bilder')
    tex_file = os.path.join(latex_dir, 'catalog.tex')
    pdf_output = os.path.join(base, 'katalog_output.pdf')
    
    # Ensure directories
    os.makedirs(src, exist_ok=True)
    os.makedirs(latex_dir, exist_ok=True)
    os.makedirs(map_dir, exist_ok=True)
    
    print("=" * 60)
    print("KATALOG GENERATOR")
    print("=" * 60)
    
    # ── Step 1: Data Processing ──────────────────────────────
    print("\n[1/4] Processing CSV data...")
    result = subprocess.run(
        [sys.executable, os.path.join(src, 'data_processor.py'), csv_path, data_path],
        capture_output=True, text=True, timeout=60
    )
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        sys.exit(1)
    
    # ── Step 2: Map Generation ───────────────────────────────
    print("\n[2/4] Generating location maps (may download cartopy data on first run)...")
    result = subprocess.run(
        [sys.executable, os.path.join(src, 'map_generator.py'), data_path, map_dir, bilder_dir],
        capture_output=True, text=True, timeout=600
    )
    print(result.stdout)
    if result.returncode != 0:
        print("WARNING (maps):", result.stderr)
        # Non-fatal: continue without maps
    
    # ── Step 3: LaTeX Generation ─────────────────────────────
    print("\n[3/4] Generating LaTeX document...")
    result = subprocess.run(
        [sys.executable, os.path.join(src, 'generate_latex.py'), data_path, tex_file, bilder_dir, map_dir],
        capture_output=True, text=True, timeout=60
    )
    print(result.stdout)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        sys.exit(1)
    
    # Verify LaTeX output
    if os.path.exists(tex_file):
        print(f"[main] LaTeX file: {tex_file} ({os.path.getsize(tex_file)} bytes)")
    
    # ── Step 4: PDF Rendering ────────────────────────────────
    print("\n[4/4] Rendering PDF...")
    result = subprocess.run(
        [sys.executable, os.path.join(src, 'render_pdf.py'), tex_file, pdf_output, latex_dir],
        capture_output=True, text=True, timeout=600
    )
    print(result.stdout)
    if result.returncode != 0:
        print("RENDER ERRORS:")
        stderr = result.stderr
        # Show only the last meaningful lines (skip traceback clutter)
        lines = [l for l in stderr.split('\n') if l.strip() and 'File "' not in l and '  File ' not in l]
        for line in lines[-15:]:
            print(f"  {line.strip()}")
        sys.exit(1)
    
    # ── Result ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if os.path.exists(pdf_output):
        size_kb = os.path.getsize(pdf_output) / 1024
        print(f"SUCCESS! PDF generated: {pdf_output}")
        print(f"Size: {size_kb:.1f} KB")
    else:
        print("FAILED: PDF not generated")
        sys.exit(1)
    
    print("=" * 60)


if __name__ == '__main__':
    main()
