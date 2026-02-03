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
        return data.assign(outlier=mask)
