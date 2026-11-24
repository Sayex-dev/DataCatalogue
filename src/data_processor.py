#!/usr/bin/env python3
"""
Data Processor - Reads artefakte_export.csv and produces structured JSON
for the catalog generation pipeline.

Groups rows by Object ID, merges static fields, collects collection history,
and assigns catalog numbers (Gattung.Objekttyp.Laufend).

The database export renames columns between releases. Every field access goes
through COLUMN_ALIASES / get_field(), so a rename only needs one edit here.
"""

import csv
import io
import json
import re
import sys
from collections import defaultdict, OrderedDict

# Canonical field -> CSV columns, first matching column wins.
# Current export column names come first, older names are kept as fallbacks.
COLUMN_ALIASES = {
    'object_id': ('Object ID',),
    'name': ('Name',),
    'katalognummer_raw': ('Katalognummer',),
    'objektname': ('Objektname',),
    'gattung': ('Gattung', 'Materialgattung'),
    'objekttyp': ('Objekttyp', 'Objektgattung'),
    'obergattung': ('Obergattung',),
    'material': ('Material', 'Materialien'),
    'groesse': ('Grösse',),
    'datierung': ('Datierung',),
    'kulturkreis': ('Kulturkreis',),
    'kuenstler': ('Künstler',),
    'erhaltung': ('Erhaltung',),
    'beschreibung_fischer': ('Beschreibung Katalog Fischer',),
    'beschreibung_extern': ('Beschreibung extern',),
    'beschreibung_mie': ('Beschreibung durch MIE',),
    'katalog_fischer': ('Lot-Nr. Katalog Fischer 1936', 'Katalog Fischer'),
    'annotationen': ('Annotationen Kataloge', 'Anmerkungen'),
    'referenz_literatur': ('Referenz in Literatur',),
    'vergleiche': ('Vergleiche',),
    'weitere_info_fundort': ('weitere Informationen zum Fundort',),
    'auktionen': ('Auktionen', 'Auktionen und Verkäufe'),
    'provenienz': ('Provenienz',),
    'aktueller_standort': ('aktueller Standort',),
    'eigentuemer': ('Eigentümer', 'aktuelle Eigentümer:in'),
    'status': ('Status',),
    'inv_nr_uzh': ('Inv. Nr. Archäologische Sammlung UZH',),
    'platzierung_haus': ('Platzierung in Haus',),
    'bild': ('Bild',),
    'bildreferenz': ('Bildreferenz',),
    'bildbeschreibung': ('Bildbeschreibung',),
    'abbildungsnachweis': ('Abbildungsnachweis', 'Bildquelle'),
    'fundort_date_start': ('[Fundort] Date Start',),
    'fundort_date_end': ('[Fundort] Date End',),
    'fundort_location_reference': ('[Fundort] Location Reference',),
    'fundort_geometry': ('[Fundort] Geometry',),
    'fundort_name': ('[Fundort] Name',),
    'fundort_finder': ('[Fundort] Finder',),
    'ic_date_start': ('[in collection] Date Start',),
    'ic_date_end': ('[in collection] Date End',),
    'ic_location_reference': ('[in collection] Location Reference',),
    'ic_geometry': ('[in collection] Geometry',),
    'ic_sammler': ('[in collection] Sammler',),
}

# Without these the export cannot be processed at all.
REQUIRED_COLUMNS = ('Object ID', 'Name')

ENCODINGS = ('utf-8-sig', 'cp1252')


def get_field(row, key, default=''):
    """Read a canonical field from a CSV row, following COLUMN_ALIASES."""
    for column in COLUMN_ALIASES.get(key, (key,)):
        if column in row:
            value = row[column]
            if value is not None and str(value).strip():
                return str(value).strip()
    return default


def parse_csv(csv_path):
    """Read the CSV, tolerating a BOM and legacy Windows-1252 exports."""
    text = None
    for encoding in ENCODINGS:
        try:
            with open(csv_path, 'r', encoding=encoding, newline='') as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise SystemExit(
            f'[data_processor] ERROR: {csv_path} is neither UTF-8 nor CP1252 '
            'encoded'
        )

    reader = csv.DictReader(io.StringIO(text, newline=''))
    # Some exports carry trailing spaces in the header names.
    reader.fieldnames = [(f or '').strip() for f in (reader.fieldnames or [])]
    return list(reader), list(reader.fieldnames)


def resolve_columns(fieldnames):
    """Return {canonical field: CSV column actually used}."""
    resolved = {}
    for key, columns in COLUMN_ALIASES.items():
        for column in columns:
            if column in fieldnames:
                resolved[key] = column
                break
    return resolved


