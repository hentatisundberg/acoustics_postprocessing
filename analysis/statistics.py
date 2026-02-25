from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd


class StatisticsCalculator:
    def calculate_descriptive_stats(self, data: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
        desc = {}
        for col in columns:
            s = pd.to_numeric(data[col], errors="coerce").dropna()
            if s.empty:
                continue
            q = s.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
            desc[col] = {
                "count": int(s.count()),
                "mean": float(s.mean()),
                "std": float(s.std(ddof=1)) if s.count() > 1 else np.nan,
                "min": float(s.min()),
                "p05": float(q.loc[0.05]),
                "p25": float(q.loc[0.25]),
                "median": float(q.loc[0.5]),
                "p75": float(q.loc[0.75]),
                "p95": float(q.loc[0.95]),
                "max": float(s.max()),
                "missing": int(data[col].isna().sum()),
            }
        return pd.DataFrame(desc).T.reset_index().rename(columns={"index": "variable"})

    def save_stats_to_file(self, stats: pd.DataFrame, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["Descriptive Statistics", "======================", ""]
        for _, row in stats.iterrows():
            lines.append(f"Variable: {row['variable']}")
            lines.append(
                (
                    f"count={row['count']} mean={row['mean']:.3f} std={row['std']:.3f} "
                    f"min={row['min']:.3f} p05={row['p05']:.3f} p25={row['p25']:.3f} "
                    f"median={row['median']:.3f} p75={row['p75']:.3f} p95={row['p95']:.3f} max={row['max']:.3f} "
                    f"missing={row['missing']}"
                )
            )
            lines.append("")
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def detect_outliers(self, data: pd.DataFrame, column: str, method: str = "iqr", z_thresh: float = 3.0) -> pd.DataFrame:
        s = pd.to_numeric(data[column], errors="coerce")
        mask = pd.Series([False] * len(s), index=s.index)
        if method == "iqr":
            q1, q3 = s.quantile([0.25, 0.75])
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            mask = (s < lower) | (s > upper)
        elif method == "zscore":
            z = (s - s.mean()) / s.std(ddof=0)
            mask = z.abs() > z_thresh
        elif method in {"modified_zscore", "modified-zscore", "mzscore"}:
            median = s.median()
            mad = (s - median).abs().median()
            if mad and not np.isnan(mad):
                modified_z = 0.6745 * (s - median) / mad
                mask = modified_z.abs() > z_thresh
        return data.assign(outlier=mask)

    def calculate_stats_by_time(self, data: pd.DataFrame, interval: str, columns: List[str], timestamp_col: str = "timestamp") -> pd.DataFrame:
        """Calculate descriptive statistics for each time bin.
        
        Returns a long-format DataFrame with columns:
        timestamp, variable, count, mean, std, min, p05, p25, median, p75, p95, max, missing
        
        Each row represents statistics for one variable in one time bin.
        """
        if timestamp_col not in data.columns:
            raise ValueError(f"Timestamp column '{timestamp_col}' not found in data")
        
        df = data.copy()
        # Ensure timestamp is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df[timestamp_col] = pd.to_datetime(df[timestamp_col], errors="coerce")
        
        # Set timestamp as index for resampling
        df = df.set_index(timestamp_col)
        
        # Collect stats for each time bin
        results = []
        
        for col in columns:
            if col not in df.columns:
                continue
            
            # Resample by interval and apply stats to each group
            resampled = df[col].resample(interval)
            
            for timestamp, group in resampled:
                s = pd.to_numeric(group, errors="coerce").dropna()
                if s.empty:
                    continue
                
                q = s.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
                
                results.append({
                    "timestamp": timestamp,
                    "variable": col,
                    "count": int(s.count()),
                    "mean": float(s.mean()),
                    "std": float(s.std(ddof=1)) if s.count() > 1 else np.nan,
                    "min": float(s.min()),
                    "p05": float(q.loc[0.05]),
                    "p25": float(q.loc[0.25]),
                    "median": float(q.loc[0.5]),
                    "p75": float(q.loc[0.75]),
                    "p95": float(q.loc[0.95]),
                    "max": float(s.max()),
                    "missing": int(group.isna().sum()),
                })
        
        return pd.DataFrame(results)

    def save_stats_by_time_to_file(self, stats: pd.DataFrame, output_path: Path) -> None:
        """Save time-aggregated stats in both CSV and readable text format."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as CSV for easy analysis
        csv_path = output_path.with_suffix(".csv")
        stats.to_csv(csv_path, index=False)
        
        # Also save as readable text
        lines = ["Descriptive Statistics by Time", "==============================", ""]
        
        # Group by timestamp for readability
        for timestamp, group in stats.groupby("timestamp"):
            lines.append(f"Time: {timestamp}")
            lines.append("-" * 50)
            for _, row in group.iterrows():
                lines.append(f"  Variable: {row['variable']}")
                lines.append(
                    f"    count={row['count']} mean={row['mean']:.3f} std={row['std']:.3f} "
                    f"min={row['min']:.3f} p05={row['p05']:.3f} p25={row['p25']:.3f} "
                    f"median={row['median']:.3f} p75={row['p75']:.3f} p95={row['p95']:.3f} "
                    f"max={row['max']:.3f} missing={row['missing']}"
                )
            lines.append("")
        
        output_path.write_text("\n".join(lines), encoding="utf-8")
