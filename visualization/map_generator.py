from __future__ import annotations

from pathlib import Path
from typing import Tuple

import folium
import pandas as pd

from aggregation.spatial_aggregator import SpatialAggregator


class HexagonalMapGenerator:
    def __init__(self):
        self.spatial = SpatialAggregator()

    def create_hexagon_map(
        self, hex_data: pd.DataFrame, value_column: str, center: Tuple[float, float] | None = None
    ) -> folium.Map:
        if center is None:
            # center on mean of centroids from hex geometries
            center = (
                float(hex_data.get("latitude", pd.Series([0.0])).mean()),
                float(hex_data.get("longitude", pd.Series([0.0])).mean()),
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
        return m

    def save_map(self, map_obj: folium.Map, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        map_obj.save(str(output_path.with_suffix(".html")))
