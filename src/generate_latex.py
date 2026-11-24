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


# Trailing source marker in "Beschreibung extern" -> label of the description
# box. The marker is removed from the text and replaced by the label.
EXTERN_SOURCE_LABELS = {
    'mp': 'Beschreibung MuseumPlus UZH',
    'BM': 'Beschreibung British Museum',
    'Bonhams': 'Beschreibung Bonhams',
    "Christie's": 'Beschreibung Christie\'s',
    'Koller': 'Beschreibung Koller',
    "Sotheby's": 'Beschreibung Sotheby\'s',
}

EXTERN_MARKER_RE = re.compile(r'\s*\(([^()]{1,20})\)\s*$')


def description_box(artifact):
    """
    Text and label for the highlighted description box.

    The catalogue text from Fischer is preferred. When it is missing, the
    external description is used and its trailing source marker (mp, BM,
    Bonhams, ...) becomes the label.
    """
    fischer = (artifact.get('beschreibung_fischer') or '').strip()
    if fischer:
        return fischer, 'Beschreibung Katalog Galerie Fischer 1936'

    extern = (artifact.get('beschreibung_extern') or '').strip()
    if not extern:
        return '', ''

    match = EXTERN_MARKER_RE.search(extern)
    if match and match.group(1) in EXTERN_SOURCE_LABELS:
        return (extern[:match.start()].rstrip(),
                EXTERN_SOURCE_LABELS[match.group(1)])

    return extern, 'Beschreibung extern'


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
    """
    All metadata and reference fields as one block.

    Labels follow the CSV column names so the catalogue and the export stay
    consistent. Fields without data are omitted.
    """
    def clean(value):
        return escape_meta(value) if value else ''

    rows = [
        # Steckbrief
        ('Standort', clean(artifact.get('aktueller_standort'))),
        ('Eigentümer', clean(artifact.get('eigentuemer'))),
        ('Status', clean(artifact.get('status'))),
        ('Material', clean(artifact.get('material'))),
        ('Grösse', clean(artifact.get('groesse'))),
        ('Datierung', clean(artifact.get('datierung'))),
        ('Kulturkreis', clean(artifact.get('kulturkreis'))),
        ('Infos Fundort', clean(artifact.get('weitere_info_fundort'))),
        ('Künstler', clean(artifact.get('kuenstler'))),
        ('Erhaltung', clean(artifact.get('erhaltung'))),
        ('Auktion 1936, Lot-Nr.', clean(artifact.get('katalog_fischer'))),
        ('Inv. Nr. UZH', clean(artifact.get('inv_nr_uzh'))),
        ('Platzierung im Haus', clean(artifact.get('platzierung_haus'))),
        # References
        ('Literatur', clean(artifact.get('referenz_literatur'))),
        ('In Kunsthandel', clean(artifact.get('auktionen'))),
        ('Vergleiche', clean(artifact.get('vergleiche'))),
        ('Provenienz', clean(artifact.get('provenienz'))),
    ]
    return [f'\\textbf{{{label}:}} {value}' for label, value in rows if value]


def format_location_table(artifact):
    """
    Chronological location history as a fixed-width tabular.

    A tabular (not longtable) keeps the whole table on one page, which lets
    the entry's height be measured; at most 7 rows this always fits.
    """
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
        spec = (r'@{}>{\raggedright\arraybackslash}p{3.9cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.0cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.0cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.6cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.9cm}@{}')
        header = (r'\textbf{Sammlung} & \textbf{Von} & \textbf{Bis} '
                  r'& \textbf{Ort} & \textbf{Sammler} \\')
    else:
        spec = (r'@{}>{\raggedright\arraybackslash}p{5.0cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.5cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{2.5cm}'
                r'@{\hspace{6pt}}>{\raggedright\arraybackslash}p{4.0cm}@{}')
        header = (r'\textbf{Sammlung} & \textbf{Von} & \textbf{Bis} '
                  r'& \textbf{Sammler} \\')

    lines = [
        r'\begin{samepage}',
        r'\vspace{6pt}',
        r'{\fontsize{10pt}{13pt}\selectfont\color{refgray}',
        r'\textsc{Standortverlauf (chronologisch)}\\',
        r'\vspace{3pt}',
        r'\rowcolors{2}{zebra}{white}',
        r'\begin{tabular}{' + spec + '}',
        r'\toprule',
        r'\rowcolor{white}',
        header,
        r'\midrule',
    ]
    lines.extend(rows)
    lines.extend([
        r'\bottomrule',
        r'\end{tabular}',
        r'}',
        r'\end{samepage}',
    ])
    return '\n'.join(lines)


