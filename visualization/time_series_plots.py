from __future__ import annotations

from pathlib import Path
from typing import List, Union

import os
import matplotlib
# Use a non-interactive backend when no display is available to avoid hangs
if not os.environ.get("DISPLAY"):
    try:
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis.smoothing import DataSmoother


class TimeSeriesPlotter:
    def __init__(self):
        sns.set(style="whitegrid")
        self.smoother = DataSmoother()

    def plot_line_series(
        self,
        data: pd.DataFrame,
        x: str,
        y: Union[str, List[str]],
        smooth: bool = True,
        smooth_method: str = "lowess",
        lowess_frac: float = 0.1,
        figsize: tuple[int, int] = (12, 5),
    ):
        y_cols = [y] if isinstance(y, str) else y
        fig, ax = plt.subplots(figsize=figsize)
        for col in y_cols:
            sns.lineplot(data=data, x=x, y=col, ax=ax, label=col)
            if smooth:
                s = pd.to_numeric(data[col], errors="coerce")
                s.index = pd.to_datetime(data[x])
                if smooth_method == "lowess":
                    sm = self.smoother.apply_lowess(s, frac=lowess_frac)
                elif smooth_method == "savgol":
                    sm = self.smoother.apply_savgol(s, window=11, polyorder=2)
                else:  # rolling
                    sm = self.smoother.apply_rolling_average(s, window="10T")
                ax.plot(s.index, sm, label=f"{col} (smoothed)")
        ax.legend()
        ax.set_xlabel(x)
        ax.set_ylabel(", ".join(y_cols))
        fig.tight_layout()
        return fig

    def plot_scatter(
        self,
        data: pd.DataFrame,
        x: str,
        y: str,
        hue: str | None = None,
        smooth: bool = True,
        figsize: tuple[int, int] = (12, 5),
    ):
        fig, ax = plt.subplots(figsize=figsize)
        sns.scatterplot(data=data, x=x, y=y, hue=hue, ax=ax)
        if smooth:
            s = pd.to_numeric(data[y], errors="coerce")
            s.index = pd.to_datetime(data[x])
            sm = self.smoother.apply_lowess(s, frac=0.1)
            ax.plot(s.index, sm, color="black", label="LOWESS")
        ax.legend()
        fig.tight_layout()
        return fig

    def save_plot(self, fig, output_path: Path, format: str = "png", close: bool = True) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path.with_suffix(f".{format}"), dpi=300)
        if close:
            plt.close(fig)
