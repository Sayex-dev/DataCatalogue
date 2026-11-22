#!/usr/bin/env python3
"""
LaTeX Generator - Produces .tex file from structured artifact data.
"""

import json
import os
import re
import sys

# Characters that pdflatex cannot typeset with the current font setup.
# Values are LaTeX replacements; None means "keep as is".
UNICODE_REPLACEMENTS = {
    '\u221e': r'\(\infty\)',      # ∞
    '\u2013': '--',               # –
    '\u2014': '---',              # —
    '\u201e': '"',                # „
    '\u201c': '"',                # "
    '\u201d': '"',                # "
    '\u2019': "'",                # ’
    '\u2026': '...',              # …
    '\u0161': r'\v{s}',           # š
    '\u00d7': r'\(\times\)',      # ×
    '\u00b7': r'\textperiodcentered{}',  # ·
    '\u2032': r"$'$",             # ′
    '\u2033': r"$''$",            # ″
    '\u2264': r'\(\leq\)',        # ≤
    '\u2265': r'\(\geq\)',        # ≥
    '\u00a0': '~',                # non-breaking space
}

# Characters the T1/tgtermes font set can render directly.
SAFE_UNICODE = set('äöüÄÖÜßéèàâêîôûçñáíóú')

# Filled while generating; reported at the end of the run.
UNKNOWN_UNICODE = {}


def sanitize_unicode(text):
    """Replace characters pdflatex cannot handle and track unknown ones."""
    if not text:
        return ''
    out = []
    for ch in text:
        if ord(ch) < 128 or ch in SAFE_UNICODE:
            out.append(ch)
        elif ch in UNICODE_REPLACEMENTS:
            out.append(UNICODE_REPLACEMENTS[ch])
        else:
            UNKNOWN_UNICODE[ch] = UNKNOWN_UNICODE.get(ch, 0) + 1
            out.append(ch)
    return ''.join(out)


def latex_escape(text):
    """Escape text for LaTeX body text. Unicode is normalized afterwards."""
    if not text:
        return ''

    escape_map = {
        '&': r'\&', '%': r'\%', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\^{}',
    }
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text) and text[i + 1].isalpha():
            # Keep existing LaTeX commands intact
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

    return sanitize_unicode(''.join(result))


def escape_meta(text):
    """Escape text for metadata fields. Newlines become line breaks."""
    if not text:
        return ''

    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = r' \\ '.join(lines)

    escape_map = {
        '&': r'\&', '%': r'\%', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\^{}',
    }
    for char, repl in escape_map.items():
        text = text.replace(char, repl)

    return sanitize_unicode(text)


def format_body_text(text):
    """Blank lines become new paragraphs, single newlines become spaces."""
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
    if not img_name:
        return None
    exact = os.path.join(bilder_dir, img_name)
    if os.path.isfile(exact):
        return exact

    # Try matching by base name (strip extensions iteratively)
    base = img_name
    while True:
        base, ext = os.path.splitext(base)
        if not ext:
            break
        for fname in sorted(os.listdir(bilder_dir)):
            if fname.startswith(base) and os.path.isfile(
                    os.path.join(bilder_dir, fname)):
                return os.path.join(bilder_dir, fname)

    return None


def split_references(value):
    """Split ';'-separated image references into a list."""
    if not value:
        return []
    return [part.strip() for part in value.split(';') if part.strip()]


def fmt_date(date_str):
    """Convert a database date to DD.MM.YYYY, resolving ±∞."""
    if not date_str:
        return ''
    s = date_str.strip()
    if s in ('\u221e', '+\u221e'):
        return 'heute'
    if s == '-\u221e':
        return 'unbekannt'
    # Remove trailing .0 on year-only floats (e.g. "1800.0")
    if s.endswith('.0') and s[:-2].replace('.', '', 1).isdigit():
        return s[:-2]
    # YYYY-MM-DD → DD.MM.YYYY
    parts = s.split('-')
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f'{parts[2]}.{parts[1]}.{parts[0]}'
    # YYYY-MM → MM.YYYY
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        return f'{parts[1]}.{parts[0]}'
    return s