def image_entries(artifact, bilder_dir):
    """
    One entry per image declared in Bildreferenz, in export order.

    Returns dicts with index, declared name, found path (or None), caption
    and Abbildungsnachweis.
    """
    captions = split_references(artifact.get('bildbeschreibung'))
    proofs = split_references(artifact.get('abbildungsnachweis'))

    entries = []
    for index, name in enumerate(artifact.get('images', [])):
        entries.append({
            'index': index,
            'name': name,
            'path': find_image_file(name, bilder_dir),
            'caption': captions[index] if index < len(captions) else '',
            'proof': proofs[index] if index < len(proofs) else '',
        })
    return entries


def placeholder_box(label):
    """Quiet dashed box shown when a figure file is missing."""
    esc = (label.replace('_', r'\_').replace('&', r'\&')
           .replace('%', r'\%').replace('#', r'\#'))
    content = r'\centering\color{refgray}Bild nicht verfügbar'
    if esc:
        # Long file names must be allowed to break at any character.
        content += (r'\\[2pt]{\fontsize{8pt}{10pt}\selectfont\ttfamily '
                    + r'\allowbreak{}'.join(esc) + '}')
    return (
        r'{\fontsize{10pt}{13pt}\selectfont'
        r'\setlength{\fboxrule}{0.4pt}\setlength{\fboxsep}{6pt}'
        r'\fcolorbox{quoteborder}{quotebg}{'
        r'\parbox{\dimexpr\linewidth-2\fboxsep-2\fboxrule\relax}{'
        + content + r'}}\par}'
    )


def format_image_block(artifact, bilder_dir):
    """Figures with their caption directly below the image."""
    lines = []
    entries = image_entries(artifact, bilder_dir)

    if not entries:
        # No Bildreferenz in the export: no image, no placeholder.
        return ''

    for entry in entries:
        number = entry['index'] + 1
        lines.append(r'\begin{samepage}')
        lines.append(r'\begin{center}')

        if entry['path']:
            lines.append(
                r'\includegraphics[width=\linewidth,height=0.32\textheight,'
                f'keepaspectratio]{{../bilder/{os.path.basename(entry["path"])}}}'
            )
        else:
            lines.append(placeholder_box(entry['name']))

        # \includegraphics does not end a paragraph, so without this the
        # caption and the Abbildungsnachweis would start beside the image.
        lines.append(r'\par')

        if entry['caption']:
            lines.append(r'\vspace{4pt}')
            lines.append(
                r'{\fontsize{11pt}{13.5pt}\selectfont\itshape '
                + escape_meta(f'Abb. {number}: {entry["caption"]}') + r'\par}'
            )
        if entry['proof']:
            lines.append(f'\\imageproof{{{escape_meta(entry["proof"])}}}')

        lines.append(r'\end{center}')
        lines.append(r'\end{samepage}')
        lines.append(r'\vspace{10pt}')

    return '\n'.join(lines)



