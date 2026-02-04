from __future__ import annotations

from pathlib import Path
from typing import List, Union

import os
import sys
import matplotlib
# On macOS and Windows, a GUI backend is available without DISPLAY.
# Only force Agg on Linux when there's truly no display to avoid blank windows.
if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    try:
        matplotlib.use("Agg", force=True)
    except Exception:
        pass
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis.smoothing import DataSmoother
from pandas.api import types as ptypes


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
        smooth_method: str = "lowess",
        lowess_frac: float = 0.1,
        figsize: tuple[int, int] = (12, 5),
    ):
        fig, ax = plt.subplots(figsize=figsize)
        # Make scatter points clearly visible and distinct from any overlay line
        sns.scatterplot(
            data=data,
            x=x,
            y=y,
            hue=hue,
            ax=ax,
            s=40,
            alpha=0.7,
            edgecolor=None,
            zorder=3,
        )
        # Apply smoothing when requested
        if smooth:
            try:
                # Decide if x is datetime-like based on dtype rather than coercion success
                x_series = data[x]
                is_time_x = ptypes.is_datetime64_any_dtype(x_series) or (
                    x_series.dtype == object and pd.to_datetime(x_series, errors="coerce").notna().sum() >= 3
                )
                s = pd.to_numeric(data[y], errors="coerce")
                if is_time_x:
                    # Time-based LOESS using datetime index
                    x_dt = pd.to_datetime(x_series, errors="coerce")
                    if x_dt.notna().sum() >= 3 and smooth_method == "lowess":
                        s.index = x_dt
                        sm = self.smoother.apply_lowess(s, frac=lowess_frac)
                        ax.plot(
                            s.index,
                            sm,
                            color="black",
                            label="LOWESS",
                            zorder=5,
                            linewidth=2.0,
                            alpha=0.95,
                        )
                else:
                    # Numeric x smoothing for non-time axes
                    x_num = pd.to_numeric(x_series, errors="coerce")
                    valid = (~x_num.isna()) & (~s.isna())
                    if valid.sum() >= 3 and smooth_method == "lowess":
                        sm = self.smoother.apply_lowess_xy(x_num, s, frac=lowess_frac)
                        # Plot line over sorted x for a clean trend
                        df_line = pd.DataFrame({"x": x_num, "y": sm}).dropna()
                        df_line = df_line.sort_values("x")
                        ax.plot(
                            df_line["x"],
                            df_line["y"],
                            color="black",
                            label="LOWESS",
                            zorder=5,
                            linewidth=2.0,
                            alpha=0.95,
                        )
            except Exception:
                # If smoothing fails (e.g., weird dtype), proceed without overlay
                pass
        ax.legend()
        fig.tight_layout()
        return fig

    def plot_boxplot(
        self,
        data: pd.DataFrame,
        y_column: str,
        x_column: str | None = None,
        # x_column is used as grouping. If continuous, pre-bin in caller.
        title: str | None = None,
        ylabel: str | None = None,
        xlabel: str | None = None,
        figsize: tuple[int, int] = (10, 6),
        showfliers: bool = True,
        vert: bool = True,
        whis: float = 1.5,
    ):
        """Create a boxplot.

        If `x_column` is provided, produces grouped boxplots of `y_column` by `x_column`.
        If `x_column` is None, produces a single boxplot of `y_column`.
        """
        if y_column not in data.columns:
            raise ValueError(f"Column '{y_column}' not found")

        # Ensure numeric y
        y_series = pd.to_numeric(data[y_column], errors="coerce")
        if y_series.dropna().empty:
            raise ValueError(f"Column '{y_column}' has no numeric data to plot")

        fig, ax = plt.subplots(figsize=figsize)
        sns.set_style("whitegrid")

        if x_column:
            if x_column not in data.columns:
                raise ValueError(f"Grouping column '{x_column}' not found")
            # Use seaborn's grouped boxplot for categorical/grouped data
            sns.boxplot(
                data=data,
                x=x_column,
                y=y_column,
                ax=ax,
                showfliers=showfliers,
                whis=whis,
                orient="v" if vert else "h",
            )
            xlabel = xlabel or x_column
            ylabel = ylabel or y_column
            title = title or f"{y_column} by {x_column}"
            # Improve label readability for many categories
            ax.tick_params(axis="x", rotation=30)
        else:
            # Single boxplot
            ax.boxplot(
                [y_series.dropna()],
                showfliers=showfliers,
                whis=whis,
                vert=vert,
            )
            xlabel = xlabel or ""
            ylabel = ylabel or y_column
            title = title or f"Boxplot of {y_column}"

        ax.set_title(title)
        ax.set_xlabel(xlabel or "")
        ax.set_ylabel(ylabel or y_column)
        fig.tight_layout()
        return fig

    def save_plot(self, fig, output_path: Path, format: str = "png", close: bool = True) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path.with_suffix(f".{format}"), dpi=300)
        if close:
            plt.close(fig)
