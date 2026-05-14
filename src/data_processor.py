#!/usr/bin/env python3
"""
Data Processor - Reads artefakte_export.csv and produces structured JSON
for the catalog generation pipeline.

Groups rows by Object ID, merges static fields, collects collection history,
and assigns catalog numbers (Gattung.Objekttyp.Laufend).
"""

import csv
import json
import os
import sys
from collections import defaultdict, OrderedDict


def parse_csv(csv_path):
    """Read CSV with proper handling of multiline fields."""
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def normalize_date(date_str):
    """Normalize date string for comparison. Returns (sortable, display)."""
    date_str = date_str.strip()
    if not date_str:
        return (None, None)
    # Replace ∞ with a far-future sentinel
    display = date_str.replace('∞', 'heute')
    # For sorting: ∞ → 9999, extract numeric start
    sort_val = date_str.replace('∞', '9999-99-99')
    return (sort_val, display)


def group_artifacts(rows):
    """
    Group rows by Object ID into unified artifact records.
    
    Each artifact gets:
    - Static fields (same across all rows)
    - Unique images
    - Collection history (chronological)
    - Fundort information
    """
    # Group rows by Object ID
    groups = defaultdict(list)
    for row in rows:
        oid = row['Object ID'].strip()
        groups[oid].append(row)
    
    artifacts = []
    
    for oid, group_rows in groups.items():
        # Identify static fields (same value across all rows)
        r0 = group_rows[0]
        
        artifact = OrderedDict()
        artifact['object_id'] = oid
        artifact['name'] = r0['Name'].strip()
        artifact['gattung'] = r0['Gattung'].strip()
        artifact['objekttyp'] = r0['Objekttyp'].strip()
        artifact['material'] = r0.get('Material', '').strip()
        artifact['groesse'] = r0.get('Grösse', '').strip()
        artifact['datierung'] = r0.get('Datierung', '').strip()
        artifact['kulturkreis'] = r0.get('Kulturkreis', '').strip()
        artifact['kuenstler'] = r0.get('Künstler', '').strip()
        artifact['beschreibung_extern'] = r0.get('Beschreibung extern', '').strip()
        artifact['beschreibung_mie'] = r0.get('Beschreibung durch MIE', '').strip()
        artifact['katalog_fischer'] = r0.get('Katalog Fischer', '').strip()
        artifact['annotationen'] = r0.get('Annotationen Kataloge', '').strip()
        artifact['erhaltung'] = r0.get('Erhaltung', '').strip()
        artifact['referenz_literatur'] = r0.get('Referenz in Literatur', '').strip()
        artifact['vergleiche'] = r0.get('Vergleiche', '').strip()
        artifact['weitere_info_fundort'] = r0.get('weitere Informationen zum Fundort', '').strip()
        artifact['auktionen'] = r0.get('Auktionen', '').strip()
        
        # Fundort (should be same across rows, but collect anyway)
        artifact['fundort'] = {
            'date_start': r0.get('[Fundort] Date Start', '').strip(),
            'date_end': r0.get('[Fundort] Date End', '').strip(),
            'location_reference': r0.get('[Fundort] Location Reference', '').strip(),
            'geometry': r0.get('[Fundort] Geometry', '').strip(),
            'name': r0.get('[Fundort] Name', '').strip(),
            'finder': r0.get('[Fundort] Finder', '').strip(),
        }
        
        # Unique images (deduplicated)
        images = []
        seen = set()
        for row in group_rows:
            img = row.get('Bild', '').strip()
            if img and img not in seen:
                seen.add(img)
                images.append(img)
        artifact['images'] = images
        
        # Collection history (unique combinations, chronologically sorted)
        history_set = set()
        for row in group_rows:
            hist = (
                row.get('[in collection] Date Start', '').strip(),
                row.get('[in collection] Date End', '').strip(),
                row.get('[in collection] Location Reference', '').strip(),
                row.get('[in collection] Sammler', '').strip(),
                row.get('[in collection] Geometry', '').strip(),
                row.get('aktueller Standort', '').strip(),
                row.get('Eigentümer', '').strip(),
                row.get('Status', '').strip(),
            )
            if any(hist):  # Only add if there's some data
                history_set.add(hist)
        
        # Sort history by date_start
        history_list = []
        for h in history_set:
            sort_key, display_start = normalize_date(h[0])
            sort_key_end, display_end = normalize_date(h[1])
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
        
        # Build chronological location list for map (Fundort + collection locations)
        artifact['all_locations'] = build_location_timeline(artifact)
        
        artifacts.append(artifact)
    
    return artifacts


