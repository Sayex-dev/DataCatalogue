#!/usr/bin/env python3
"""
Map Generator - Creates location history maps for each artifact.

Uses matplotlib + cartopy for high-resolution static map images.
Shows chronological path between locations with color coding:
- Fundort: red/orange square
- Collection locations: blue circle
- Solid lines when both dates are known, dashed lines otherwise

Labels are placed without overlaps by trying candidate offsets around each
point and rejecting boxes that collide with already placed labels.
"""

import json
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.transforms import Bbox
import cartopy.crs as ccrs
import cartopy.feature as cfeature

FUNDORT_COLOR = '#d4451a'
COLLECTION_COLOR = '#1a5ba0'
PATH_COLOR = '#666666'
TEXT_COLOR = '#333333'

FIG_WIDTH = 10.0
FIG_HEIGHT = 6.5

# Label candidate placements (dx, dy, ha, va) in points, tried in order.
LABEL_OFFSETS = (
    (0, 10, 'center', 'bottom'),
    (0, -12, 'center', 'top'),
    (14, 0, 'left', 'center'),
    (-14, 0, 'right', 'center'),
    (12, 10, 'left', 'bottom'),
    (-12, 10, 'right', 'bottom'),
    (12, -12, 'left', 'top'),
    (-12, -12, 'right', 'top'),
    (0, 24, 'center', 'bottom'),
    (0, -26, 'center', 'top'),
)


def wrap_longitude(lon_min, lon_max):
    """Clamp the viewport to valid longitudes."""
    lon_min = max(lon_min, -180.0)
    lon_max = min(lon_max, 180.0)
    if lon_max - lon_min < 0.5:
        center = (lon_min + lon_max) / 2
        lon_min, lon_max = center - 0.25, center + 0.25
    return lon_min, lon_max


def clamp_latitude(lat_min, lat_max):
    """Keep the viewport inside the projection's valid range."""
    lat_min = max(lat_min, -85.0)
    lat_max = min(lat_max, 85.0)
    if lat_max - lat_min < 0.5:
        center = (lat_min + lat_max) / 2
        lat_min, lat_max = center - 0.25, center + 0.25
    return lat_min, lat_max


def compute_extent(locations):
    """Bounding box with padding, corrected for latitude distortion."""
    lons = [loc['geometry'][0] for loc in locations]
    lats = [loc['geometry'][1] for loc in locations]

    lon_span = max(lons) - min(lons)
    lat_span = max(lats) - min(lats)
    lon_span = max(lon_span, 3.0)
    lat_span = max(lat_span, 3.0)

    pad = 0.35
    lon_min = min(lons) - lon_span * pad
    lon_max = max(lons) + lon_span * pad
    lat_min = min(lats) - lat_span * pad
    lat_max = max(lats) + lat_span * pad

    # Degrees of longitude shrink with cos(latitude). Without this correction
    # a mid-latitude region looks horizontally stretched in PlateCarree.
    mid_lat = (lat_min + lat_max) / 2
    lon_scale = max(math.cos(math.radians(mid_lat)), 0.15)
    target_ratio = (FIG_WIDTH / FIG_HEIGHT) / lon_scale

    width = lon_max - lon_min
    height = lat_max - lat_min
    if width / height < target_ratio:
        new_width = height * target_ratio
        center = (lon_min + lon_max) / 2
        lon_min, lon_max = center - new_width / 2, center + new_width / 2
    else:
        new_height = width / target_ratio
        center = (lat_min + lat_max) / 2
        lat_min, lat_max = center - new_height / 2, center + new_height / 2

    lon_min, lon_max = wrap_longitude(lon_min, lon_max)
    lat_min, lat_max = clamp_latitude(lat_min, lat_max)
    return [lon_min, lon_max, lat_min, lat_max]


def place_labels(ax, locations, fig):
    """Annotate every location, avoiding overlaps with earlier labels."""
    placed = []
    renderer = fig.canvas.get_renderer()

    box_style = dict(boxstyle='round,pad=0.28', facecolor='white',
                     alpha=0.88, edgecolor='#cccccc', linewidth=0.5)
    candidates = list(LABEL_OFFSETS) + [(0, 34, 'center', 'bottom'),
                                        (0, 48, 'center', 'bottom')]

    for loc in locations:
        lon, lat = loc['geometry']
        text = loc.get('label') or ''
        if not text:
            continue

        chosen = None
        for dx, dy, ha, va in candidates:
            annotation = ax.annotate(
                text, xy=(lon, lat), xytext=(dx, dy),
                textcoords='offset points', fontsize=6,
                ha=ha, va=va, color=TEXT_COLOR, weight='bold',
                bbox=box_style, zorder=7,
            )
            box = annotation.get_window_extent(renderer=renderer)
            padded = Bbox.from_extents(box.x0 - 2, box.y0 - 2,
                                       box.x1 + 2, box.y1 + 2)
            if not any(padded.overlaps(other) for other in placed):
                placed.append(padded)
                chosen = annotation
                break
            annotation.remove()

        if chosen is None:
            # Extreme fallback: place far above the point anyway.
            chosen = ax.annotate(
                text, xy=(lon, lat), xytext=(0, 62),
                textcoords='offset points', fontsize=6, ha='center',
                va='bottom', color=TEXT_COLOR, weight='bold',
                bbox=box_style, zorder=7,
            )
            placed.append(chosen.get_window_extent(renderer=renderer))


