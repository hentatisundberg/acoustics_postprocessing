from __future__ import annotations

from pathlib import Path
from typing import Tuple

import folium
import pandas as pd

from aggregation.spatial_aggregator import SpatialAggregator


from utils.io_helpers import read_config
from pathlib import Path

class HexagonalMapGenerator:
    def __init__(self, config_path: str | Path = "config/settings.yaml"):
        self.spatial = SpatialAggregator(config_path=config_path)
        config = read_config(Path(config_path))
        coords_cfg = config.get("coordinates", {})
        columns = coords_cfg.get("columns", {})
        self.sweref_mode = coords_cfg.get("output_crs", "EPSG:3006") == coords_cfg.get("active_crs", coords_cfg.get("output_crs", "EPSG:3006"))
        self.easting_col = columns.get("output_easting", "easting")
        self.northing_col = columns.get("output_northing", "northing")
        self.lat_col = columns.get("input_lat", "latitude")
        self.lon_col = columns.get("input_lon", "longitude")

    def create_hexagon_map(
        self, hex_data: pd.DataFrame, value_column: str, center: Tuple[float, float] | None = None, coastline_path: str | None = None
    ) -> folium.Map:
        if center is None:
            if self.sweref_mode and self.easting_col in hex_data.columns and self.northing_col in hex_data.columns:
                # Center on mean of easting/northing, but folium expects lat/lon, so fallback to WGS84
                center = (
                    float(hex_data.get(self.lat_col, pd.Series([0.0])).mean()),
                    float(hex_data.get(self.lon_col, pd.Series([0.0])).mean()),
                )
            else:
                center = (
                    float(hex_data.get(self.lat_col, pd.Series([0.0])).mean()),
                    float(hex_data.get(self.lon_col, pd.Series([0.0])).mean()),
                )
        m = folium.Map(location=center, zoom_start=7, tiles="OpenStreetMap")

        for _, row in hex_data.iterrows():
            poly = self.spatial._hex_to_polygon(row["h3_hex"])  # noqa: SLF001
            folium.Polygon(
                locations=[(lat, lon) for lon, lat in poly.exterior.coords],
                fill=True,
                color=None,
                fill_opacity=0.6,
                opacity=0.3,
                tooltip=f"{row['h3_hex']}\n{value_column}: {row[value_column]}",
            ).add_to(m)

        # Add Sweden coastline overlay if provided
        if coastline_path is not None and Path(coastline_path).exists():
            try:
                folium.GeoJson(coastline_path, name="Sweden Coastline", style_function=lambda x: {"color": "black", "weight": 2, "fillOpacity": 0}).add_to(m)
            except Exception as e:
                print(f"Warning: Could not add Sweden coastline overlay: {e}")
        return m

    def show_map(self, map_obj: folium.Map):
        # Save to a temporary file and open in browser
        import webbrowser, tempfile
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            map_obj.save(f.name)
            webbrowser.open(f.name)

    def save_map(self, map_obj: folium.Map, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        map_obj.save(str(output_path.with_suffix(".html")))
