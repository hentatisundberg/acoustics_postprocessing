from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

# For coordinate transformation
from pathlib import Path
import pyproj
from utils.io_helpers import read_config

logger = logging.getLogger(__name__)


class PositionMerger:
    def __init__(
        self,
        acoustic_time_col: str = "timestamp",
        position_time_col: str = "timestamp",
        lat_col: str = "latitude",
        lon_col: str = "longitude",
        config_path: str | Path = "config/settings.yaml",
    ):
        self.acoustic_time_col = acoustic_time_col
        self.position_time_col = position_time_col
        self.lat_col = lat_col
        self.lon_col = lon_col

        # Load coordinate config
        config = read_config(Path(config_path))
        coords_cfg = config.get("coordinates", {})
        self.input_crs = coords_cfg.get("input_crs", "EPSG:4326")
        self.output_crs = coords_cfg.get("output_crs", "EPSG:3006")
        self.transform_on_load = coords_cfg.get("transform_on_load", True)
        columns = coords_cfg.get("columns", {})
        self.input_lon_col = columns.get("input_lon", "longitude")
        self.input_lat_col = columns.get("input_lat", "latitude")
        self.output_easting_col = columns.get("output_easting", "easting")
        self.output_northing_col = columns.get("output_northing", "northing")
        self.keep_original = columns.get("keep_original", True)
        self.original_lon_suffix = columns.get("original_lon_suffix", "_wgs84")
        self.original_lat_suffix = columns.get("original_lat_suffix", "_wgs84")

        # Prepare transformer
        self._transformer = pyproj.Transformer.from_crs(self.input_crs, self.output_crs, always_xy=True)

    def _add_transformed_coords(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.transform_on_load:
            return df
        lon = df[self.input_lon_col]
        lat = df[self.input_lat_col]
        easting, northing = self._transformer.transform(lon.values, lat.values)
        df[self.output_easting_col] = easting
        df[self.output_northing_col] = northing
        if self.keep_original:
            # Optionally keep original lat/lon with suffix
            df[self.input_lon_col + self.original_lon_suffix] = lon
            df[self.input_lat_col + self.original_lat_suffix] = lat
        return df

    def merge_positions(
        self,
        acoustic_data: pd.DataFrame,
        position_data: pd.DataFrame,
        tolerance: str = "5s",
        direction: str = "nearest",
    ) -> pd.DataFrame:
        a = acoustic_data.copy()
        p = position_data.copy()
        a[self.acoustic_time_col] = pd.to_datetime(a[self.acoustic_time_col])
        p[self.position_time_col] = pd.to_datetime(p[self.position_time_col])
        a.sort_values(self.acoustic_time_col, inplace=True)
        p.sort_values(self.position_time_col, inplace=True)

        merged = pd.merge_asof(
            a,
            p[[self.position_time_col, self.lat_col, self.lon_col]],
            left_on=self.acoustic_time_col,
            right_on=self.position_time_col,
            tolerance=pd.Timedelta(tolerance),
            direction=direction,
        )
        # Only drop the right-side time column if it's distinct from the acoustic time column
        if self.position_time_col != self.acoustic_time_col and self.position_time_col in merged.columns:
            merged.drop(columns=[self.position_time_col], inplace=True)
        merged["position_matched"] = (~merged[self.lat_col].isna()) & (~merged[self.lon_col].isna())
        match_rate = merged["position_matched"].mean() * 100
        logger.info("Position match rate: %.2f%%", match_rate)
        # Add transformed coordinates if enabled
        merged = self._add_transformed_coords(merged)
        return merged

    def interpolate_positions(self, data: pd.DataFrame, method: str = "linear", limit: Optional[int] = None) -> pd.DataFrame:
        df = data.copy()
        df.sort_values(self.acoustic_time_col, inplace=True)
        for col in (self.lat_col, self.lon_col):
            df[col] = df[col].interpolate(method=method, limit=limit)
        return df

    def merge_positions_interpolated(
        self,
        acoustic_data: pd.DataFrame,
        position_data: pd.DataFrame,
        direction: str = "nearest",
    ) -> pd.DataFrame:
        """
        Assign positions to acoustic timestamps via linear interpolation between
        the nearest previous and next position points. Falls back to nearest when
        only one side is available.
        """
        a = acoustic_data.copy()
        p = position_data.copy()
        a[self.acoustic_time_col] = pd.to_datetime(a[self.acoustic_time_col])
        p[self.position_time_col] = pd.to_datetime(p[self.position_time_col])
        a.sort_values(self.acoustic_time_col, inplace=True)
        p.sort_values(self.position_time_col, inplace=True)

        # Build a union time index of acoustic and position timestamps
        base = a[[self.acoustic_time_col]].drop_duplicates().set_index(self.acoustic_time_col)
        pos_idx = p.set_index(self.position_time_col)[[self.lat_col, self.lon_col]].sort_index()
        union_index = base.index.union(pos_idx.index).unique().sort_values()
        timeline = pd.DataFrame(index=union_index)
        # Place known positions on the timeline
        timeline = timeline.join(pos_idx, how="left")
        # Time-based interpolation across the union timeline
        timeline[[self.lat_col, self.lon_col]] = timeline[[self.lat_col, self.lon_col]].interpolate(method="time")
        # Extract interpolated positions at acoustic timestamps
        interp_at_acoustic = timeline.loc[base.index]
        # Fallback: nearest position if interpolation left gaps (e.g., outside ends)
        if interp_at_acoustic[self.lat_col].isna().any() or interp_at_acoustic[self.lon_col].isna().any():
            nearest = pos_idx.reindex(base.index, method="nearest")
            interp_at_acoustic[self.lat_col] = interp_at_acoustic[self.lat_col].fillna(nearest[self.lat_col])
            interp_at_acoustic[self.lon_col] = interp_at_acoustic[self.lon_col].fillna(nearest[self.lon_col])

        out = a.merge(interp_at_acoustic.reset_index(), on=self.acoustic_time_col, how="left")
        out["position_matched"] = (~out[self.lat_col].isna()) & (~out[self.lon_col].isna())
        match_rate = out["position_matched"].mean() * 100
        logger.info("Position interpolation match rate: %.2f%%", match_rate)
        # Add transformed coordinates if enabled
        out = self._add_transformed_coords(out)
        return out
