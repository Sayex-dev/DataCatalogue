#!/usr/bin/env python3
"""
PDF Renderer - Compiles LaTeX to PDF using pdflatex.

Auto-detects pdflatex on Windows (MiKTeX, TeX Live) and Linux.
Handles multiple compilation passes for TOC and references.
"""

import os
import sys
import subprocess
import shutil


def find_pdflatex():
    """Find pdflatex executable. Returns path or raises FileNotFoundError."""
    # 1. Try plain name (works if it's in PATH)
    if shutil.which('pdflatex'):
        return 'pdflatex'
    if shutil.which('pdflatex.exe'):
        return 'pdflatex.exe'

    # 2. Windows: search common MiKTeX and TeX Live locations
    if sys.platform == 'win32':
        candidates = [
            # MiKTeX (user install)
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe'),
            os.path.expandvars(r'%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x86\pdflatex.exe'),
            # MiKTeX (system install)
            r'C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe',
            r'C:\Program Files (x86)\MiKTeX\miktex\bin\x86\pdflatex.exe',
            # TeX Live
            r'C:\texlive\2024\bin\windows\pdflatex.exe',
            r'C:\texlive\2023\bin\windows\pdflatex.exe',
            r'C:\texlive\2025\bin\windows\pdflatex.exe',
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path

        # 3. Last resort: dir search on whole C: (slow, only if nothing else works)
        try:
            result = subprocess.run(
                ['where', '/r', 'C:\\', 'pdflatex.exe'],
                capture_output=True, text=True, timeout=30
            )
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.lower().endswith('pdflatex.exe') and os.path.isfile(line):
                    return line
        except Exception:
            pass

    raise FileNotFoundError(
        'pdflatex not found.\n\n'
        'Install MiKTeX from https://miktex.org/download\n'
        'or TeX Live from https://tug.org/texlive/\n'
        'After installation, ensure pdflatex is in your PATH.'
    )


def run_pdflatex(tex_file, workdir, passes=2):
    """Run pdflatex with multiple passes for TOC."""

    pdflatex = find_pdflatex()
    tex_basename = os.path.splitext(os.path.basename(tex_file))[0]

    for pass_num in range(1, passes + 1):
        print(f"[render] Pass {pass_num}/{passes} (using {pdflatex})...")

        cmd = [
            pdflatex,
            '-interaction=nonstopmode',
            '-halt-on-error',
            '-output-directory', '.',
            tex_file,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='latin-1',
            cwd=workdir,
            timeout=300,
        )

        if result.returncode != 0:
            log_file = os.path.join(workdir, f"{tex_basename}.log")
            errors = extract_errors(result.stdout, result.stderr)
            print(f"[render] ERROR on pass {pass_num}:")
            for err in errors:
                print(f"  {err}")

            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                    log = f.read()
                for line in log.split('\n'):
                    if line.startswith('!'):
                        print(f"  LOG: {line.strip()}")

            return False

    pdf_path = os.path.join(workdir, f"{tex_basename}.pdf")
    if os.path.exists(pdf_path):
        print(f"[render] PDF created: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
        return True
    else:
        print(f"[render] ERROR: PDF not found at {pdf_path}")
        return False


def extract_errors(stdout, stderr):
    """Extract error messages from LaTeX output."""
    errors = []
    for line in (stdout + '\n' + stderr).split('\n'):
        if line.startswith('!') or 'Error' in line or 'error' in line.lower():
            errors.append(line.strip())
    if not errors:
        errors = (stdout + stderr).split('\n')[-20:]
    return errors[:10]


def render(tex_file, output_pdf_path, workdir=None):
    """Compile LaTeX to PDF."""

    tex_file = os.path.abspath(tex_file)
    tex_dir = os.path.dirname(tex_file)

    if workdir is None:
        workdir = tex_dir

    os.makedirs(workdir, exist_ok=True)

    styling_file = os.path.join(tex_dir, 'catalog_styling.tex')
    if not os.path.exists(styling_file):
        print(f"[render] WARNING: styling file not found at {styling_file}")

    os.makedirs(os.path.join(tex_dir, 'maps'), exist_ok=True)

    success = run_pdflatex(tex_file, workdir, passes=2)

    if success:
        pdf_basename = os.path.splitext(os.path.basename(tex_file))[0]
        generated_pdf = os.path.join(workdir, f"{pdf_basename}.pdf")

        if os.path.abspath(generated_pdf) != os.path.abspath(output_pdf_path):
            shutil.copy2(generated_pdf, output_pdf_path)
            print(f"[render] Copied to: {output_pdf_path}")

    return success


if __name__ == '__main__':
    tex_file = sys.argv[1] if len(sys.argv) > 1 else 'latex_temp/catalog.tex'
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else 'katalog_output.pdf'
    workdir = sys.argv[3] if len(sys.argv) > 3 else 'latex_temp'

    try:
        success = render(tex_file, output_pdf, workdir)
        sys.exit(0 if success else 1)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