def build_location_timeline(artifact):
    """Build a chronological list of all locations for mapping."""
    locations = []
    
    # Fundort (origin)
    fo = artifact['fundort']
    fo_date = fo['date_end'] or fo['date_start'] or 'unbekannt'
    is_fundort = True
    
    fo_geom = parse_geometry_center(fo.get('geometry', ''))
    if fo_geom:
        locations.append({
            'type': 'Fundort',
            'label': fo.get('name') or fo.get('location_reference') or 'Fundort',
            'date': fo_date,
            'date_start': fo.get('date_start', ''),
            'date_end': fo.get('date_end', ''),
            'geometry': fo_geom,
            'is_fundort': True,
        })
    
    # Collection locations (already chronological)
    for entry in artifact['collection_history']:
        ic_geom = parse_geometry_center(entry.get('geometry', ''))
        loc_label = entry.get('location_reference', '') or entry.get('sammler', '') or entry.get('aktueller_standort', '')
        date_label = entry.get('date_start_display', '')
        
        if loc_label:
            locations.append({
                'type': 'in collection',
                'label': loc_label,
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


def has_geometry_data(locations):
    """Check if any location has geometry data."""
    return any(loc.get('geometry') is not None for loc in locations)


def has_multiple_locations(locations):
    """Check if there are multiple distinct locations for mapping."""
    labels = set()
    for loc in locations:
        geom = loc.get('geometry')
        if geom:
            labels.add(geom)
    return len(labels) >= 1


def assign_catalog_numbers(artifacts):
    """
    Assign catalog numbers in format: Gattung_Nr.Objekttyp_Nr.Laufend_Nr
    
    First level: sorted by Gattung alphabetically
    Second level: within each Gattung, sorted by Objekttyp alphabetically
    Third level: within each Objekttyp, running number
    """
    # Sort artifacts: Gattung → Objekttyp → Name
    artifacts.sort(key=lambda a: (a['gattung'].lower(), a['objekttyp'].lower(), a['name'].lower()))
    
    # Build hierarchy
    gattung_order = {}
    objekttyp_order = {}
    gattung_counter = 0
    current_gattung = None
    current_objekttyp = None
    objekttyp_counter = 0
    
    for artifact in artifacts:
        g = artifact['gattung']
        o = artifact['objekttyp']
        
        if g not in gattung_order:
            gattung_counter += 1
            gattung_order[g] = gattung_counter
            objekttyp_order[(g, o)] = 1
            current_gattung = g
            current_objekttyp = o
            objekttyp_counter = 1
        elif o != current_objekttyp or g != current_gattung:
            objekttyp_counter += 1
            objekttyp_order[(g, o)] = objekttyp_counter
            current_objekttyp = o
    
    # Assign running numbers within each Objekttyp
    running = defaultdict(int)
    for artifact in artifacts:
        g = artifact['gattung']
        o = artifact['objekttyp']
        running[(g, o)] += 1
        g_num = gattung_order[g]
        o_num = objekttyp_order[(g, o)]
        r_num = running[(g, o)]
        artifact['katalognummer'] = f"{g_num}.{o_num}.{r_num}"
    
    return artifacts


def process(input_path, output_path):
    """Main processing function."""
    print(f"[data_processor] Reading {input_path}...")
    rows = parse_csv(input_path)
    print(f"[data_processor]   {len(rows)} rows read")
    
    print(f"[data_processor] Grouping artifacts...")
    artifacts = group_artifacts(rows)
    print(f"[data_processor]   {len(artifacts)} unique artifacts identified")
    
    print(f"[data_processor] Assigning catalog numbers...")
    artifacts = assign_catalog_numbers(artifacts)
    
    for a in artifacts:
        print(f"[data_processor]   {a['katalognummer']}: {a['name'][:60]}")
        print(f"[data_processor]     Images: {len(a['images'])}, History: {len(a['collection_history'])}, Locations: {len(a['all_locations'])}")
    
    # Build TOC structure
    toc = build_toc(artifacts)
    
    result = {
        'artifacts': artifacts,
        'toc': toc,
        'total_artifacts': len(artifacts),
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[data_processor] Output written to {output_path}")
    
    return result


def build_toc(artifacts):
    """Build table of contents structure."""
    toc = OrderedDict()
    for a in artifacts:
        g = a['gattung']
        o = a['objekttyp']
        if g not in toc:
            toc[g] = OrderedDict()
        if o not in toc[g]:
            toc[g][o] = []
        toc[g][o].append({
            'katalognummer': a['katalognummer'],
            'name': a['name'],
        })
    return toc


if __name__ == '__main__':
    csv_path = sys.argv[1] if len(sys.argv) > 1 else '/opt/hermes/work/artefakte_export.csv'
    output_path = sys.argv[2] if len(sys.argv) > 2 else '/opt/hermes/work/artifacts_data.json'
    process(csv_path, output_path)
