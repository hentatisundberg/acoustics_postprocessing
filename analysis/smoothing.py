from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from scipy.interpolate import UnivariateSpline
from scipy.signal import savgol_filter

try:
    from statsmodels.nonparametric.smoothers_lowess import lowess  # type: ignore
except Exception:  # noqa: BLE001
    lowess = None  # type: ignore


class DataSmoother:
    def apply_lowess(self, data: pd.Series, frac: float = 0.1) -> pd.Series:
        """LOWESS smoothing that respects the time or numeric index.

        - If the Series index is datetime-like, use epoch seconds as x.
        - If the index is numeric, use the index values as x.
        - Otherwise, fall back to positional index.
        Inputs are sorted by x before smoothing, then restored to original order.
        """
        if lowess is None:
            raise ImportError("statsmodels is required for LOWESS smoothing")

        y = data.to_numpy()
        idx = data.index

        # Build numeric x from index
        try:
            if np.issubdtype(idx.dtype, np.datetime64):
                # Convert nanosecond timestamps to seconds
                x_full = idx.view("int64").astype(float) / 1e9
            else:
                # Try numeric conversion of index
                x_full = pd.to_numeric(idx, errors="coerce").to_numpy(dtype=float)
        except Exception:
            # Fallback to positional index
            x_full = np.arange(len(data), dtype=float)

        # Valid points require both y and x to be non-NaN
        mask = (~np.isnan(y)) & (~np.isnan(x_full))
        if mask.sum() < 5:
            # Not enough points to smooth; return original
            return data.copy()

        x = x_full[mask]
        y_masked = y[mask]

        # Sort by x to satisfy LOWESS expectations
        order = np.argsort(x)
        x_sorted = x[order]
        y_sorted = y_masked[order]

        # Apply LOWESS; returns y-estimates aligned to input order
        sm_sorted = lowess(y_sorted, x_sorted, frac=frac, return_sorted=False)

        # Restore to original masked order
        sm_unsorted = np.empty_like(y_masked, dtype=float)
        sm_unsorted[order] = sm_sorted

        # Map back to full length Series
        out = np.full_like(y, np.nan, dtype=float)
        out[mask] = sm_unsorted
        return pd.Series(out, index=idx)

    def apply_lowess_xy(self, x: pd.Series, y: pd.Series, frac: float = 0.1) -> pd.Series:
        """LOWESS on explicit numeric x and y.

        - Converts x to numeric, drops NaNs jointly with y.
        - Sorts by x before smoothing; restores to original index order.
        Returns a Series aligned to y.index (with NaNs where x/y invalid).
        """
        if lowess is None:
            raise ImportError("statsmodels is required for LOWESS smoothing")
        x_num = pd.to_numeric(x, errors="coerce")
        y_arr = pd.to_numeric(y, errors="coerce")
        mask = (~x_num.isna()) & (~y_arr.isna())
        if mask.sum() < 5:
            return y.copy()
        xv = x_num[mask].to_numpy(dtype=float)
        yv = y_arr[mask].to_numpy(dtype=float)
        order = np.argsort(xv)
        xs = xv[order]
        ys = yv[order]
        sm_sorted = lowess(ys, xs, frac=frac, return_sorted=False)
        sm_unsorted = np.empty_like(yv, dtype=float)
        sm_unsorted[order] = sm_sorted
        out = np.full(len(y_arr), np.nan, dtype=float)
        out[np.flatnonzero(mask)] = sm_unsorted
        return pd.Series(out, index=y.index)

    def apply_savgol(self, data: pd.Series, window: int, polyorder: int) -> pd.Series:
        y = data.to_numpy()
        # Ensure window is odd and <= len(non-nan)
        non_nan = np.count_nonzero(~np.isnan(y))
        w = min(window if window % 2 == 1 else window + 1, non_nan - (non_nan + 1) % 2)
        if w < 3:
            return data.copy()
        # Fill nans via interpolation for filtering
        s = pd.Series(y).interpolate().fillna(method="bfill").fillna(method="ffill").to_numpy()
        sm = savgol_filter(s, window_length=w, polyorder=polyorder)
        return pd.Series(sm, index=data.index)

    def apply_rolling_average(self, data: pd.Series, window: str) -> pd.Series:
        return data.rolling(window).mean()

    def fit_spline(self, x: pd.Series, y: pd.Series, smoothing: float | None = None) -> Callable[[np.ndarray], np.ndarray]:
        mask = ~y.isna()
        spline = UnivariateSpline(x[mask].to_numpy(), y[mask].to_numpy(), s=smoothing)
        return lambda xi: spline(xi)
