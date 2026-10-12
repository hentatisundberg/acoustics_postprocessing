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
        self._encodings = ("utf-8", "utf-8-sig", "latin-1", "cp1252")
        self._timestamp_candidates = (
            "time",
            "timestamp",
            "datetime",
            "date",
            "utc_time",
            "local_time",
        )

    def get_file_list(self, root_dir: Path, pattern: str) -> List[Path]:
        files = sorted(f for f in Path(root_dir).glob(pattern) if not f.name.startswith("._"))
        if not files:
            logger.warning("No files found at %s with pattern %s", root_dir, pattern)
        return files

    def load_csv_files(
        self,
        file_paths: List[Path],
        lazy: bool = True,
        dtype: Optional[Dict[str, str]] = None,
        assume_missing: bool = True,
        blocksize: str | None = "64MB",
    ) -> dd.DataFrame | pd.DataFrame:
        if not file_paths:
            raise ValueError("No input files provided")
        # Determine separator based on file extension (simple heuristic)
        ext = file_paths[0].suffix.lower()
        sep = "\t" if ext in {".tsv", ".txt"} else ","

        if lazy:
            logger.info("Loading %d CSV files with Dask", len(file_paths))
            ddf = self._read_dask_csv([str(p) for p in file_paths], dtype, assume_missing, blocksize, sep)
            # Normalize column names to lowercase first, then apply mapping like {"time": "timestamp"}
            ddf = ddf.rename(columns={c: c.lower().strip() for c in ddf.columns})
            ddf = self._ensure_timestamp_column(ddf)
            if "timestamp" in ddf.columns:
                ddf["timestamp"] = self._normalize_timestamp_column(ddf["timestamp"])
            if self.column_map:
                ddf = ddf.rename(columns=self.column_map)
            return ddf
        else:
            logger.info("Loading %d CSV files eagerly with Pandas", len(file_paths))
            encoding = self._detect_encoding(file_paths[0], sep, dtype)
            parts = []
            for p in track(file_paths, description="Reading CSVs"):
                df = self._read_single_csv_with_encoding(p, dtype, sep, encoding)
                # Normalize columns and apply mapping
                df.columns = [c.lower().strip() for c in df.columns]
                df = self._ensure_timestamp_column(df)
                if "timestamp" in df.columns:
                    df["timestamp"] = self._normalize_timestamp_column(df["timestamp"])
                if self.column_map:
                    df.rename(columns=self.column_map, inplace=True)
                parts.append(df)
            df_all = pd.concat(parts, ignore_index=True)
            return df_all

    def _read_single_csv_with_encoding(
        self,
        path: Path,
        dtype: Optional[Dict[str, str]],
        sep: str,
        preferred_encoding: str,
    ) -> pd.DataFrame:
        last_exc: Exception | None = None
        for encoding in (preferred_encoding, *[e for e in self._encodings if e != preferred_encoding]):
            try:
                return pd.read_csv(path, dtype=dtype, sep=sep, encoding=encoding)
            except UnicodeDecodeError as exc:
                last_exc = exc
                logger.debug("Failed to decode %s with %s", path.name, encoding)
        raise last_exc or RuntimeError(
            f"Unable to decode {path} using encodings {', '.join(self._encodings)}"
        )

    def _detect_encoding(self, path: Path, sep: str, dtype: Optional[Dict[str, str]]) -> str:
        last_exc: Exception | None = None
        for encoding in self._encodings:
            try:
                pd.read_csv(path, nrows=5, dtype=dtype, sep=sep, encoding=encoding)
                return encoding
            except UnicodeDecodeError as exc:
                last_exc = exc
                logger.debug("Sampling %s failed to decode with %s", path.name, encoding)
        raise RuntimeError(
            f"Unable to decode {path} using encodings {', '.join(self._encodings)}"
        ) from last_exc

    def _read_dask_csv(
        self,
        paths: List[str],
        dtype: Optional[Dict[str, str]],
        assume_missing: bool,
        blocksize: str | None,
        sep: str,
    ) -> dd.DataFrame:
        last_exc: Exception | None = None
        for encoding in self._encodings:
            try:
                return dd.read_csv(
                    paths,
                    dtype=dtype,
                    parse_dates=None,
                    assume_missing=assume_missing,
                    blocksize=blocksize,
                    sep=sep,
                    encoding=encoding,
                )
            except UnicodeDecodeError as exc:
                last_exc = exc
                logger.debug("Dask failed to decode batch with %s", encoding)
        raise RuntimeError(
            f"Unable to decode CSV inputs using encodings {', '.join(self._encodings)}"
        ) from last_exc

    def _ensure_timestamp_column(self, df: dd.DataFrame | pd.DataFrame) -> dd.DataFrame | pd.DataFrame:
        """Ensure there is a single normalized timestamp column by merging known candidates."""
        candidates = [c for c in self._timestamp_candidates if c in df.columns]
        if not candidates and "timestamp" not in df.columns:
            return df

        if "timestamp" not in df.columns and candidates:
            first = candidates.pop(0)
            df = df.rename(columns={first: "timestamp"})
        else:
            candidates = [c for c in candidates if c != "timestamp"]

        for candidate in candidates:
            if candidate not in df.columns:
                continue
            df["timestamp"] = df["timestamp"].fillna(df[candidate])
            df = df.drop(columns=[candidate])
        return df

    def _normalize_timestamp_column(self, series: dd.Series | pd.Series) -> dd.Series | pd.Series:
        """Convert a timestamp series to UTC-naive datetimes."""
        if isinstance(series, dd.Series):
            ts = dd.to_datetime(series.astype(str), errors="coerce", utc=True)
            try:
                return ts.dt.tz_convert(None)
            except AttributeError:
                return ts
        ts = pd.to_datetime(series.astype(str), errors="coerce", utc=True)
        if ts.dt.tz is not None:
            ts = ts.dt.tz_convert(None)
        return ts
