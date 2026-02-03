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
        parse_dates = parse_dates or [self.timestamp_col]

        if lazy:
            logger.info("Loading %d CSV files with Dask", len(file_paths))
            ddf = dd.read_csv(
                [str(p) for p in file_paths],
                dtype=dtype,
                parse_dates=parse_dates,
                assume_missing=assume_missing,
                blocksize=blocksize,
            )
            ddf = ddf.rename(columns=self.column_map)
            return ddf
        else:
            logger.info("Loading %d CSV files eagerly with Pandas", len(file_paths))
            parts = []
            for p in track(file_paths, description="Reading CSVs"):
                df = pd.read_csv(p, dtype=dtype, parse_dates=parse_dates)
                parts.append(df)
            df_all = pd.concat(parts, ignore_index=True)
            df_all.rename(columns=self.column_map, inplace=True)
            return df_all
