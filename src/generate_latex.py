#!/usr/bin/env python3
"""
LaTeX Generator - Produces .tex file from structured artifact data.
"""

import json
import os
import sys
import re


def latex_escape(text):
    """Escape text for LaTeX body text. Unicode → LaTeX after normal escaping."""
    if not text:
        return ''

    # Character-level escaping (skip $ so math mode survives)
    escape_map = {
        '&': r'\&', '%': r'\%', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\^{}',
    }
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text) and text[i+1].isalpha():
            result.append(text[i])
            i += 1
            while i < len(text) and text[i].isalpha():
                result.append(text[i])
                i += 1
            continue
        elif text[i] in escape_map:
            result.append(escape_map[text[i]])
        else:
            result.append(text[i])
        i += 1

    escaped = ''.join(result)

    # Unicode → LaTeX (after escaping, so math-mode $ stays intact)
    escaped = escaped.replace('\u221e', r'\(\infty\)')   # ∞
    escaped = escaped.replace('\u2013', '--')            # –
    escaped = escaped.replace('\u2014', '---')           # —
    escaped = escaped.replace('\u201e', '"')             # „
    escaped = escaped.replace('\u201c', '"')             # "
    escaped = escaped.replace('\u2026', '...')           # …

    return escaped


def escape_meta(text):
    """Escape text for metadata fields. Newlines → \\, then escape + Unicode."""
    if not text:
        return ''

    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    text = r' \\ '.join(line.strip() for line in lines if line.strip())

    escape_map = {
        '&': r'\&', '%': r'\%', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\^{}',
    }
    for char, repl in escape_map.items():
        text = text.replace(char, repl)

    text = text.replace('\u221e', r'\(\infty\)')
    text = text.replace('\u2013', '--')
    text = text.replace('\u2014', '---')
    text = text.replace('\u201e', '"')
    text = text.replace('\u201c', '"')
    text = text.replace('\u2026', '...')

    return text


def format_body_text(text):
    """Blank lines → \\par, single newlines → spaces."""
    if not text:
        return ''
    paragraphs = re.split(r'\n\s*\n', text)
    formatted = []
    for para in paragraphs:
        para = re.sub(r'\s*\n\s*', ' ', para.strip())
        if para:
            formatted.append(para)
    return '\n\n\\par\n\n'.join(formatted)


def find_image_file(img_name, bilder_dir):
    """Find image file, handling naming mismatches like .jpg.jpg."""
    exact = os.path.join(bilder_dir, img_name)
    if os.path.isfile(exact):
        return exact

    # Try matching by base name (strip extensions iteratively)
    base = img_name
    while True:
        base, ext = os.path.splitext(base)
        if not ext:
            break
        for fname in os.listdir(bilder_dir):
            if fname.startswith(base) and os.path.isfile(os.path.join(bilder_dir, fname)):
                return os.path.join(bilder_dir, fname)

    return None