def generate_artifact_entry(artifact, bilder_dir, chapter='',
                           first_in_chapter=False, last_in_chapter=False,
                           label=''):
    """
    Generate LaTeX for one artifact.

    The entry is measured first and only moved to the next page when it would
    otherwise be split; entries taller than a page are allowed to break.
    """
    kn = artifact['katalognummer']
    artifact_name = escape_meta(artifact['name'])
    obergattung = escape_meta(artifact.get('obergattung', ''))
    chapter_mark = escape_meta(chapter)

    # Body of the entry, kept as a unit so its height can be measured.
    body = []
    body.append(f'\\artifacttitle{{{kn}}}{{{artifact_name}}}')
    body.append(r'\vspace{6pt}')

    # Left column: metadata + descriptions
    left_content = [r'{\parskip=0pt\relax']
    fields = format_entry_fields(artifact)
    if fields:
        left_content.append(r'\metablock{')
        left_content.append(r' \\ '.join(fields))
        left_content.append('}')

    # Description box: catalogue text from Fischer, or the external
    # description with its source marker turned into the label.
    box_text, box_label = description_box(artifact)
    if box_text:
        left_content.append('')
        left_content.append(r'\begin{quotebox}')
        left_content.append(
            r'{\fontsize{9pt}{11.5pt}\selectfont\bfseries\color{accent}'
            + escape_meta(box_label) + r':\par}'
        )
        left_content.append(r'\vspace{4pt}')
        left_content.append(latex_escape(format_body_text(box_text)))
        left_content.append(r'\end{quotebox}')
        left_content.append('')

    if artifact.get('beschreibung_mie'):
        left_content.append(
            latex_escape(format_body_text(artifact['beschreibung_mie']))
        )
        left_content.append('')

    # Close the compact-spacing group opened at the top of the column.
    left_content.append(r'}')

    image_block = format_image_block(artifact, bilder_dir)
    if image_block:
        # Two columns: text left, figure right.
        body.extend([
            r'\noindent',
            r'\begin{minipage}[t]{0.55\textwidth}',
            '\n'.join(left_content),
            r'\end{minipage}',
            r'\hfill',
            r'\begin{minipage}[t]{0.42\textwidth}',
            r'\vspace{0pt}',
            image_block,
            r'\end{minipage}',
        ])
    else:
        # No figure: the text uses the full width instead of leaving the right
        # column empty (90% of the objects have no image).
        body.extend([
            r'\noindent',
            r'\begin{minipage}[t]{0.78\textwidth}',
            '\n'.join(left_content),
            r'\end{minipage}',
        ])

    table = format_location_table(artifact)
    if table:
        body.append('')
        body.append(table)

    lines = []
    lines.append('')
    lines.append(r'\FloatBarrier')
    lines.append('')
    lines.append('%' + '-' * 60)
    lines.append(f'% Katalog-Nr. {kn}: {artifact["name"][:60]}')
    lines.append('%' + '-' * 60)
    lines.append('')

    # The label goes inside the measured box: a \write is only executed when
    # the box is contributed to a page, so \pageref points at the page the
    # entry actually lands on, even when TeX moves it to the next page.
    if label:
        body.insert(0, f'\\label{{art:{label}}}')

    # Measure the entry and start a new page only when it would be split. The
    # first entry of a chapter always stays on its chapter page; entries taller
    # than a page are allowed to break.
    lines.append(r'\begingroup')
    lines.append(r'\setbox0=\vbox{%')
    lines.extend(body)
    lines.append(r'}')

    if not first_in_chapter:
        lines.append(r'\ifdim\ht0<\textheight')
        lines.append(
            r'  \ifdim\ht0>\dimexpr\pagegoal-\pagetotal+1pt\relax')
        lines.append(r'    \clearpage')
        lines.append(r'  \fi')
        lines.append(r'\fi')

    # The marks are set after the page break: emitted before it, they would
    # describe the page the entry was pushed away from.
    lines.append(r'\markboth{' + chapter_mark + '}{' + (obergattung or '') + '}')

    # The vertical gap belongs after the page break: emitted before it, it
    # would be the only content of the page it is pushed onto. The first entry
    # of a chapter already follows the chapter heading, so it needs no gap.
    if not first_in_chapter:
        lines.append(r'\vspace{16pt}')
    # parfillskip is non-zero here because of KOMA's parskip=half, which would
    # make the box paragraph 10.95pt too wide.
    lines.append(r'\vbox{\box0}\endgroup')
    lines.append('')

    # The separator is only emitted when there is still room for it on the
    # page. Otherwise it would be pushed alone onto the next page and leave a
    # nearly empty page behind. It is also omitted after the last entry of a
    # chapter, where the chapter's \newpage follows anyway.
    if not last_in_chapter:
        lines.append(r'\ifdim\dimexpr\pagegoal-\pagetotal\relax>40pt\relax')
        lines.append(r'  \artifactsep')
        lines.append(r'\fi')
        lines.append('')
    return '\n'.join(lines)



