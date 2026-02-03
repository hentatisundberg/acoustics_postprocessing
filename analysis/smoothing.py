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
        if lowess is None:
            raise ImportError("statsmodels is required for LOWESS smoothing")
        x = np.arange(len(data))
        y = data.to_numpy()
        mask = ~np.isnan(y)
        sm = lowess(y[mask], x[mask], frac=frac, return_sorted=False)
        out = np.full_like(y, np.nan, dtype=float)
        out[mask] = sm
        return pd.Series(out, index=data.index)

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
