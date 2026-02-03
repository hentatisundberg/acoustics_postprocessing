from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd


def validate_csv_schema(df: pd.DataFrame, required_columns: List[str]) -> bool:
    return all(col in df.columns for col in required_columns)


def validate_timestamps(df: pd.DataFrame, time_column: str) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    if time_column not in df.columns:
        errs.append(f"Missing time column: {time_column}")
        return False, errs
    if not np.issubdtype(df[time_column].dtype, np.datetime64):
        try:
            pd.to_datetime(df[time_column])
        except Exception:
            errs.append("Timestamp column is not parseable as datetime")
    if df[time_column].isna().any():
        errs.append("Timestamp column contains missing values")
    return len(errs) == 0, errs


def validate_coordinates(df: pd.DataFrame, lat_col: str, lon_col: str) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    for col in (lat_col, lon_col):
        if col not in df.columns:
            errs.append(f"Missing coordinate column: {col}")
    if errs:
        return False, errs
    lats = df[lat_col]
    lons = df[lon_col]
    invalid = (
        lats.isna() | lons.isna() | (lats < -90) | (lats > 90) | (lons < -180) | (lons > 180)
    )
    if invalid.any():
        errs.append("Found invalid lat/lon values")
    return len(errs) == 0, errs


def check_data_gaps(df: pd.DataFrame, time_column: str, expected_freq: str) -> pd.DataFrame:
    s = pd.Series(1, index=pd.to_datetime(df[time_column]).sort_values())
    full = s.resample(expected_freq).sum()
    gaps = full[full.isna()]
    return gaps.to_frame(name="missing").reset_index().rename(columns={"index": time_column})
