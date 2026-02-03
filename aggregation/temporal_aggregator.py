from __future__ import annotations

from typing import Dict

import pandas as pd


class TemporalAggregator:
    def __init__(self, timestamp_col: str = "timestamp"):
        self.timestamp_col = timestamp_col

    def aggregate_by_time(self, data: pd.DataFrame, interval: str, agg_func: Dict[str, str]) -> pd.DataFrame:
        df = data.copy()
        df[self.timestamp_col] = pd.to_datetime(df[self.timestamp_col])
        df.set_index(self.timestamp_col, inplace=True)
        agg_df = df.resample(interval).agg(agg_func)
        agg_df.reset_index(inplace=True)
        return agg_df

    def apply_rolling_window(self, data: pd.DataFrame, window: str, agg: str = "mean") -> pd.DataFrame:
        df = data.copy()
        df[self.timestamp_col] = pd.to_datetime(df[self.timestamp_col])
        df.set_index(self.timestamp_col, inplace=True)
        rolled = getattr(df.rolling(window), agg)()
        rolled.reset_index(inplace=True)
        return rolled
