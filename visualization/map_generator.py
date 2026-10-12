from __future__ import annotations

from pathlib import Path
from typing import Tuple

import folium
import pandas as pd
from matplotlib.colors import Normalize, to_hex
from matplotlib.cm import ScalarMappable, get_cmap

from aggregation.spatial_aggregator import SpatialAggregator
from utils.io_helpers import read_config


class HexagonalMapGenerator:
    def __init__(self, config: dict | None = None, config_path: str | Path = "config/settings.yaml"):
        config = config or read_config(Path(config_path))
        self.default_map_settings = dict(config.get("visualization", {}).get("map", {}))
        self.default_coords_cfg = config.get("coordinates", {})
        self.spatial = SpatialAggregator(coords_cfg=self.default_coords_cfg)

    def create_hexagon_map(
        self,
        hex_data: pd.DataFrame,
        value_column: str,
        center: Tuple[float, float] | None = None,
        coastline_path: str | None = None,
        map_settings: dict | None = None,
        coords_cfg: dict | None = None,
    ) -> folium.Map:
        effective_settings = dict(self.default_map_settings)
        if map_settings:
            effective_settings.update(map_settings)
        coords_cfg = coords_cfg or self.default_coords_cfg
        columns = coords_cfg.get("columns", {})
        lat_col = columns.get("input_lat", "latitude")
        lon_col = columns.get("input_lon", "longitude")
        tiles = effective_settings.get("background_map") or effective_settings.get("basemap_source") or "OpenStreetMap"
        zoom_val = effective_settings.get("folium_zoom_start") or effective_settings.get("basemap_zoom")
        zoom_start = None
        if isinstance(zoom_val, (int, float)):
            zoom_start = int(zoom_val)
        elif isinstance(zoom_val, str) and zoom_val.isdigit():
            zoom_start = int(zoom_val)
        computed_center = center
        lat_series = hex_data.get(lat_col)
        lon_series = hex_data.get(lon_col)
        if computed_center is None and lat_series is not None and lon_series is not None:
            try:
                computed_center = (float(lat_series.mean()), float(lon_series.mean()))
            except Exception:
                computed_center = None
        if computed_center is None:
            computed_center = (0.0, 0.0)
        map_kwargs = {"location": computed_center, "tiles": tiles}
        if zoom_start is not None:
            map_kwargs["zoom_start"] = zoom_start

        cmap_name = effective_settings.get("colormap") or "viridis"
        entries = []
        polygons = []
        for _, row in hex_data.iterrows():
            hex_id = row.get("h3_hex")
            if not hex_id:
                continue
            poly = self.spatial._hex_to_polygon(hex_id)  # noqa: SLF001
            polygons.append(poly)
            coords = [(lat, lon) for lon, lat in poly.exterior.coords]
            entries.append((hex_id, coords, row.get(value_column)))
        bounds = None
        centroid = None
        if polygons:
            min_lon = min(poly.bounds[0] for poly in polygons)
            min_lat = min(poly.bounds[1] for poly in polygons)
            max_lon = max(poly.bounds[2] for poly in polygons)
            max_lat = max(poly.bounds[3] for poly in polygons)
            bounds = [[min_lat, min_lon], [max_lat, max_lon]]
            centroid_lat = sum(poly.centroid.y for poly in polygons) / len(polygons)
            centroid_lon = sum(poly.centroid.x for poly in polygons) / len(polygons)
            centroid = (centroid_lat, centroid_lon)
            if center is None:
                map_kwargs["location"] = centroid
        m = folium.Map(**map_kwargs)
        values = [value for _, _, value in entries if isinstance(value, (int, float)) and pd.notna(value)]
        sm = None
        if values:
            vmin = min(values)
            vmax = max(values)
            if vmin == vmax:
                vmax = vmin + 1
            norm = Normalize(vmin=vmin, vmax=vmax)
            cmap = get_cmap(cmap_name)
            sm = ScalarMappable(norm=norm, cmap=cmap)
        fill_color_default = effective_settings.get("folium_hex_fill_color", "#3186cc")
        edge_color = effective_settings.get("hex_edge_color", "black")
        fill_opacity = float(effective_settings.get("folium_hex_fill_opacity", 0.6))
        stroke_opacity = float(effective_settings.get("folium_hex_opacity", 0.3))
        edge_weight = float(effective_settings.get("folium_hex_edge_weight", 1))
        for hex_id, coords, value in entries:
            fill_color = fill_color_default
            if sm and isinstance(value, (int, float)) and pd.notna(value):
                fill_color = to_hex(sm.to_rgba(value))
            folium.Polygon(
                locations=coords,
                fill=True,
                fill_color=fill_color,
                color=edge_color,
                weight=edge_weight,
                fill_opacity=fill_opacity,
                opacity=stroke_opacity,
                tooltip=f"{hex_id}\n{value_column}: {value}",
            ).add_to(m)
        if bounds:
            m.fit_bounds(bounds)

        show_coastline = effective_settings.get("show_coastline", True)
        coastline = coastline_path or effective_settings.get("coastline_path")
        if show_coastline and coastline and Path(coastline).exists():
            try:
                folium.GeoJson(
                    coastline,
                    name="Coastline",
                    style_function=lambda _: {"color": "black", "weight": 2, "fillOpacity": 0},
                ).add_to(m)
            except Exception as exc:
                print(f"Warning: Could not add coastline overlay: {exc}")
        return m

    def show_map(self, map_obj: folium.Map):
        import webbrowser, tempfile

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            map_obj.save(f.name)
            webbrowser.open(f.name)

    def save_map(self, map_obj: folium.Map, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        map_obj.save(str(output_path.with_suffix(".html")))
