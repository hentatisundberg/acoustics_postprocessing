from __future__ import annotations

from typing import Dict

import pandas as pd

try:
    import geopandas as gpd  # type: ignore
except Exception:  # noqa: BLE001
    gpd = None  # type: ignore

from shapely.geometry import Polygon
import h3


class SpatialAggregator:
    def __init__(self, lat_col: str = "latitude", lon_col: str = "longitude"):
        self.lat_col = lat_col
        self.lon_col = lon_col

    def assign_hex_ids(self, data: pd.DataFrame, resolution: int) -> pd.DataFrame:
        df = data.copy()
        df["h3_hex"] = [
            h3.geo_to_h3(lat, lon, resolution) if pd.notna(lat) and pd.notna(lon) else None
            for lat, lon in zip(df[self.lat_col], df[self.lon_col])
        ]
        return df

    def aggregate_by_hex(self, data: pd.DataFrame, agg_func: Dict[str, str]) -> pd.DataFrame:
        if "h3_hex" not in data.columns:
            raise ValueError("Data must contain 'h3_hex' column. Call assign_hex_ids first.")
        agg_df = data.dropna(subset=["h3_hex"]).groupby("h3_hex").agg(agg_func).reset_index()
        return agg_df

    def _hex_to_polygon(self, hex_id: str) -> Polygon:
        boundary = h3.h3_to_geo_boundary(hex_id)
        # h3 returns (lat, lon); shapely expects (lon, lat)
        coords = [(lon, lat) for lat, lon in boundary] + [(boundary[0][1], boundary[0][0])]
        return Polygon(coords)

    def to_geodataframe(self, hex_data: pd.DataFrame) -> pd.DataFrame:
        polys = [self._hex_to_polygon(h) for h in hex_data["h3_hex"]]
        if gpd is not None:
            return gpd.GeoDataFrame(hex_data.copy(), geometry=polys, crs="EPSG:4326")
        # Fallback: return WKT in a pandas DataFrame
        out = hex_data.copy()
        out["geometry_wkt"] = [p.wkt for p in polys]
        return out

    def get_hex_statistics(self, hex_data: pd.DataFrame) -> pd.DataFrame:
        stats = hex_data.copy()
        stats["sample_size"] = stats.get("count", pd.Series([None] * len(stats)))
        return stats