def format_location_table(artifact):
    """Generate longtable of chronological location history (without Typ column)."""
    locations = artifact.get('all_locations', [])
    if not locations:
        return ''

    def fmt_date(date_str):
        """Convert date to DD.MM.YYYY dot format."""
        if not date_str:
            return ''
        s = date_str.strip()
        if s == '\u221e':
            return 'heute'
        # Remove trailing .0 on year-only floats (e.g. "1800.0")
        if s.endswith('.0') and s[:-2].replace('.', '', 1).isdigit():
            return s[:-2]
        # YYYY-MM-DD → DD.MM.YYYY
        parts = s.split('-')
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return f'{parts[2]}.{parts[1]}.{parts[0]}'
        # YYYY-MM → MM.YYYY (edge case)
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            return f'{parts[1]}.{parts[0]}'
        return s

    rows = []
    for loc in locations:
        label = escape_meta(loc.get('label', ''))
        ds = fmt_date(loc.get('date_start', ''))
        de = fmt_date(loc.get('date_end', ''))

        # Date range with fixed-width left box → all dashes aligned
        if ds and de:
            date_str = f'\\makebox[3cm][r]{{{ds}}} -- {de}'
        elif ds:
            date_str = f'\\makebox[3cm][r]{{{ds}}} --'
        elif de:
            date_str = f'\\makebox[3cm][r]{{}} -- {de}'
        else:
            date_str = 'unbekannt'

        sammler = escape_meta(loc.get('sammler', ''))

        row = f'{label} & {date_str}'
        if sammler and not loc.get('is_fundort'):
            row += f' & {sammler}'
        else:
            row += r' & \hspace{0pt}'
        row += r' \\'
        rows.append(row)

    if not rows:
        return ''

    lines = [
        r'\vspace{8pt}',
        r'{\fontsize{9pt}{11pt}\selectfont\color{metagray}',
        r'\textbf{Standortverlauf (chronologisch)}\\',
        r'\vspace{2pt}',
        r'\begin{longtable}{@{}>{\raggedright\arraybackslash}p{5cm}@{\hspace{6pt}}>{\raggedright\arraybackslash}p{5.3cm}@{\hspace{6pt}}>{\raggedright\arraybackslash}p{5.3cm}@{}}',
        r'\toprule',
        r'\textbf{Ort} & \multicolumn{1}{c}{\textbf{Zeitraum}} & \textbf{Sammler} \\',
        r'\midrule',
        r'\endfirsthead',
        r'\toprule',
        r'\textbf{Ort} & \multicolumn{1}{c}{\textbf{Zeitraum}} & \textbf{Sammler} \\',
        r'\midrule',
        r'\endhead',
    ]
    lines.extend(rows)
    lines.extend([
        r'\bottomrule',
        r'\end{longtable}',
        r'}',
    ])
    return '\n'.join(lines)