def add_path(ax, locations):
    """Draw chronological connecting lines with direction arrows."""
    for first, second in zip(locations, locations[1:]):
        lon1, lat1 = first['geometry']
        lon2, lat2 = second['geometry']

        dates_known = all(
            loc.get('date_start') or loc.get('date_end')
            for loc in (first, second)
        )
        linestyle = '-' if dates_known else '--'
        alpha = 0.8 if dates_known else 0.5
        linewidth = 1.5 if dates_known else 1.0

        ax.plot([lon1, lon2], [lat1, lat2], color=PATH_COLOR,
                linestyle=linestyle, linewidth=linewidth, alpha=alpha,
                zorder=3, transform=ccrs.PlateCarree())

        mid_lon = (lon1 + lon2) / 2
        mid_lat = (lat1 + lat2) / 2
        dx = (lon2 - lon1) * 0.15
        dy = (lat2 - lat1) * 0.15
        ax.annotate('', xy=(mid_lon + dx, mid_lat + dy),
                    xytext=(mid_lon - dx, mid_lat - dy),
                    arrowprops=dict(arrowstyle='->', color=PATH_COLOR,
                                    alpha=alpha, lw=1.2, shrinkA=3, shrinkB=3),
                    zorder=4)


def add_features(ax):
    """Map background tuned for orientation rather than decoration."""
    ax.add_feature(cfeature.LAND, facecolor='#f7f4ee',
                   edgecolor='#c8bda8', linewidth=0.5, zorder=1)
    ax.add_feature(cfeature.OCEAN, facecolor='#cfe0ee',
                   edgecolor='#a8bdd2', linewidth=0.3, zorder=1)
    ax.add_feature(cfeature.LAKES, facecolor='#cfe0ee',
                   edgecolor='#a8bdd2', linewidth=0.3, zorder=2)
    ax.add_feature(cfeature.RIVERS, facecolor='none',
                   edgecolor='#a9c6dc', linewidth=0.4, zorder=2)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8,
                   edgecolor='#7d7368', zorder=2)
    ax.add_feature(cfeature.BORDERS, linewidth=0.35,
                   edgecolor='#a99c88', linestyle=':', zorder=2)

    # Graticule without numeric labels: coordinates are not part of the book.
    ax.gridlines(draw_labels=False, linewidth=0.25, color='#8f8f8f',
                 alpha=0.25, linestyle=':')


def create_map(artifact, output_dir, bilder_dir=None):
    """Create a location history map for a single artifact."""
    locations = [loc for loc in artifact.get('all_locations', [])
                 if loc.get('geometry') is not None]

    if not locations:
        print(f"  [map] No geometry data for {artifact['katalognummer']} - skipping")
        return None

    fig = plt.figure(figsize=(FIG_WIDTH, FIG_HEIGHT), dpi=150)
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_extent(compute_extent(locations), crs=ccrs.PlateCarree())
    add_features(ax)

    for loc in locations:
        lon, lat = loc['geometry']
        is_fundort = bool(loc.get('is_fundort'))
        ax.scatter(lon, lat,
                   c=FUNDORT_COLOR if is_fundort else COLLECTION_COLOR,
                   marker='s' if is_fundort else 'o',
                   s=110 if is_fundort else 75,
                   zorder=5, edgecolors='white', linewidth=0.8,
                   transform=ccrs.PlateCarree())

    add_path(ax, locations)
    place_labels(ax, locations, fig)

    legend_elements = [
        Line2D([0], [0], marker='s', color='w', markerfacecolor=FUNDORT_COLOR,
               markersize=8, label='Fundort',
               markeredgecolor='white', markeredgewidth=0.5),
        Line2D([0], [0], marker='o', color='w', markerfacecolor=COLLECTION_COLOR,
               markersize=8, label='Sammlungsstandort',
               markeredgecolor='white', markeredgewidth=0.5),
        Line2D([0], [0], color=PATH_COLOR, linestyle='-', linewidth=1.5,
               label='Verlauf gesichert'),
        Line2D([0], [0], color=PATH_COLOR, linestyle='--', linewidth=1.0,
               label='Verlauf ungesichert'),
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=7,
              framealpha=0.92, edgecolor='#cccccc')

    plt.tight_layout()

    safe_name = artifact['object_id']
    map_path = os.path.join(output_dir, f'map_{safe_name}.png')
    plt.savefig(map_path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close()

    print(f'  [map] Created: {map_path}')
    return f'map_{safe_name}.png'


def generate_maps(data_path, output_dir, bilder_dir=None):
    """Generate maps for all artifacts."""
    os.makedirs(output_dir, exist_ok=True)

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    artifacts = data.get('artifacts', [])
    print(f'[map_generator] Processing {len(artifacts)} artifacts...')

    map_files = {}
    for artifact in artifacts:
        map_filename = create_map(artifact, output_dir, bilder_dir)
        if map_filename:
            map_files[artifact['object_id']] = map_filename

    print(f'[map_generator] Generated {len(map_files)} maps')
    return map_files


if __name__ == '__main__':
    data_path = sys.argv[1] if len(sys.argv) > 1 else 'artifacts_data.json'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'latex_temp/maps'
    bilder_dir = sys.argv[3] if len(sys.argv) > 3 else 'bilder'
    generate_maps(data_path, output_dir, bilder_dir)
