from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class PositionMerger:
    def __init__(
        self,
        acoustic_time_col: str = "timestamp",
        position_time_col: str = "timestamp",
        lat_col: str = "latitude",
        lon_col: str = "longitude",
    ):
        self.acoustic_time_col = acoustic_time_col
        self.position_time_col = position_time_col
        self.lat_col = lat_col
        self.lon_col = lon_col

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
        merged.drop(columns=[self.position_time_col], inplace=True)
        merged["position_matched"] = (~merged[self.lat_col].isna()) & (~merged[self.lon_col].isna())
        match_rate = merged["position_matched"].mean() * 100
        logger.info("Position match rate: %.2f%%", match_rate)
        return merged

    def interpolate_positions(self, data: pd.DataFrame, method: str = "linear", limit: Optional[int] = None) -> pd.DataFrame:
        df = data.copy()
        df.sort_values(self.acoustic_time_col, inplace=True)
        for col in (self.lat_col, self.lon_col):
            df[col] = df[col].interpolate(method=method, limit=limit)
        return df