def validate_columns(fieldnames):
    """Fail early with an actionable message instead of a KeyError deep inside."""
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise SystemExit(
            '[data_processor] ERROR: the export is missing required column(s): '
            + ', '.join(missing)
            + '\n[data_processor] Columns found:\n  - '
            + '\n  - '.join(fieldnames)
            + '\n[data_processor] If a column was renamed, add the new name to '
            'COLUMN_ALIASES in src/data_processor.py.'
        )

    resolved = resolve_columns(fieldnames)
    absent = [key for key in COLUMN_ALIASES if key not in resolved]
    if absent:
        print('[data_processor] WARNING: no column found for these fields: '
              + ', '.join(absent))


def normalize_date(date_str):
    text = (date_str or '').strip()
    if not text:
        return (None, None)

    # -∞ means "no known start", ∞ means "still ongoing"
    if '∞' in text:
        if text.lstrip().startswith('-'):
            return ('-9999-99-99', '')
        return ('9999-99-99', text.replace('∞', 'heute'))
    return (text, text)


def clean_name(raw_name, katalognummer='', objektname=''):
    """
    Strip the database number from the display name.

    The export prefixes Name with Katalognummer (e.g. "42 L 1752 Fischteller").
    Objektname already holds the cleaned value whenever the database has one.
    """
    name = (raw_name or '').strip()
    if (objektname or '').strip():
        return objektname.strip()

    number = (katalognummer or '').strip()
    if number and name.startswith(number):
        rest = name[len(number):].strip()
        if rest:
            return rest.lstrip()

    # Fallback: strip leading number tokens one by one, e.g.
    # "42 L 1752 (L 242) Fischteller" -> "Fischteller".
    token = re.compile(
        r'^(?:L\s?\d+[a-c]?|\d+[a-c]?(?:-\w+)?|\(\s*L\s?\d+\s*\))\s+'
    )
    cleaned = name
    while True:
        stripped = token.sub('', cleaned, count=1)
        if stripped == cleaned or not stripped.strip():
            break
        cleaned = stripped
    return cleaned.strip() or name


KATALOGNUMMER_RE = re.compile(
    r'^L?\s?(\d+)\s*([a-c](?=[\s-]|$))?\s*(?:-\s*[a-c])?\s*(.*)$'
)


def parse_katalognummer(raw):
    """
    Split the export's Katalognummer into (number, suffix, caption).

    Only the numeric part drives the order; any trailing text in the column is
    an artefact name left over from an older export and is ignored.
    "11b L 1099 attische rotfigurige Hydria" -> (11, 'b', '')
    """
    text = (raw or '').strip()
    match = KATALOGNUMMER_RE.match(text)
    if not match:
        return (None, '', text)
    return (int(match.group(1)), match.group(2) or '', '')


def format_katalognummer(number, suffix):
    """Display form of the catalogue number, e.g. 11b or 274."""
    if number is None:
        return ''
    return f'{number}{suffix}'


def chapter_order_key(gattung):
    """Sort chapters by Materialgattung; unassigned objects go last."""
    return (1, '') if not gattung else (0, gattung.lower())