def generate_artifact_entry(artifact, bilder_dir, map_dir):
    """Generate LaTeX for one artifact with minipage layout."""
    lines = []
    kn = artifact['katalognummer']
    artifact_name = escape_meta(artifact['name'])
    # Title with catalog number in gray, slightly smaller
    title = f'{{\\fontsize{{17pt}}{{21pt}}\\selectfont\\color{{metagray}}{kn}}} {artifact_name}'
    oid = artifact['object_id']
    fo = artifact.get('fundort', {})

    # Metadata
    meta_lines = []
    meta_lines.append(f"{escape_meta(artifact['gattung'])} -- {escape_meta(artifact['objekttyp'])}")
    if artifact.get('material'):
        meta_lines.append(escape_meta(artifact['material']))
    if artifact.get('groesse'):
        meta_lines.append(escape_meta(artifact['groesse']))
    if artifact.get('kulturkreis'):
        meta_lines.append(escape_meta(artifact['kulturkreis']))
    if artifact.get('datierung'):
        meta_lines.append(escape_meta(artifact['datierung']))
    if artifact.get('kuenstler'):
        meta_lines.append(escape_meta(artifact['kuenstler']))
    if artifact.get('erhaltung'):
        meta_lines.append(escape_meta(artifact['erhaltung']))
    fo_loc = fo.get('location_reference', '').strip() or fo.get('name', '').strip()
    if fo_loc:
        meta_lines.append(escape_meta(fo_loc))
    if artifact.get('katalog_fischer'):
        meta_lines.append(escape_meta(artifact['katalog_fischer']))

    # Images
    img_paths = []
    missing_imgs = []
    for img in artifact.get('images', []):
        found = find_image_file(img, bilder_dir)
        if found:
            img_paths.append(found)
        else:
            missing_imgs.append(img)

    # Build entry - each artifact starts on a new page
    lines.append('')
    lines.append(r'\newpage')
    lines.append(r'\FloatBarrier')
    lines.append('')
    lines.append('%' + '-' * 60)
    lines.append(f'% Katalog-Nr. {kn}: {artifact["name"][:60]}')
    lines.append('%' + '-' * 60)
    lines.append('')

    # Title (full width) — catalog number in gray
    lines.append(f'\\artifacttitle{{{title}}}')
    lines.append('')
    lines.append(r'\vspace{4pt}')

    # Missing image notices
    for img in missing_imgs:
        esc = img.replace('_', r'\_').replace('&', r'\&').replace('%', r'\%').replace('#', r'\#')
        lines.append('')
        lines.append(r'\begin{center}')
        lines.append(
            r'{\fontsize{9pt}{11pt}\selectfont\color{metagray}'
            r'\fbox{\parbox{0.45\textwidth}{\centering Bild nicht verfügbar:\\ \texttt{'
            + esc + r'}}}}'
        )
        lines.append(r'\end{center}')
        lines.append('')

    # --- Two-column layout using paracol (breaks across pages) ---
    # Left column: text content (can span multiple pages)
    # Right column: images (at top, then whitespace)

    # Build left column content
    left_content = []
    left_content.append(r'\metablock{')
    left_content.append(r' \\ '.join(meta_lines))
    left_content.append('}')

    # Beschreibung Extern (quoted box)
    if artifact.get('beschreibung_extern'):
        left_content.append('')
        left_content.append(r'\begin{quotebox}')
        formatted = format_body_text(artifact['beschreibung_extern'])
        left_content.append(latex_escape(formatted))
        if artifact.get('annotationen'):
            left_content.append('')
            left_content.append(r'\medskip')
            left_content.append(r'{\footnotesize\bfseries Annotationen:} ' + escape_meta(artifact['annotationen']))
        left_content.append(r'\end{quotebox}')
        left_content.append('')

    # Beschreibung MIE
    if artifact.get('beschreibung_mie'):
        formatted = format_body_text(artifact['beschreibung_mie'])
        left_content.append(latex_escape(formatted))
        left_content.append('')

    # Referenzen
    if artifact.get('referenz_literatur'):
        left_content.append(f'\\referencetext{{{escape_meta(artifact["referenz_literatur"])}}}')
    if artifact.get('vergleiche'):
        left_content.append(f'\\referencetext{{Vergleiche: {escape_meta(artifact["vergleiche"])}}}')
    if artifact.get('auktionen'):
        left_content.append(f'\\referencetext{{Auktionen: {escape_meta(artifact["auktionen"])}}}')

    left_str = '\n'.join(left_content)

    # Build right column (images)
    right_content = []
    right_content.append(r'\vspace{0pt}')
    if img_paths:
        for i, ip in enumerate(img_paths):
            right_content.append(f'\\includegraphics[width=\\linewidth,keepaspectratio]{{../bilder/{os.path.basename(ip)}}}')
            if i < len(img_paths) - 1:
                right_content.append(r'\vspace{8pt}')
    else:
        right_content.append(r'\vspace{0pt}')  # empty placeholder

    right_str = '\n'.join(right_content)

    # Assemble with paracol (column ratio ~55:45)
    lines.append(r'\columnratio{0.55}')
    lines.append(r'\begin{paracol}{2}')
    lines.append(left_str)
    lines.append('')
    lines.append(r'\switchcolumn')
    lines.append(right_str)
    lines.append(r'\end{paracol}')
    lines.append('')

    # --- Standortkarte (always on new page, with title) ---
    map_path = os.path.join(map_dir, f'map_{oid}.png')
    if os.path.isfile(map_path):
        lines.append('')
        lines.append(r'\newpage')
        lines.append(r'\FloatBarrier')
        lines.append('')
        lines.append(r'{\fontsize{11pt}{14pt}\selectfont\bfseries Standortkarte}')
        lines.append(r'\vspace{6pt}')
        lines.append('')
        lines.append(r'\begin{center}')
        lines.append(f'  \\includegraphics[width=0.92\\textwidth,keepaspectratio]{{./maps/{os.path.basename(map_path)}}}')
        lines.append(r'\end{center}')
        lines.append('')
        tbl = format_location_table(artifact)
        if tbl:
            lines.append(tbl)
            lines.append('')

    lines.append(r'\artifactsep')
    lines.append('')
    return '\n'.join(lines)