def generate_toc_section(data):
    """Generate TOC: chapter per Materialgattung, one row per artifact."""
    toc = data.get('toc', {})
    if not toc:
        return ''

    lines = []
    lines.append('')
    lines.append(r'\begingroup')
    lines.append(r'\setlength{\parindent}{0pt}')
    lines.append(r'\begin{center}')
    lines.append(r'{\fontsize{22pt}{28pt}\selectfont\bfseries '
                 r'\color{accent}Inhaltsverzeichnis}')
    lines.append(r'\par\vspace{4pt}')
    lines.append(r'{\color{accent}\rule{0.6\textwidth}{0.6pt}}')
    lines.append(r'\end{center}')
    lines.append(r'\vspace{18pt}')

    for chapter, artifacts in toc.items():
        heading = escape_meta(chapter)
        lines.append('')
        lines.append(r'\vspace{10pt}')
        lines.append(
            f'{{\\fontsize{{13pt}}{{16pt}}\\selectfont\\bfseries'
            f'\\color{{accent}}{heading}\\par}}'
        )
        lines.append(r'\vspace{1pt}')
        lines.append(r'{\parfillskip=0pt\relax'
                     r'\noindent{\color{quoteborder}\rule{0.35\textwidth}{0.4pt}}\par}')
        lines.append(r'\vspace{5pt}')
        for a in artifacts:
            kn = a['katalognummer']
            nm = escape_meta(a['name'])
            lbl = f"art:{a['katalog_id'].replace('.', '-').replace(' ', '-')}"
            lines.append(
                r'\noindent{\fontsize{10pt}{12.5pt}\selectfont'
                r'\hspace*{1.2em}'
                f'\\textcolor{{accent}}{{{kn}}}\\hspace{{0.6em}}{nm}'
                r'\dotfill\ '
                f'\\pageref{{{lbl}}}'
                r'\par}'
            )
            lines.append(r'\vspace{2.5pt}')
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

    # Title page: title block in the middle, year at the bottom.
    doc.append(r'\thispagestyle{empty}')
    doc.append(r'\begin{center}')
    doc.append(r'\vspace*{\fill}')
    doc.append(r'{\color{accent}\rule{0.18\textwidth}{1.2pt}\par}')
    doc.append(r'\vspace{14pt}')
    doc.append(r'{\fontsize{40pt}{46pt}\selectfont\bfseries Katalog\par}')
    doc.append(r'\vspace{10pt}')
    doc.append(r'{\fontsize{13pt}{17pt}\selectfont\itshape'
               r'\color{metagray}Sammlung Arnold Ruesch\par}')
    doc.append(r'\vspace{14pt}')
    doc.append(r'{\color{accent}\rule{0.18\textwidth}{1.2pt}\par}')
    doc.append(r'\vspace*{\fill}')
    doc.append(r'{\fontsize{11pt}{14pt}\selectfont\color{refgray}1936\par}')
    doc.append(r'\vspace*{1.2cm}')
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

    # Each chapter (Materialgattung) starts on a new page; artifacts flow
    # within the chapter so short entries do not waste a page.
    current_chapter = None
    first_in_chapter = False
    chapters = [a.get('gattung') or 'Ohne Materialgattung' for a in artifacts]
    for index, art in enumerate(artifacts):
        chapter = chapters[index]
        last_in_chapter = (index + 1 == len(artifacts)
                           or chapters[index + 1] != chapter)
        if chapter != current_chapter:
            current_chapter = chapter
            first_in_chapter = True
            doc.append(r'\newpage')
            doc.append(r'\FloatBarrier')
            # No \markboth here: the first entry sets both marks, and an empty
            # right mark would win over it (\rightmark uses the first mark on
            # the page), leaving the Obergattung blank on chapter pages.
            doc.append('')

        label = art['katalog_id'].replace('.', '-').replace(' ', '-')
        doc.append(generate_artifact_entry(art, bilder_dir, chapter,
                                          first_in_chapter, last_in_chapter,
                                          label))
        first_in_chapter = False
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
