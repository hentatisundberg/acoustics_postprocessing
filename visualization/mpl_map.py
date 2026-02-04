import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import PatchCollection
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import numpy as np
import h3

# Optional: contextily for basemap
try:
    import contextily as ctx
    CONTEXTILY_AVAILABLE = True
except ImportError:
    CONTEXTILY_AVAILABLE = False

from utils.io_helpers import read_config
from pathlib import Path
import geopandas as gpd
import os
from pyproj import Transformer

def create_matplotlib_hex_map(hex_data, value_column, cmap="viridis", show_colorbar=True, use_basemap=True, title=None, figsize=(12, 10), config_path="config/settings.yaml", show=True, coastline_path=None, east_lim=None, north_lim=None, vmin=None, vmax=None):
    grouped = hex_data.copy()
    if grouped.empty:
        raise ValueError(f"No data to plot for {value_column}")
    # Read config for CRS/column selection
    config = read_config(Path(config_path))
    coords_cfg = config.get("coordinates", {})
    columns = coords_cfg.get("columns", {})
    sweref_mode = coords_cfg.get("output_crs", "EPSG:3006") == coords_cfg.get("active_crs", coords_cfg.get("output_crs", "EPSG:3006"))
    easting_col = columns.get("output_easting", "easting")
    northing_col = columns.get("output_northing", "northing")
    lat_col = columns.get("input_lat", "latitude")
    lon_col = columns.get("input_lon", "longitude")

    fig, ax = plt.subplots(figsize=figsize)
    patches = []
    values = []
    # Prepare transformer for SWEREF99 if needed
    transformer = None
    if sweref_mode:
        # Transform from WGS84 (lon, lat) to SWEREF99 TM (easting, northing)
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)

    for _, row in grouped.iterrows():
        hex_id = row.get("h3_hex") or row.get("hex_id")
        value = row[value_column]
        boundary = h3.cell_to_boundary(hex_id)
        # h3 returns list of (lat, lon); convert to (lon, lat)
        lonlat_coords = [(lon, lat) for lat, lon in boundary]
        if sweref_mode and transformer is not None:
            # Reproject to EPSG:3006 for consistent axes and basemap
            coords = [transformer.transform(lon, lat) for lon, lat in lonlat_coords]
        else:
            coords = lonlat_coords
        polygon = mpatches.Polygon(coords, closed=True)
        patches.append(polygon)
        values.append(value)
    # Use provided vmin/vmax if available; otherwise compute from data
    data_vmin = min(values) if vmin is None else float(vmin)
    data_vmax = max(values) if vmax is None else float(vmax)
    norm = Normalize(vmin=data_vmin, vmax=data_vmax)
    cmap_obj = plt.get_cmap(cmap)
    collection = PatchCollection(
        patches,
        cmap=cmap_obj,
        norm=norm,
        alpha=0.7,
        edgecolor='none',
        linewidth=0
    )
    collection.set_array(np.array(values))
    ax.add_collection(collection)
    all_coords = np.concatenate([p.get_path().vertices for p in patches])
    margin = 0.02
    # Allow user to specify east/north limits
    if east_lim is not None:
        ax.set_xlim(east_lim)
    else:
        ax.set_xlim(all_coords[:, 0].min() - margin, all_coords[:, 0].max() + margin)
    if north_lim is not None:
        ax.set_ylim(north_lim)
    else:
        ax.set_ylim(all_coords[:, 1].min() - margin, all_coords[:, 1].max() + margin)
    # Basemap CRS and axis labels
    if sweref_mode:
        ax.set_xlabel('Easting (SWEREF99 TM)')
        ax.set_ylabel('Northing (SWEREF99 TM)')
        if use_basemap and CONTEXTILY_AVAILABLE:
            try:
                ctx.add_basemap(ax, crs="EPSG:3006", source=ctx.providers.OpenStreetMap.Mapnik, attribution=False)
            except Exception as e:
                print(f"Warning: Could not add basemap: {e}")
        # Add Sweden coastline if provided
        if coastline_path and os.path.exists(coastline_path):
            try:
                coast = gpd.read_file(coastline_path)
                coast = coast.to_crs("EPSG:3006")
                coast.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=1, zorder=10)
            except Exception as e:
                print(f"Warning: Could not plot Sweden coastline: {e}")
    else:
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        if use_basemap and CONTEXTILY_AVAILABLE:
            try:
                ctx.add_basemap(ax, crs="EPSG:4326", source=ctx.providers.OpenStreetMap.Mapnik, attribution=False)
            except Exception as e:
                print(f"Warning: Could not add basemap: {e}")
        if coastline_path and os.path.exists(coastline_path):
            try:
                coast = gpd.read_file(coastline_path)
                coast = coast.to_crs("EPSG:4326")
                coast.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=1, zorder=10)
            except Exception as e:
                print(f"Warning: Could not plot Sweden coastline: {e}")
    if show_colorbar:
        sm = ScalarMappable(cmap=cmap_obj, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, orientation='vertical', pad=0.02, fraction=0.046)
        cbar.set_label(value_column, rotation=270, labelpad=20)
    ax.set_title(title or f"Map of {value_column}")
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    plt.tight_layout()
    if show:
        plt.show()
    return fig
