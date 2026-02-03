from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import dask.dataframe as dd
import pandas as pd
from rich.progress import track

logger = logging.getLogger(__name__)


class AcousticsDataLoader:
    def __init__(self, column_map: Optional[Dict[str, str]] = None, timestamp_col: str = "timestamp"):
        self.column_map = column_map or {}
        self.timestamp_col = timestamp_col

    def get_file_list(self, root_dir: Path, pattern: str) -> List[Path]:
        files = sorted(Path(root_dir).glob(pattern))
        if not files:
            logger.warning("No files found at %s with pattern %s", root_dir, pattern)
        return files

    def load_csv_files(
        self,
        file_paths: List[Path],
        lazy: bool = True,
        dtype: Optional[Dict[str, str]] = None,
        parse_dates: Optional[List[str]] = None,
        assume_missing: bool = True,
        blocksize: str | None = "64MB",
    ) -> dd.DataFrame | pd.DataFrame:
        if not file_paths:
            raise ValueError("No input files provided")
        # Determine separator based on file extension (simple heuristic)
        ext = file_paths[0].suffix.lower()
        sep = "\t" if ext in {".tsv", ".txt"} else ","

        # Inspect first file header to resolve actual timestamp column case-insensitively
        try:
            header_df = pd.read_csv(file_paths[0], nrows=0, sep=sep)
            col_lut = {c.lower().strip(): c for c in header_df.columns}
            ts_key = next((k for k in ("time", "timestamp", "datetime", "date") if k in col_lut), None)
            resolved_ts_col = col_lut[ts_key] if ts_key else None
        except Exception:
            resolved_ts_col = None

        # Prefer detected timestamp column for parse_dates; fallback to provided/self
        if parse_dates is None:
            if resolved_ts_col is not None:
                parse_dates = [resolved_ts_col]
            else:
                # Avoid failing parse if the guessed column isn't present; we'll parse later
                parse_dates = []

        if lazy:
            logger.info("Loading %d CSV files with Dask", len(file_paths))
            ddf = dd.read_csv(
                [str(p) for p in file_paths],
                dtype=dtype,
                parse_dates=parse_dates,
                assume_missing=assume_missing,
                blocksize=blocksize,
                sep=sep,
            )
            # Normalize column names to lowercase first, then apply mapping like {"time": "timestamp"}
            ddf = ddf.rename(columns={c: c.lower().strip() for c in ddf.columns})
            if self.column_map:
                ddf = ddf.rename(columns=self.column_map)
            # Ensure timestamp column is datetime if present
            if "timestamp" in ddf.columns:
                ddf["timestamp"] = dd.to_datetime(ddf["timestamp"], errors="coerce")
            return ddf
        else:
            logger.info("Loading %d CSV files eagerly with Pandas", len(file_paths))
            parts = []
            for p in track(file_paths, description="Reading CSVs"):
                df = pd.read_csv(p, dtype=dtype, parse_dates=parse_dates, sep=sep)
                # Normalize columns and apply mapping
                df.columns = [c.lower().strip() for c in df.columns]
                if self.column_map:
                    df.rename(columns=self.column_map, inplace=True)
                parts.append(df)
            df_all = pd.concat(parts, ignore_index=True)
            # If timestamp exists, ensure datetime dtype
            if "timestamp" in df_all.columns:
                df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], errors="coerce")
            return df_all
