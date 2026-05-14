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
    """Generate longtable of chronological location history."""
    locations = artifact.get('all_locations', [])
    if not locations:
        return ''

    rows = []
    for loc in locations:
        if loc.get('is_fundort'):
            typ = r'{[Fundort]}'
        else:
            typ = r'{[in collection]}'

        label = escape_meta(loc.get('label', ''))
        ds = escape_meta(loc.get('date_start', ''))
        de = escape_meta(loc.get('date_end', ''))

        if ds and de:
            date_str = f'{ds} \u2013 {de}'
        elif ds:
            date_str = f'{ds} \u2013'
        elif de:
            date_str = f'\u2013 {de}'
        else:
            date_str = 'unbekannt'

        sammler = escape_meta(loc.get('sammler', ''))

        row = f'{typ} & {label} & {date_str}'
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
        r'\begin{longtable}{p{2.5cm} p{3.5cm} p{4.5cm} p{3cm}}',
        r'\toprule',
        r'\textbf{Typ} & \textbf{Ort} & \textbf{Zeitraum} & \textbf{Sammler} \\',
        r'\midrule',
        r'\endfirsthead',
        r'\toprule',
        r'\textbf{Typ} & \textbf{Ort} & \textbf{Zeitraum} & \textbf{Sammler} \\',
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
    """Generate LaTeX for one artifact."""
    lines = []
    kn = artifact['katalognummer']
    name = escape_meta(artifact['name'])
    oid = artifact['object_id']
    fo = artifact.get('fundort', {})

    # Metadata
    meta_lines = []
    meta_lines.append(f"{escape_meta(artifact['gattung'])} -- {escape_meta(artifact['objekttyp'])}")
    if artifact.get('material'):
        meta_lines.append(f"Material: {escape_meta(artifact['material'])}")
    if artifact.get('groesse'):
        meta_lines.append(f"Gr\u00f6sse: {escape_meta(artifact['groesse'])}")
    if artifact.get('kulturkreis'):
        meta_lines.append(f"Kulturkreis: {escape_meta(artifact['kulturkreis'])}")
    if artifact.get('datierung'):
        meta_lines.append(f"Datierung: {escape_meta(artifact['datierung'])}")
    if artifact.get('kuenstler'):
        meta_lines.append(f"K\u00fcnstler: {escape_meta(artifact['kuenstler'])}")
    if artifact.get('erhaltung'):
        meta_lines.append(f"Erhaltung: {escape_meta(artifact['erhaltung'])}")
    fo_loc = fo.get('location_reference', '').strip() or fo.get('name', '').strip()
    if fo_loc:
        meta_lines.append(f"{{[Fundort]}} {escape_meta(fo_loc)}")
    if artifact.get('katalog_fischer'):
        meta_lines.append(f"Katalog Fischer: {escape_meta(artifact['katalog_fischer'])}")

    # Images
    img_paths = []
    missing_imgs = []
    for img in artifact.get('images', []):
        found = find_image_file(img, bilder_dir)
        if found:
            img_paths.append(found)
        else:
            missing_imgs.append(img)

    # Build entry
    lines.append('')
    lines.append('%' + '-' * 60)
    lines.append(f'% Katalog-Nr. {kn}: {artifact["name"][:60]}')
    lines.append('%' + '-' * 60)
    lines.append('')

    lines.append(f'\\artifacttitle{{{name}}}')
    lines.append(f'\\catnum{{{kn}}}')
    lines.append('')

    lines.append('\\metablock{')
    lines.append(r' \\ '.join(meta_lines))
    lines.append('}')

    # Wrapfigure for images
    if img_paths:
        lines.append('')
        lines.append(r'\begin{wrapfigure}{r}{0.48\textwidth}')
        lines.append(r'  \vspace{-14pt}')
        for i, ip in enumerate(img_paths):
            lines.append(f'  \\includegraphics[width=\\linewidth,keepaspectratio]{{{ip}}}')
            if i < len(img_paths) - 1:
                lines.append(r'  \vspace{6pt}')
        lines.append(r'\end{wrapfigure}')
        lines.append('')

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

    # Beschreibung Extern (quoted box)
    if artifact.get('beschreibung_extern'):
        lines.append('')
        lines.append(r'\begin{quotebox}')
        formatted = format_body_text(artifact['beschreibung_extern'])
        lines.append(latex_escape(formatted))
        if artifact.get('annotationen'):
            lines.append('')
            lines.append(r'\medskip')
            lines.append(r'{\footnotesize\bfseries Annotationen:} ' + escape_meta(artifact['annotationen']))
        lines.append(r'\end{quotebox}')
        lines.append('')

    # Beschreibung MIE
    if artifact.get('beschreibung_mie'):
        formatted = format_body_text(artifact['beschreibung_mie'])
        lines.append(latex_escape(formatted))
        lines.append('')

    # Referenzen
    if artifact.get('referenz_literatur'):
        lines.append(f'\\referencetext{{{escape_meta(artifact["referenz_literatur"])}}}')
        lines.append('')
    if artifact.get('vergleiche'):
        lines.append(f'\\referencetext{{Vergleiche: {escape_meta(artifact["vergleiche"])}}}')
        lines.append('')
    if artifact.get('auktionen'):
        lines.append(f'\\referencetext{{Auktionen: {escape_meta(artifact["auktionen"])}}}')
        lines.append('')

    # Standortkarte
    map_path = os.path.join(map_dir, f'map_{oid}.png')
    if os.path.isfile(map_path):
        lines.append('')
        lines.append(r'\vspace{8pt}')
        lines.append(r'{\fontsize{11pt}{14pt}\selectfont\bfseries Standortkarte}')
        lines.append('')
        lines.append(r'\begin{center}')
        lines.append(f'  \\includegraphics[width=0.92\\textwidth,keepaspectratio]{{{map_path}}}')
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
    """Generate TOC by Gattung / Objekttyp."""
    toc = data.get('toc', {})
    if not toc:
        return ''

    lines = []
    lines.append('')
    lines.append(r'\begin{center}')
    lines.append(r'{\fontsize{18pt}{22pt}\selectfont\bfseries Inhaltsverzeichnis}')
    lines.append(r'\end{center}')
    lines.append(r'\vspace{16pt}')

    for gattung, objektypen in toc.items():
        lines.append('')
        lines.append(f'{{\\fontsize{{14pt}}{{18pt}}\\selectfont\\bfseries {escape_meta(gattung)}}}')
        lines.append(r'\vspace{6pt}')
        for objekttyp, artifacts in objektypen.items():
            lines.append(f'{{\\fontsize{{11pt}}{{14pt}}\\selectfont\\textit{{{escape_meta(objekttyp)}}}}}')
            lines.append(r'\vspace{4pt}')
            for a in artifacts:
                kn = a['katalognummer']
                nm = escape_meta(a['name'])
                lbl = f"art:{kn.replace('.', '-')}"
                lines.append(
                    f'\\noindent\\hspace*{{1.5em}}{{\\fontsize{{10pt}}{{13pt}}\\selectfont'
                    f' {kn}\\quad {nm} \\dotfill\\ \\pageref{{{lbl}}}}}'
                )
                lines.append(r'\vspace{2pt}')
            lines.append(r'\vspace{4pt}')

    lines.append('')
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
    doc.append(r'\begin{document}')
    doc.append('')

    # Title page
    doc.append(r'\thispagestyle{empty}')
    doc.append(r'\begin{center}')
    doc.append(r'\vspace*{4cm}')
    doc.append(r'{\fontsize{28pt}{34pt}\selectfont\bfseries Katalog der Artefakte}')
    doc.append(r'\vspace{1cm}')
    doc.append(r'{\fontsize{14pt}{18pt}\selectfont Arch\"aologische Sammlung}')
    doc.append(r'\vspace{0.5cm}')
    gs = escape_meta(artifacts[0]['gattung'] if artifacts else '')
    doc.append(f'{{\\fontsize{{12pt}}{{16pt}}\\selectfont\\color{{metagray}}Stand: {gs}}}')
    doc.append(r'\vspace{3cm}')
    doc.append(r'{\fontsize{11pt}{14pt}\selectfont\color{metagray}Erstellt am \today}')
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
