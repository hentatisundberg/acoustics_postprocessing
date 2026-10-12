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

import geopandas as gpd
import os
from pyproj import Transformer


def _resolve_provider(provider_path: str):
    if not provider_path:
        return None
    if not CONTEXTILY_AVAILABLE:
        return None
    provider = ctx.providers
    for segment in provider_path.split("."):
        provider = getattr(provider, segment, None)
        if provider is None:
            return None
    return provider


def create_matplotlib_hex_map(
    hex_data,
    value_column,
    *,
    map_settings: dict | None = None,
    coords_cfg: dict | None = None,
    cmap: str | None = None,
    title: str | None = None,
    figsize: tuple[int, int] | None = None,
    show: bool = True,
    coastline_path: str | None = None,
    east_lim=None,
    north_lim=None,
    vmin=None,
    vmax=None,
):
    if coords_cfg is None:
        coords_cfg = {}
    map_cfg = dict(map_settings or {})
    columns = coords_cfg.get("columns", {})
    output_crs = coords_cfg.get("output_crs", "EPSG:3006")
    active_crs = map_cfg.get("projection") or coords_cfg.get("active_crs") or output_crs
    sweref_mode = active_crs == output_crs

    cmap_name = cmap or map_cfg.get("colormap") or "viridis"
    use_basemap = bool(map_cfg.get("use_basemap", True))
    basemap_source = map_cfg.get("basemap_source", "OpenStreetMap.Mapnik")
    show_colorbar = bool(map_cfg.get("show_colorbar", True))
    hex_edge_color = map_cfg.get("hex_edge_color", "none")
    hex_alpha = float(map_cfg.get("hex_alpha", 0.7))
    final_coastline = coastline_path or map_cfg.get("coastline_path")
    show_coastline = bool(map_cfg.get("show_coastline", True)) and bool(final_coastline)

    if figsize is None:
        default_size = map_cfg.get("figsize")
        if isinstance(default_size, (list, tuple)) and len(default_size) == 2:
            figsize = tuple(default_size)
        else:
            figsize = (12, 10)

    grouped = hex_data.copy()
    if grouped.empty:
        raise ValueError(f"No data to plot for {value_column}")

    fig, ax = plt.subplots(figsize=figsize)
    patches = []
    values = []
    transformer = None
    if sweref_mode:
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)

    for _, row in grouped.iterrows():
        hex_id = row.get("h3_hex") or row.get("hex_id")
        value = row[value_column]
        boundary = h3.cell_to_boundary(hex_id)
        lonlat_coords = [(lon, lat) for lat, lon in boundary]
        if sweref_mode and transformer is not None:
            coords = [transformer.transform(lon, lat) for lon, lat in lonlat_coords]
        else:
            coords = lonlat_coords
        polygon = mpatches.Polygon(coords, closed=True)
        patches.append(polygon)
        values.append(value)

    data_vmin = min(values) if vmin is None else float(vmin)
    data_vmax = max(values) if vmax is None else float(vmax)
    norm = Normalize(vmin=data_vmin, vmax=data_vmax)
    cmap_obj = plt.get_cmap(cmap_name)
    collection = PatchCollection(
        patches,
        cmap=cmap_obj,
        norm=norm,
        alpha=hex_alpha,
        edgecolor=hex_edge_color,
        linewidth=0,
    )
    collection.set_array(np.array(values))
    ax.add_collection(collection)

    all_coords = np.concatenate([p.get_path().vertices for p in patches])
    margin = 0.02
    if east_lim is not None:
        ax.set_xlim(east_lim)
    else:
        ax.set_xlim(all_coords[:, 0].min() - margin, all_coords[:, 0].max() + margin)
    if north_lim is not None:
        ax.set_ylim(north_lim)
    else:
        ax.set_ylim(all_coords[:, 1].min() - margin, all_coords[:, 1].max() + margin)

    if sweref_mode:
        ax.set_xlabel('Easting (SWEREF99 TM)')
        ax.set_ylabel('Northing (SWEREF99 TM)')
    else:
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')

    if use_basemap and CONTEXTILY_AVAILABLE:
        provider = _resolve_provider(basemap_source)
        if provider:
            try:
                ctx.add_basemap(ax, crs=active_crs, source=provider, attribution=False)
            except Exception as exc:
                print(f"Warning: Could not add basemap: {exc}")

    if show_coastline and final_coastline and os.path.exists(final_coastline):
        try:
            coast = gpd.read_file(final_coastline)
            target_crs = active_crs if active_crs else "EPSG:4326"
            coast = coast.to_crs(target_crs)
            coast.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=1, zorder=10)
        except Exception as exc:
            print(f"Warning: Could not plot coastline: {exc}")

    if show_colorbar:
        sm = ScalarMappable(cmap=cmap_obj, norm=norm)
        sm.set_array([])
        colorbar_orientation = map_cfg.get("colorbar_orientation", "horizontal")
        cbar_kwargs = {
            "ax": ax,
            "orientation": colorbar_orientation,
        }
        if colorbar_orientation.lower() == "horizontal":
            cbar_kwargs.update({"pad": 0.08, "fraction": 0.04, "shrink": 0.8})
            cbar_label_rotation = 0
        else:
            cbar_kwargs.update({"pad": 0.02, "fraction": 0.046})
            cbar_label_rotation = 270
        cbar = plt.colorbar(sm, **cbar_kwargs)
        cbar.set_label(value_column, rotation=cbar_label_rotation, labelpad=16)

    ax.set_title(title or f"Map of {value_column}")
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    plt.tight_layout()
    if show:
        plt.show()
    return fig