def group_artifacts(rows):
    """
    Group rows by Object ID into unified artifact records.

    Each artifact gets:
    - Static fields (same across all rows)
    - Unique images
    - Collection history (chronological)
    - Fundort information
    """
    groups = defaultdict(list)
    for row in rows:
        oid = get_field(row, 'object_id')
        if oid:
            groups[oid].append(row)

    artifacts = []

    for oid, group_rows in groups.items():
        r0 = group_rows[0]

        artifact = OrderedDict()
        artifact['object_id'] = oid
        artifact['name'] = clean_name(
            get_field(r0, 'name'),
            get_field(r0, 'katalognummer_raw'),
            get_field(r0, 'objektname'),
        )
        raw_number = get_field(r0, 'katalognummer_raw')
        number, suffix, _ = parse_katalognummer(raw_number)
        artifact['kat_nummer'] = number
        artifact['kat_suffix'] = suffix
        artifact['katalognummer'] = format_katalognummer(number, suffix)
        for key in ('gattung', 'objekttyp', 'obergattung', 'material',
                    'groesse', 'datierung', 'kulturkreis', 'kuenstler',
                    'erhaltung', 'beschreibung_fischer',
                    'beschreibung_extern', 'beschreibung_mie',
                    'katalog_fischer', 'annotationen', 'referenz_literatur',
                    'vergleiche', 'weitere_info_fundort', 'auktionen',
                    'provenienz', 'aktueller_standort', 'eigentuemer',
                    'status', 'inv_nr_uzh', 'platzierung_haus',
                    'bildreferenz', 'bildbeschreibung',
                    'abbildungsnachweis'):
            artifact[key] = get_field(r0, key)

        # Catalog numbers are only unique per chapter, so the label key keeps
        # the chapter as well.
        artifact['katalog_id'] = (
            f"{artifact['gattung'] or 'Ohne Materialgattung'}-{number}{suffix}"
            if number is not None else oid
        )

        artifact['fundort'] = {
            'date_start': get_field(r0, 'fundort_date_start'),
            'date_end': get_field(r0, 'fundort_date_end'),
            'location_reference': get_field(r0, 'fundort_location_reference'),
            'geometry': get_field(r0, 'fundort_geometry'),
            'name': get_field(r0, 'fundort_name'),
            'finder': get_field(r0, 'fundort_finder'),
        }

        # Image file names come from Bildreferenz (";"-separated). The legacy
        # Bild column only holds opaque hash names and is no longer used.
        images = []
        seen = set()
        for row in group_rows:
            for ref in get_field(row, 'bildreferenz').split(';'):
                name = ref.strip()
                if name and name not in seen:
                    seen.add(name)
                    images.append(name)
        artifact['images'] = images

        # Collection history (unique combinations, chronologically sorted)
        history_set = set()
        for row in group_rows:
            hist = (
                get_field(row, 'ic_date_start'),
                get_field(row, 'ic_date_end'),
                get_field(row, 'ic_location_reference'),
                get_field(row, 'ic_sammler'),
                get_field(row, 'ic_geometry'),
                get_field(row, 'aktueller_standort'),
                get_field(row, 'eigentuemer'),
                get_field(row, 'status'),
            )
            if any(hist):  # Only add if there's some data
                history_set.add(hist)

        history_list = []
        for h in history_set:
            sort_key, display_start = normalize_date(h[0])
            _, display_end = normalize_date(h[1])
            history_list.append({
                'date_start': h[0],
                'date_end': h[1],
                'date_start_display': display_start or h[0],
                'date_end_display': display_end or h[1],
                'location_reference': h[2],
                'sammler': h[3],
                'geometry': h[4],
                'aktueller_standort': h[5],
                'eigentuemer': h[6],
                'status': h[7],
                'sort_key': sort_key or '0000',
            })

        history_list.sort(key=lambda x: x['sort_key'])
        artifact['collection_history'] = history_list

        # Chronological location list for map and location table
        artifact['all_locations'] = build_location_timeline(artifact)

        artifacts.append(artifact)

    return artifacts


def build_location_timeline(artifact):
    """Build a chronological list of all locations for mapping."""
    locations = []

    # Fundort (origin)
    fo = artifact['fundort']
    fo_date = fo['date_end'] or fo['date_start'] or 'unbekannt'
    fo_label = fo.get('name') or fo.get('location_reference') or ''

    fo_geom = parse_geometry_center(fo.get('geometry', ''))
    if fo_geom:
        locations.append({
            'type': 'Fundort',
            'label': fo_label or 'Fundort',
            'ort': fo.get('name', ''),
            'date': fo_date,
            'date_start': fo.get('date_start', ''),
            'date_end': fo.get('date_end', ''),
            'geometry': fo_geom,
            'is_fundort': True,
        })

    # Collection locations (already chronological)
    for entry in artifact['collection_history']:
        ic_geom = parse_geometry_center(entry.get('geometry', ''))
        loc_label = (entry.get('location_reference', '')
                     or entry.get('sammler', '')
                     or entry.get('aktueller_standort', ''))
        date_label = entry.get('date_start_display', '')

        if loc_label:
            locations.append({
                'type': 'in collection',
                'label': loc_label,
                'ort': entry.get('aktueller_standort', ''),
                'date': date_label,
                'date_start': entry.get('date_start', ''),
                'date_end': entry.get('date_end', ''),
                'geometry': ic_geom,
                'is_fundort': False,
                'sammler': entry.get('sammler', ''),
            })

    return locations


def parse_geometry_center(geom_str):
    """Extract center coordinates from a GeoJSON geometry string.
    Returns (lon, lat) or None."""
    if not geom_str or not geom_str.strip():
        return None
    try:
        geom = json.loads(geom_str)
        coords = extract_all_coordinates(geom)
        if coords:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            return (sum(lons) / len(lons), sum(lats) / len(lats))
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        pass
    return None