def format_entry_fields(artifact):
    """Steckbrief fields in the order requested by the editorship."""
    def clean(value):
        return escape_meta(value) if value else ''

    rows = [
        ('Standort', clean(artifact.get('aktueller_standort'))),
        ('Eigentümer', clean(artifact.get('eigentuemer'))),
        ('Status', clean(artifact.get('status'))),
        ('Material', clean(artifact.get('material'))),
        ('Grösse', clean(artifact.get('groesse'))),
        ('Datierung', clean(artifact.get('datierung'))),
        ('Kulturkreis', clean(artifact.get('kulturkreis'))),
        ('Angaben Fundort', clean(artifact.get('weitere_info_fundort'))),
        ('Künstler', clean(artifact.get('kuenstler'))),
        ('Erhaltung', clean(artifact.get('erhaltung'))),
        ('Dekor', clean(artifact.get('dekor'))),
        ('ID Auktion', clean(artifact.get('katalog_fischer'))),
        ('ID UZH', clean(artifact.get('inv_nr_uzh'))),
        ('Platzierung im Haus', clean(artifact.get('platzierung_haus'))),
    ]
    return [f'\\textbf{{{label}:}} {value}' for label, value in rows if value]


def format_location_table(artifact):
    """Generate longtable of chronological location history."""
    locations = artifact.get('all_locations', [])
    if not locations:
        return ''

    rows_data = []
    has_ort = False
    for loc in locations:
        # For the Fundort the label already is the place name.
        ort = '' if loc.get('is_fundort') else escape_meta(loc.get('ort', ''))
        if ort:
            has_ort = True
        rows_data.append({
            'label': escape_meta(loc.get('label', '')),
            'ort': ort,
            'start': fmt_date(loc.get('date_start', '')),
            'end': fmt_date(loc.get('date_end', '')),
            'sammler': escape_meta(loc.get('sammler', '')),
            'is_fundort': bool(loc.get('is_fundort')),
        })

    if not rows_data:
        return ''

    rows = []
    for item in rows_data:
        if not item['start'] and not item['end']:
            date_cells = r'\multicolumn{2}{@{}l}{unbekannt}'
        else:
            date_cells = f"{item['start']} & {item['end']}"
        sammler = item['sammler'] if (item['sammler'] and not item['is_fundort']) else ''

        row = f"{item['label']} & {date_cells}"
        if has_ort:
            row += ' & ' + (item['ort'] or '')
        row += ' & ' + (sammler or '')
        row += r' \\'
        rows.append(row)

    # Column widths add up to <= 16cm (A4 minus 2 x 2.5cm margins).
    if has_ort:
        spec = (r'@{}>{\raggedright\arraybackslash}p{4.4cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.2cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.2cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.4cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{3.0cm}@{}')
        header = (r'\textbf{Sammlung} & \multicolumn{2}{c}{\textbf{Zeitraum}} '
                  r'& \textbf{Ort} & \textbf{Sammler} \\')
    else:
        spec = (r'@{}>{\raggedright\arraybackslash}p{5.4cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.6cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.6cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{4.0cm}@{}')
        header = (r'\textbf{Sammlung} & \multicolumn{2}{c}{\textbf{Zeitraum}} '
                  r'& \textbf{Sammler} \\')

    lines = [
        r'\vspace{8pt}',
        r'{\fontsize{9pt}{11pt}\selectfont\color{metagray}',
        r'\textbf{Standortverlauf (chronologisch)}\\',
        r'\vspace{2pt}',
        r'\begin{longtable}{' + spec + '}',
        r'\toprule',
        header,
        r'\midrule',
        r'\endfirsthead',
        r'\toprule',
        header,
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


def image_entries(artifact, bilder_dir):
    """
    One entry per image declared in the export, in export order.

    Returns dicts with index, declared name, found path (or None), caption
    and source. Keeping a single list keeps figure numbers, captions and the
    Abbildungsverzeichnis in sync even when a file is missing.
    """
    captions = split_references(artifact.get('bildreferenz'))
    sources = split_references(artifact.get('bildquelle'))

    entries = []
    for index, name in enumerate(artifact.get('images', [])):
        entries.append({
            'index': index,
            'name': name,
            'path': find_image_file(name, bilder_dir),
            'caption': captions[index] if index < len(captions) else '',
            'source': sources[index] if index < len(sources) else '',
        })
    return entries


def format_image_block(artifact, bilder_dir):
    """Figures with their caption directly below the image."""
    lines = []
    label_base = artifact['katalognummer'].replace('.', '-')

    for entry in image_entries(artifact, bilder_dir):
        number = entry['index'] + 1
        lines.append(r'\begin{samepage}')
        lines.append(r'\begin{center}')

        if entry['path']:
            lines.append(
                r'\includegraphics[width=\linewidth,height=0.32\textheight,'
                f'keepaspectratio]{{../bilder/{os.path.basename(entry["path"])}}}'
            )
        else:
            esc = (entry['name'].replace('_', r'\_').replace('&', r'\&')
                   .replace('%', r'\%').replace('#', r'\#'))
            lines.append(
                r'{\fontsize{9pt}{11pt}\selectfont\color{metagray}'
                r'\fbox{\parbox{\dimexpr\linewidth-2\fboxsep-2\fboxrule\relax}'
                r'{\centering Bild nicht verfügbar:\\ '
                r'\texttt{' + esc + r'}}}\par}'
            )

        if entry['caption']:
            lines.append(r'\par\vspace{4pt}')
            lines.append(
                r'{\footnotesize\itshape '
                + escape_meta(f'Abb. {number}: {entry["caption"]}') + r'\par}'
            )
        if entry['source']:
            lines.append(
                r'{\fontsize{8pt}{10pt}\selectfont\color{metagray}'
                + escape_meta(f'Quelle: {entry["source"]}') + r'\par}'
            )

        lines.append(f'\\label{{art:{label_base}-img{number}}}')
        lines.append(r'\end{center}')
        lines.append(r'\end{samepage}')
        lines.append(r'\vspace{10pt}')

    return '\n'.join(lines)


def generate_artifact_entry(artifact, bilder_dir):
    """Generate LaTeX for one artifact with minipage layout."""
    lines = []
    kn = artifact['katalognummer']
    artifact_name = escape_meta(artifact['name'])
    title = (f'{{\\fontsize{{17pt}}{{21pt}}\\selectfont\\color{{metagray}}'
             f'{kn}}} {artifact_name}')

    lines.append('')
    lines.append(r'\newpage')
    lines.append(r'\FloatBarrier')
    lines.append('')
    lines.append('%' + '-' * 60)
    lines.append(f'% Katalog-Nr. {kn}: {artifact["name"][:60]}')
    lines.append('%' + '-' * 60)
    lines.append('')

    lines.append(f'\\artifacttitle{{{title}}}')
    lines.append('')
    lines.append(r'\vspace{4pt}')

    # Left column: metadata + descriptions
    left_content = []
    fields = format_entry_fields(artifact)
    if fields:
        left_content.append(r'\metablock{')
        left_content.append(r' \\ '.join(fields))
        left_content.append('}')

    # Description box: catalogue text, with the external description as
    # fallback when the export only carries one of the two texts.
    box_text = (artifact.get('beschreibung_fischer')
                or artifact.get('beschreibung_extern'))
    if box_text:
        left_content.append('')
        left_content.append(r'\begin{quotebox}')
        left_content.append(latex_escape(format_body_text(box_text)))
        if artifact.get('annotationen'):
            left_content.append('')
            left_content.append(r'\medskip')
            left_content.append(
                r'{\footnotesize\bfseries Anmerkungen:} '
                + escape_meta(artifact['annotationen'])
            )
        left_content.append(r'\end{quotebox}')
        left_content.append('')

    if artifact.get('beschreibung_mie'):
        left_content.append(
            latex_escape(format_body_text(artifact['beschreibung_mie']))
        )
        left_content.append('')

    if artifact.get('provenienz'):
        left_content.append(
            f'\\referencetext{{Provenienz: {escape_meta(artifact["provenienz"])}}}'
        )
    if artifact.get('referenz_literatur'):
        left_content.append(
            f'\\referencetext{{{escape_meta(artifact["referenz_literatur"])}}}'
        )
    if artifact.get('vergleiche'):
        left_content.append(
            f'\\referencetext{{Vergleiche: '
            f'{escape_meta(artifact["vergleiche"])}}}'
        )
    if artifact.get('auktionen'):
        left_content.append(
            f'\\referencetext{{Auktionen: {escape_meta(artifact["auktionen"])}}}'
        )

    right_str = format_image_block(artifact, bilder_dir)

    lines.append(r'\columnratio{0.55}')
    lines.append(r'\begin{paracol}{2}')
    lines.append('\n'.join(left_content))
    lines.append('')
    lines.append(r'\switchcolumn')
    lines.append(r'\vspace{0pt}')
    lines.append(right_str)
    lines.append(r'\end{paracol}')
    lines.append('')

    # Chronological location history (table only, no map)
    table = format_location_table(artifact)
    if table:
        lines.append(table)
        lines.append('')

    lines.append(r'\artifactsep')
    lines.append('')
    return '\n'.join(lines)


def generate_figure_index(data, bilder_dir):
    """Abbildungsverzeichnis: artifact, then one line per figure."""
    entries = []
    for artifact in data.get('artifacts', []):
        images = image_entries(artifact, bilder_dir)
        if images:
            entries.append((artifact, images))

    if not entries:
        return ''

    lines = [
        '',
        r'\begingroup',
        r'\setlength{\parindent}{0pt}',
        r'\begin{center}',
        r'{\fontsize{22pt}{28pt}\selectfont\bfseries Abbildungsverzeichnis}',
        r'\par\vspace{4pt}',
        r'\rule{0.6\textwidth}{0.6pt}',
        r'\end{center}',
        r'\vspace{20pt}',
    ]
    for artifact, images in entries:
        kn = artifact['katalognummer']
        label = kn.replace('.', '-')
        lines.append('')
        lines.append(r'\vspace{8pt}')
        lines.append(
            r'{\fontsize{11pt}{14pt}\selectfont\bfseries '
            f'{kn}\\quad {escape_meta(artifact["name"])}\\par}}'
        )
        lines.append(r'\vspace{3pt}')
        for entry in images:
            number = entry['index'] + 1
            text = entry['source'] or entry['caption']
            lines.append(
                r'\noindent\hspace*{1.5em}{\fontsize{10pt}{13pt}'
                r'\selectfont '
                + escape_meta(f'Abb. {number}')
                + (r': ' + escape_meta(text) if text else '')
                + r'\dotfill\ '
                + f'\\pageref{{art:{label}-img{number}}}'
                + r'\par}'
            )
            lines.append(r'\vspace{2pt}')
    lines.append(r'\vspace{16pt}')
    lines.append(r'\endgroup')
    lines.append(r'\newpage')
    return '\n'.join(lines)


def generate_toc_section(data):
    """Generate TOC by Gattung — one artifact per row."""
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
        heading = escape_meta(gattung) or 'Ohne Gattung'
        lines.append('')
        lines.append(r'\vspace{8pt}')
        lines.append(
            f'{{\\fontsize{{12pt}}{{16pt}}\\selectfont\\itshape '
            f'{heading}\\par}}'
        )
        lines.append(r'\vspace{8pt}')
        for artifacts in objektypen.values():
            for a in artifacts:
                kn = a['katalognummer']
                nm = escape_meta(a['name'])
                lbl = f"art:{kn.replace('.', '-')}"
                lines.append(
                    r'\noindent{\fontsize{11pt}{14pt}\selectfont'
                    r'\hspace*{1.5em}'
                    f'{kn}\\quad {nm}'
                    r'\dotfill\ '
                    f'\\pageref{{{lbl}}}'
                    r'\par}'
                )
                lines.append(r'\vspace{4pt}')
        lines.append(r'\vspace{2pt}')

    lines.append(r'\vspace{16pt}')
    lines.append(r'\endgroup')
    lines.append(r'\newpage')
    return '\n'.join(lines)


def generate_latex(data_path, output_path, bilder_dir):
    """Generate complete LaTeX document."""
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    artifacts = data.get('artifacts', [])
    print(f'[latex_generator] {len(artifacts)} artifacts')

    # One \rhead per Gattung group: the first artifact of each group sets it.
    doc = [r'\input{catalog_styling.tex}', '', r'\begin{document}', '']

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

    # Figure index
    figure_index = generate_figure_index(data, bilder_dir)
    if figure_index:
        doc.append(figure_index)
        doc.append('')

    # Catalog
    doc.append(r'\pagestyle{fancy}')
    doc.append(r'\setcounter{page}{1}')
    doc.append('')

    current_gattung = None
    for art in artifacts:
        gattung = art.get('gattung', '')
        if gattung != current_gattung:
            current_gattung = gattung
            header = escape_meta(gattung) or 'Ohne Gattung'
            doc.append(
                r'\fancyhead[R]{\small\textit{' + header + '}}'
            )
            doc.append('')
        doc.append(generate_artifact_entry(art, bilder_dir))
        label = art['katalognummer'].replace('.', '-')
        doc.append(f'\\label{{art:{label}}}')
        doc.append('')

    doc.append(r'\end{document}')

    content = '\n'.join(doc)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'[latex_generator] Written: {output_path} ({len(content)} chars)')

    if UNKNOWN_UNICODE:
        print('[latex_generator] WARNING: characters without LaTeX mapping:')
        for ch, count in sorted(UNKNOWN_UNICODE.items()):
            print(f'[latex_generator]   U+{ord(ch):04X} {ch!r} x{count}')
    return UNKNOWN_UNICODE


if __name__ == '__main__':
    dp = sys.argv[1] if len(sys.argv) > 1 else 'artifacts_data.json'
    op = sys.argv[2] if len(sys.argv) > 2 else 'latex_temp/catalog.tex'
    bd = sys.argv[3] if len(sys.argv) > 3 else 'bilder'
    generate_latex(dp, op, bd)
