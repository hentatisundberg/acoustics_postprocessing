from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

try:
    import geopandas as gpd  # type: ignore
except Exception:  # noqa: BLE001
    gpd = None  # type: ignore

from shapely.geometry import Polygon
import h3


from pathlib import Path
from utils.io_helpers import read_config

class SpatialAggregator:
    def __init__(self, lat_col: Optional[str] = None, lon_col: Optional[str] = None, config_path: str | Path = "config/settings.yaml"):
        # Load config for CRS/column selection
        config = read_config(Path(config_path))
        coords_cfg = config.get("coordinates", {})
        columns = coords_cfg.get("columns", {})
        self.sweref_mode = coords_cfg.get("output_crs", "EPSG:3006") == coords_cfg.get("active_crs", coords_cfg.get("output_crs", "EPSG:3006"))
        # Use easting/northing if SWEREF99 is active, else lat/lon
        self.lat_col = lat_col or (columns.get("output_northing") if self.sweref_mode else columns.get("input_lat", "latitude"))
        self.lon_col = lon_col or (columns.get("output_easting") if self.sweref_mode else columns.get("input_lon", "longitude"))
        # For legacy code, also keep WGS84 columns
        self.wgs84_lat_col = columns.get("input_lat", "latitude")
        self.wgs84_lon_col = columns.get("input_lon", "longitude")

    def assign_hex_ids(self, data: pd.DataFrame, resolution: int) -> pd.DataFrame:
        df = data.copy()
        # If using SWEREF99, transform to WGS84 for H3 assignment
        if self.sweref_mode and self.wgs84_lat_col in df.columns and self.wgs84_lon_col in df.columns:
            lat_col = self.wgs84_lat_col
            lon_col = self.wgs84_lon_col
        else:
            lat_col = self.lat_col
            lon_col = self.lon_col
        use_latlng_to_cell = hasattr(h3, "latlng_to_cell")
        df["h3_hex"] = [
            (
                (h3.latlng_to_cell(lat, lon, resolution) if use_latlng_to_cell else h3.geo_to_h3(lat, lon, resolution))
                if pd.notna(lat) and pd.notna(lon)
                else None
            )
            for lat, lon in zip(df[lat_col], df[lon_col])
        ]
        return df

    def aggregate_by_hex(self, data: pd.DataFrame, agg_func: Dict[str, str]) -> pd.DataFrame:
        if "h3_hex" not in data.columns:
            raise ValueError("Data must contain 'h3_hex' column. Call assign_hex_ids first.")
        agg_df = data.dropna(subset=["h3_hex"]).groupby("h3_hex").agg(agg_func).reset_index()
        return agg_df

    def _hex_to_polygon(self, hex_id: str) -> Polygon:
        # Support both h3-py v3 (cell_to_boundary) and legacy (h3_to_geo_boundary)
        if hasattr(h3, "cell_to_boundary"):
            boundary = h3.cell_to_boundary(hex_id)
        else:
            boundary = h3.h3_to_geo_boundary(hex_id)
        # h3 returns (lat, lon); shapely expects (lon, lat)
        coords = [(lon, lat) for lat, lon in boundary] + [(boundary[0][1], boundary[0][0])]
        return Polygon(coords)

    def to_geodataframe(self, hex_data: pd.DataFrame) -> pd.DataFrame:
        polys = [self._hex_to_polygon(h) for h in hex_data["h3_hex"]]
        if gpd is not None:
            # Always use WGS84 for geometry
            return gpd.GeoDataFrame(hex_data.copy(), geometry=polys, crs="EPSG:4326")
        # Fallback: return WKT in a pandas DataFrame
        out = hex_data.copy()
        out["geometry_wkt"] = [p.wkt for p in polys]
        return out

    def get_hex_statistics(self, hex_data: pd.DataFrame) -> pd.DataFrame:
        stats = hex_data.copy()
        stats["sample_size"] = stats.get("count", pd.Series([None] * len(stats)))
        return stats