def extract_all_coordinates(geom):
    """Recursively extract all coordinate pairs from a GeoJSON geometry."""
    coords = []
    if isinstance(geom, dict):
        gtype = geom.get('type', '')
        if gtype == 'Point':
            return [tuple(geom['coordinates'])]
        elif gtype in ('MultiPoint', 'LineString'):
            return [tuple(c) for c in geom['coordinates']]
        elif gtype in ('MultiLineString', 'Polygon'):
            for ring in geom['coordinates']:
                coords.extend([tuple(c) for c in ring])
        elif gtype == 'MultiPolygon':
            for poly in geom['coordinates']:
                for ring in poly:
                    coords.extend([tuple(c) for c in ring])
        elif gtype == 'GeometryCollection':
            for g in geom.get('geometries', []):
                coords.extend(extract_all_coordinates(g))
    return coords




def order_artifacts(artifacts):
    """
    Order the catalog: chapters by Materialgattung, within a chapter by the
    catalogue number taken from the export.

    The catalogue number is the authoritative order. Numbers with a letter
    suffix keep their position (4a before 4b) and stay unique.
    """
    artifacts.sort(key=lambda a: (
        chapter_order_key(a['gattung']),
        a['kat_nummer'] if a['kat_nummer'] is not None else 10 ** 9,
        a['kat_suffix'],
        a['name'].lower(),
    ))
    return artifacts


def build_toc(artifacts):
    """Table of contents keyed by chapter (Materialgattung)."""
    toc = OrderedDict()
    for artifact in artifacts:
        chapter = artifact['gattung'] or 'Ohne Materialgattung'
        toc.setdefault(chapter, []).append({
            'katalognummer': artifact['katalognummer'],
            'katalog_id': artifact['katalog_id'],
            'name': artifact['name'],
        })
    return toc


def build_chapters(artifacts):
    """Group artifacts into chapters while preserving the catalog order."""
    chapters = OrderedDict()
    for artifact in artifacts:
        title = artifact['gattung'] or 'Ohne Materialgattung'
        chapters.setdefault(title, []).append(artifact)
    return [
        {'title': title, 'count': len(items), 'artifacts': items}
        for title, items in chapters.items()
    ]


def process(input_path, output_path):
    """Main processing function."""
    print(f'[data_processor] Reading {input_path}...')
    rows, fieldnames = parse_csv(input_path)
    validate_columns(fieldnames)
    print(f'[data_processor]   {len(rows)} rows read')

    resolved = resolve_columns(fieldnames)
    print('[data_processor] Column mapping:')
    for key in ('gattung', 'objekttyp', 'material', 'katalog_fischer',
                'annotationen', 'auktionen', 'eigentuemer',
                'beschreibung_fischer'):
        column = resolved.get(key)
        print(f"[data_processor]   {key:<22} <- {column or 'MISSING'}")

    print('[data_processor] Grouping artifacts...')
    artifacts = group_artifacts(rows)
    print(f'[data_processor]   {len(artifacts)} unique artifacts identified')

    print('[data_processor] Ordering catalog (chapters by Materialgattung, '
          'objects by Katalognummer)...')
    artifacts = order_artifacts(artifacts)

    empty_gattung = [a for a in artifacts if not a['gattung']]
    if empty_gattung:
        print(f'[data_processor] WARNING: {len(empty_gattung)} artifacts have no '
              "Materialgattung and are listed under 'Ohne Materialgattung'")
    numeric_names = [a for a in artifacts if a['name'].isdigit()]
    if numeric_names:
        print(f'[data_processor] WARNING: {len(numeric_names)} artifacts only '
              'have a numeric name (no Objektname in the export)')

    chapters = build_chapters(artifacts)
    print(f'[data_processor] {len(chapters)} chapters:')
    for chapter in chapters:
        numbers = [a['kat_nummer'] for a in chapter['artifacts']
                   if a['kat_nummer'] is not None]
        span = f'{min(numbers)}-{max(numbers)}' if numbers else '-'
        print(f"[data_processor]   {chapter['title']} "
              f"({chapter['count']} objects, Nr. {span})")

    result = {
        'artifacts': artifacts,
        'chapters': [
            {'title': c['title'], 'count': c['count']} for c in chapters
        ],
        'toc': build_toc(artifacts),
        'total_artifacts': len(artifacts),
        'source_columns': fieldnames,
        'column_mapping': resolved,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'[data_processor] Output written to {output_path}')

    return result


if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'artefakte_export.csv'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'artifacts_data.json'
    process(csv_path, output_path)
