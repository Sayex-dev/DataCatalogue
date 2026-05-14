#!/usr/bin/env python3
"""
Map Generator - Creates location history maps for each artifact.

Uses matplotlib + cartopy for high-resolution static map images.
Shows chronological path between locations with color coding:
- Fundort: red/orange
- Collection locations: blue
- Solid lines when dates are known, dashed lines otherwise
"""

import json
import os
import sys
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import cartopy.crs as ccrs
import cartopy.feature as cfeature


def create_map(artifact, output_dir, bilder_dir=None):
    """Create a location history map for a single artifact."""
    locations = artifact.get('all_locations', [])
    
    # Filter to locations with geometry
    geo_locations = [loc for loc in locations if loc.get('geometry') is not None]
    
    if len(geo_locations) < 1:
        print(f"  [map] No geometry data for {artifact['katalognummer']} - skipping")
        return None
    
    # Extract coordinates
    lons = [loc['geometry'][0] for loc in geo_locations]
    lats = [loc['geometry'][1] for loc in geo_locations]
    
    # Calculate map bounds with padding
    lon_range = max(lons) - min(lons) if len(lons) > 1 else 5
    lat_range = max(lats) - min(lats) if len(lats) > 1 else 5
    
    # Minimum viewport of ~3 degrees
    lon_range = max(lon_range, 3)
    lat_range = max(lat_range, 3)
    
    pad_factor = 0.4
    lon_min = min(lons) - lon_range * pad_factor
    lon_max = max(lons) + lon_range * pad_factor
    lat_min = min(lats) - lat_range * pad_factor
    lat_max = max(lats) + lat_range * pad_factor
    
    # Create figure with high DPI
    fig = plt.figure(figsize=(10, 6.5), dpi=150)
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    # Set map extent
    ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
    
    # Add map features
    ax.add_feature(cfeature.LAND, facecolor='#f5f0e8', edgecolor='#c0b090', linewidth=0.5)
    ax.add_feature(cfeature.OCEAN, facecolor='#d4e4f0', edgecolor='#a0b8d0', linewidth=0.3)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8, edgecolor='#8a8078')
    ax.add_feature(cfeature.BORDERS, linewidth=0.4, edgecolor='#a09080', linestyle='--')
    ax.add_feature(cfeature.RIVERS, linewidth=0.2, edgecolor='#b0c8e0')
    ax.add_feature(cfeature.LAKES, facecolor='#d4e4f0', edgecolor='#a0b8d0', linewidth=0.3)
    
    # Gridlines
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.4, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 7, 'color': '#666666'}
    gl.ylabel_style = {'size': 7, 'color': '#666666'}
    
    # Plot locations
    fundort_color = '#d4451a'  # Warm red-orange
    collection_color = '#1a5ba0'  # Deep blue
    fundort_marker = 's'
    collection_marker = 'o'
    
    fundort_lons = []
    fundort_lats = []
    collection_lons = []
    collection_lats = []
    
    for i, loc in enumerate(geo_locations):
        lon, lat = loc['geometry']
        if loc.get('is_fundort'):
            fundort_lons.append(lon)
            fundort_lats.append(lat)
        else:
            collection_lons.append(lon)
            collection_lats.append(lat)
        
        # Plot the point
        color = fundort_color if loc.get('is_fundort') else collection_color
        marker = fundort_marker if loc.get('is_fundort') else collection_marker
        size = 120 if loc.get('is_fundort') else 80
        
        ax.scatter(lon, lat, c=color, marker=marker, s=size, zorder=5,
                   edgecolors='white', linewidth=0.8, transform=ccrs.PlateCarree())
        
        # Label
        label = loc.get('label', '')
        date_str = loc.get('date', '')
        display_text = f"{label}"
        if date_str and date_str != 'unbekannt':
            display_text += f"\n({date_str})"
        
        # Offset label to avoid overlap
        offset_y = 0.15 * lat_range if i % 2 == 0 else -0.15 * lat_range
        ax.annotate(display_text, xy=(lon, lat),
                    xytext=(0, 8 if i % 2 == 0 else -10),
                    textcoords='offset points',
                    fontsize=6, ha='center', va='bottom' if i % 2 == 0 else 'top',
                    color='#333333', weight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.85, edgecolor='#cccccc', linewidth=0.5),
                    zorder=6)
    
    # Draw connecting lines in chronological order
    for i in range(len(geo_locations) - 1):
        loc1 = geo_locations[i]
        loc2 = geo_locations[i + 1]
        
        lon1, lat1 = loc1['geometry']
        lon2, lat2 = loc2['geometry']
        
        # Determine line style based on date availability
        date1_known = bool(loc1.get('date_start') or loc1.get('date_end'))
        date2_known = bool(loc2.get('date_start') or loc2.get('date_end'))
        
        if date1_known and date2_known:
            linestyle = '-'  # Solid line: both dates known
            alpha = 0.8
            linewidth = 1.5
        else:
            linestyle = '--'  # Dashed line: missing date
            alpha = 0.5
            linewidth = 1.0
        
        # Color: use a neutral path color
        path_color = '#666666'
        
        ax.plot([lon1, lon2], [lat1, lat2],
                color=path_color, linestyle=linestyle, linewidth=linewidth,
                alpha=alpha, zorder=3, transform=ccrs.PlateCarree())
        
        # Arrow in the middle
        mid_lon = (lon1 + lon2) / 2
        mid_lat = (lat1 + lat2) / 2
        dx = (lon2 - lon1) * 0.15
        dy = (lat2 - lat1) * 0.15
        ax.annotate('', xy=(mid_lon + dx, mid_lat + dy),
                    xytext=(mid_lon - dx, mid_lat - dy),
                    arrowprops=dict(arrowstyle='->', color=path_color, alpha=alpha,
                                   lw=1.2, shrinkA=3, shrinkB=3),
                    zorder=4)
    
    # Legend
    legend_elements = [
        Line2D([0], [0], marker=fundort_marker, color='w', markerfacecolor=fundort_color,
               markersize=8, label='Fundort', markeredgecolor='white', markeredgewidth=0.5),
        Line2D([0], [0], marker=collection_marker, color='w', markerfacecolor=collection_color,
               markersize=8, label='Sammlungsstandort', markeredgecolor='white', markeredgewidth=0.5),
        Line2D([0], [0], color='#666666', linestyle='-', linewidth=1.5, label='Datierung bekannt'),
        Line2D([0], [0], color='#666666', linestyle='--', linewidth=1.0, label='Datierung unbekannt'),
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=7,
              framealpha=0.9, edgecolor='#cccccc')
    
    # Title
    ax.set_title(f"Standortverlauf: {artifact['name']} (Kat.-Nr. {artifact['katalognummer']})",
                 fontsize=10, pad=10, color='#333333')
    
    plt.tight_layout()
    
    # Save
    safe_name = artifact['object_id']
    map_path = os.path.join(output_dir, f"map_{safe_name}.png")
    plt.savefig(map_path, dpi=150, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close()
    
    print(f"  [map] Created: {map_path}")
    return f"map_{safe_name}.png"


def generate_maps(data_path, output_dir, bilder_dir=None):
    """Generate maps for all artifacts."""
    os.makedirs(output_dir, exist_ok=True)
    
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    artifacts = data.get('artifacts', [])
    print(f"[map_generator] Processing {len(artifacts)} artifacts...")
    
    map_files = {}
    for artifact in artifacts:
        map_filename = create_map(artifact, output_dir, bilder_dir)
        if map_filename:
            map_files[artifact['object_id']] = map_filename
    
    print(f"[map_generator] Generated {len(map_files)} maps")
    return map_files


if __name__ == '__main__':
    data_path = sys.argv[1] if len(sys.argv) > 1 else '/opt/hermes/work/artifacts_data.json'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '/opt/hermes/work/latex_temp/maps'
    bilder_dir = sys.argv[3] if len(sys.argv) > 3 else '/opt/hermes/work/bilder'
    generate_maps(data_path, output_dir, bilder_dir)