def generate_toc_section(data):
    """Generate TOC by Gattung / Objekttyp — clean layout with one artifact per row."""
    toc = data.get('toc', {})
    if not toc:
        return ''

    lines = []
    lines.append('')
    lines.append(r'\begingroup')
    lines.append(r'\setlength{\parindent}{0pt}')
    lines.append(r'\begin{center}')
    lines.append(r'{\fontsize{22pt}{28pt}\selectfont\bfseries Inhaltsverzeichnis}')
    lines.append(r'\par\vspace{4pt}')
    lines.append(r'\rule{0.6\textwidth}{0.6pt}')
    lines.append(r'\end{center}')
    lines.append(r'\vspace{20pt}')

    for gattung, objektypen in toc.items():
        for objekttyp, artifacts in objektypen.items():
            lines.append('')
            lines.append(r'\vspace{8pt}')
            lines.append(
                f'{{\\fontsize{{12pt}}{{16pt}}\\selectfont\\itshape '
                f'{escape_meta(gattung)}\\par}}'
            )
            lines.append(r'\vspace{8pt}')

            for a in artifacts:
                kn = a['katalognummer']
                nm = escape_meta(a['name'])
                lbl = f"art:{kn.replace('.', '-')}"

                # Clean one-row layout: indent, number, name, dots, page.
                # Wrap in \par at the end so each entry forms its own line.
                entry = (
                    r'\noindent{\fontsize{11pt}{14pt}\selectfont'
                    r'\hspace*{1.5em}'
                    f'{kn}\\quad {nm}'
                    r'\dotfill\ '
                    f'\\pageref{{{lbl}}}'
                    r'\par}'
                )
                lines.append(entry)
                lines.append(r'\vspace{4pt}')

            lines.append(r'\vspace{2pt}')

    lines.append(r'\vspace{16pt}')
    lines.append(r'\endgroup')
    lines.append(r'\newpage')
    return '\n'.join(lines)


def generate_latex(data_path, output_path, bilder_dir, map_dir):
    """Generate complete LaTeX document."""
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    artifacts = data.get('artifacts', [])
    print(f'[latex_generator] {len(artifacts)} artifacts')

    doc = []
    doc.append(r'\input{catalog_styling.tex}')
    doc.append('')
    # Determine Gattung for title + running header
    gs = escape_meta(artifacts[0]['gattung'] if artifacts else '')

    # Override running header with actual Gattung value
    doc.append('\\fancyhead[R]{\\small\\textit{' + gs + '}}')
    doc.append('')

    doc.append(r'\begin{document}')
    doc.append('')

    # Title page
    doc.append(r'\thispagestyle{empty}')
    doc.append(r'\begin{center}')
    doc.append(r'\vspace*{\fill}')
    doc.append(r'{\fontsize{36pt}{44pt}\selectfont\bfseries Katalog}')
    doc.append(r'\par\vspace{12pt}')
    doc.append(r'\rule{0.5\textwidth}{0.8pt}')
    doc.append(r'\vspace*{\fill}')
    doc.append(r'\end{center}')
    doc.append(r'\newpage')
    doc.append('')

    # TOC
    doc.append(r'\pagestyle{empty}')
    doc.append(r'\setcounter{page}{0}')
    doc.append(generate_toc_section(data))
    doc.append('')

    # Catalog
    doc.append(r'\pagestyle{fancy}')
    doc.append(r'\setcounter{page}{1}')
    doc.append('')

    for art in artifacts:
        entry = generate_artifact_entry(art, bilder_dir, map_dir)
        doc.append(entry)
        lbl = art['katalognummer'].replace('.', '-')
        doc.append(f'\\label{{art:{lbl}}}')
        doc.append('')

    doc.append(r'\end{document}')

    content = '\n'.join(doc)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'[latex_generator] Written: {output_path} ({len(content)} chars)')


if __name__ == '__main__':
    dp = sys.argv[1] if len(sys.argv) > 1 else '/opt/hermes/work/artifacts_data.json'
    op = sys.argv[2] if len(sys.argv) > 2 else '/opt/hermes/work/latex_temp/catalog.tex'
    bd = sys.argv[3] if len(sys.argv) > 3 else '/opt/hermes/work/bilder'
    md = sys.argv[4] if len(sys.argv) > 4 else '/opt/hermes/work/latex_temp/maps'
    generate_latex(dp, op, bd, md)
