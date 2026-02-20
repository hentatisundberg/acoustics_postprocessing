from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class ParseResult:
    ok: bool
    command: Dict[str, Any]
    error: str | None = None


class CommandInterpreter:
    """Simple rule-based interpreter with lightweight natural language parsing.

    Examples:
    - "load data from ./data pattern=*.csv positions=positions.csv"
    - "plot acoustic backscatter over time with 5min averages"
    - "map hex backscatter res=8"
    - "stats columns=backscatter,temperature"
    - "alias bs=backscatter temp=temp_water"  # define CLI variables
    """

    def parse_command(self, user_input: str) -> Dict[str, Any]:
        raw = user_input.strip()
        s = raw.lower()
        # Boxplot command
        if s.startswith("boxplot") or " boxplot" in s:
            # y: required, x/group: optional
            y = self._find_param(raw, ["y"])  # required unless using shorthand
            x = self._find_param(raw, ["x", "group"])  # optional
            # Shorthand: boxplot <column>
            if not y:
                m = re.match(r"boxplot\s+(\w+)", raw, flags=re.IGNORECASE)
                if m:
                    y = m.group(1)
            params: Dict[str, Any] = {"task": "plot_boxplot", "y": y}
            if x:
                params["x"] = x
            # Common params: dates and transforms
            params.update(self._extract_date_params(raw))
            params.update(self._extract_transform_params(raw))
            # Optional x-axis binning for continuous data: xbins (equal-width) or xqbins (quantile bins)
            xbins = self._find_param(raw, ["xbins", "x_bins"])  # supports xbins= or xbins:
            xqbins = self._find_param(raw, ["xqbins", "x_quantile_bins", "quantile_bins"])  # optional
            if xbins is not None:
                params["xbins"] = xbins
            if xqbins is not None:
                params["xqbins"] = xqbins
            # Optional show/save/out
            params["show"] = self._find_bool(raw, ["show"])  # may be None
            params["save"] = self._find_bool(raw, ["save"])  # may be None
            params["out"] = self._find_param(raw, ["out", "file", "path"])  # may be None
            return params
        # Scatter plotting can be invoked directly via 'scatter ...'
        if s.startswith("scatter"):
            interval = self._find_interval(s)
            y = self._find_param(raw, ["y", "column", "value", "backscatter"])  # optional
            x = self._find_param(raw, ["x"])  # optional
            # Support 'scatter y vs x' syntax
            vs_match = re.search(r"scatter\s+(\w+)\s+vs\s+(\w+)", raw, re.IGNORECASE)
            if vs_match:
                y = vs_match.group(1)
                x = vs_match.group(2)
            # Support 'scatter <y>' shorthand
            if not y:
                simple = re.match(r"scatter\s+(\w+)", raw, flags=re.IGNORECASE)
                if simple:
                    y = simple.group(1)
            if not x:
                x = "timestamp"
            # Parse smooth mode: supports true/false/loess
            smooth = self._find_param(raw, ["smooth"])  # optional, may be bool or string
            # Optional LOWESS fraction (0-1), e.g., frac=0.1 or lowess_frac=0.2
            lowess_frac = self._find_param(raw, ["frac", "lowess_frac"])  # optional
            show = self._find_bool(raw, ["show"])      # optional
            save = self._find_bool(raw, ["save"])      # optional
            out = self._find_param(raw, ["out", "file", "path"])  # optional
            base = {
                "task": "scatter_plot",
                "y": y,
                "x": x,
                "interval": interval,
                "smooth": smooth,
                "lowess_frac": lowess_frac,
                "show": show,
                "save": save,
                "out": out,
            }
            # Add date/transform params
            base.update(self._extract_date_params(raw))
            base.update(self._extract_transform_params(raw))
            return base
        # Settings
        if s.startswith("set "):
            # set key=value
            m = re.findall(r"(\w+)=([^\s]+)", raw, flags=re.IGNORECASE)
            return {"task": "set", "params": {k.lower(): v for k, v in m}}

        # Define CLI variable aliases: alias name=column [name=column ...]
        if s.startswith("alias ") or s.startswith("define "):
            pairs = re.findall(r"(\w+)=([^\s]+)", raw, flags=re.IGNORECASE)
            return {"task": "alias", "aliases": {k.lower(): v for k, v in pairs}}

        if s.startswith("load"):
            pairs = re.findall(r"(pattern|positions|dir)=([^\s]+)", raw, flags=re.IGNORECASE)
            params = {k.lower(): v for k, v in pairs}
            return {"task": "load", "params": params}

        if "plot" in s or s.startswith("plot"):
            interval = self._find_interval(s)
            y = self._find_param(raw, ["y", "column", "value", "backscatter"]) or "backscatter"
            x = self._find_param(raw, ["x"])
            # Support 'scatter y vs x' syntax
            if not x and "scatter" in s:
                vs_match = re.search(r'scatter\s+(\w+)\s+vs\s+(\w+)', raw, re.IGNORECASE)
                if vs_match:
                    y = vs_match.group(1)
                    x = vs_match.group(2)
            if not x:
                x = "timestamp"
            # Parse smooth mode as bool or string
            smooth = self._find_param(raw, ["smooth"])  # optional
            # Optional LOWESS fraction (0-1)
            lowess_frac = self._find_param(raw, ["frac", "lowess_frac"])  # optional
            show = self._find_bool(raw, ["show"])      # optional
            save = self._find_bool(raw, ["save"])      # optional
            out = self._find_param(raw, ["out", "file", "path"])  # optional
            base = {"y": y, "x": x, "interval": interval, "smooth": smooth, "lowess_frac": lowess_frac, "show": show, "save": save, "out": out}
            base.update(self._extract_date_params(raw))
            base.update(self._extract_transform_params(raw))
            if "scatter" in s:
                return {"task": "scatter_plot", **base}
            return {"task": "time_series_plot", **base}

        if "aggregate" in s and ("time" in s or re.search(r"\d+min|\d+h|\d+d", s)):
            interval = self._find_interval(s) or "5min"
            y = self._find_param(raw, ["y", "column", "value"])  # optional
            cmd: Dict[str, Any] = {"task": "aggregate_time", "interval": interval}
            if y:
                cmd["y"] = y
            return cmd

        if "map" in s or "hex" in s:
            y = self._find_param(raw, ["y", "value", "column", "backscatter"]) or "backscatter"
            res = self._find_int(s, r"res=(\d+)") or 8
            backend = None
            if "matplotlib" in s or "mpl" in s:
                backend = "matplotlib"
            elif "folium" in s or "html" in s:
                backend = "folium"
            coastline_path = self._find_param(raw, ["coastline", "coast", "shapefile", "geojson"])
            east_lim = self._find_range(raw, ["east_lim", "xlim"])  # optional
            north_lim = self._find_range(raw, ["north_lim", "ylim"])  # optional
            base = {"task": "hex_map", "y": y, "resolution": res, "backend": backend, "coastline_path": coastline_path, "east_lim": east_lim, "north_lim": north_lim}
            base.update(self._extract_date_params(raw))
            base.update(self._extract_transform_params(raw))
            return base

        # Create calculated variable: "create var hour=timestamp.dt.hour" or "calc depth_m=depth/1000"
        if s.startswith("create") or s.startswith("calc"):
            # Pattern 1: "create var <name>=<expression>" or "calc <name>=<expression>"
            m = re.search(r"(?:create\s+var\s+|calc\s+)(\w+)=(.+)", raw, flags=re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                expression = m.group(2).strip()
                return {"task": "create_variable", "name": name, "expression": expression}
            
            # Pattern 2: "create hour from timestamp" (temporal extraction shorthand)
            m2 = re.search(r"create\s+(\w+)\s+from\s+(\w+)", raw, flags=re.IGNORECASE)
            if m2:
                attr_name = m2.group(1).strip().lower()
                col_name = m2.group(2).strip()
                # Map common temporal attributes
                temporal_attrs = {
                    "hour": "hour", "day": "day", "month": "month", "year": "year",
                    "dayofweek": "dayofweek", "weekday": "dayofweek",
                    "dayofyear": "dayofyear", "week": "isocalendar().week",
                    "quarter": "quarter", "date": "date"
                }
                if attr_name in temporal_attrs:
                    expression = f"{col_name}.dt.{temporal_attrs[attr_name]}"
                    return {"task": "create_variable", "name": attr_name, "expression": expression}

        # list available columns (especially for plotting)
        if re.match(r"^(\s*(show|list)\s+)?columns\b", s) and "=" not in s:
            return {"task": "list_columns"}

        # Statistics: check for time-aggregated stats first
        if s.startswith("stats") or "statistics" in s:
            # Check for "by time" or time interval pattern
            interval = self._find_interval(s)
            if interval or " by time" in s or "by_time" in s:
                # Time-aggregated stats
                cols = self._find_list(raw, r"columns=([\w,]+)") or ["backscatter"]
                base = {"task": "compute_stats_by_time", "columns": cols, "interval": interval or "5min"}
                base.update(self._extract_date_params(raw))
                base.update(self._extract_transform_params(raw))
                return base
            else:
                # Regular stats (no time aggregation)
                cols = self._find_list(raw, r"columns=([\w,]+)") or ["backscatter"]
                return {"task": "compute_stats", "columns": cols}

        if s in {"exit", "quit"}:
            return {"task": "exit"}

        if s in {"help", "?"}:
            return {"task": "help"}

        # default: show help (no implicit plotting)
        return {"task": "help"}

    def validate_command(self, command: Dict[str, Any]) -> Tuple[bool, str | None]:
        task = command.get("task")
        if task in {"time_series_plot", "scatter_plot"}:
            if not command.get("y"):
                return False, "Missing y/column for plotting"
        if task == "plot_boxplot":
            if not command.get("y"):
                return False, "Missing y for boxplot"
        if task == "aggregate_time" and not command.get("interval"):
            return False, "Missing interval"
        if task == "hex_map" and not command.get("y"):
            return False, "Missing value column for map"
        return True, None

    def _find_interval(self, s: str) -> str | None:
        m = re.search(r"(\d+min|\d+h|\d+d)", s)
        return m.group(1) if m else None

    def _find_param(self, raw: str, keys: list[str]) -> str | None:
        """Find a parameter value for any of the given keys.

        Supports both "key=value" and "key:value" syntaxes commonly used in the CLI.
        Returns the first match found, case-insensitive.
        """
        for k in keys:
            # Try equals syntax: key=value
            m = re.search(rf"{k}=([^\s]+)", raw, flags=re.IGNORECASE)
            if m:
                return m.group(1)
            # Try colon syntax: key:value
            m2 = re.search(rf"{k}:([^\s]+)", raw, flags=re.IGNORECASE)
            if m2:
                return m2.group(1)
        return None

    def _find_int(self, s: str, pattern: str) -> int | None:
        m = re.search(pattern, s)
        return int(m.group(1)) if m else None

    def _find_list(self, raw: str, pattern: str) -> list[str] | None:
        m = re.search(pattern, raw, flags=re.IGNORECASE)
        if not m:
            return None
        return [t.strip() for t in m.group(1).split(",") if t.strip()]

    def _find_bool(self, raw: str, keys: list[str]) -> bool | None:
        for k in keys:
            m = re.search(rf"{k}=([^\s]+)", raw, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip().lower()
                if val in {"1", "true", "yes", "y"}:
                    return True
                if val in {"0", "false", "no", "n"}:
                    return False
        return None

    def _find_range(self, raw: str, keys: list[str]) -> list[float] | None:
        """Parse a numeric range of two values, e.g., east_lim=[12,20] or east_lim=12,20."""
        for k in keys:
            # Try bracketed form [a,b]
            m = re.search(rf"{k}=\[([^\]]+)\]", raw, flags=re.IGNORECASE)
            if m:
                parts = [p.strip() for p in m.group(1).split(',') if p.strip()]
                try:
                    vals = [float(p) for p in parts]
                    if len(vals) == 2:
                        return vals
                except ValueError:
                    continue
            # Try simple comma-separated form a,b
            m2 = re.search(rf"{k}=([^\s]+)", raw, flags=re.IGNORECASE)
            if m2:
                text = m2.group(1)
                parts = [p.strip() for p in text.split(',') if p.strip()]
                try:
                    vals = [float(p) for p in parts]
                    if len(vals) == 2:
                        return vals
                except ValueError:
                    continue
        return None

    def _extract_date_params(self, input_string: str) -> Dict[str, str]:
        params: Dict[str, str] = {}
        # start_date=... (support quoted or unquoted)
        m = re.search(r"start_date=[\"']?([0-9\-\s:T+]+)[\"']?", input_string, flags=re.IGNORECASE)
        if m:
            params["start_date"] = m.group(1).strip("\"'")
        m2 = re.search(r"end_date=[\"']?([0-9\-\s:T+]+)[\"']?", input_string, flags=re.IGNORECASE)
        if m2:
            params["end_date"] = m2.group(1).strip("\"'")
        return params

    def _extract_transform_params(self, input_string: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        m = re.search(r"log=(true|false|yes|no|1|0)", input_string, flags=re.IGNORECASE)
        if m:
            val = m.group(1).lower()
            params["log"] = val in {"true", "yes", "1"}
        # Also support colon syntax for log
        m_colon = re.search(r"log:([^\s]+)", input_string, flags=re.IGNORECASE)
        if m_colon and "log" not in params:
            val = m_colon.group(1).lower()
            params["log"] = val in {"true", "yes", "1"}
        # Negative transform (alias: neg)
        m_neg = re.search(r"(negative|neg)=(true|false|yes|no|1|0)", input_string, flags=re.IGNORECASE)
        if m_neg:
            val = m_neg.group(2).lower()
            params["negative"] = val in {"true", "yes", "1"}
        m_neg_colon = re.search(r"(negative|neg):([^\s]+)", input_string, flags=re.IGNORECASE)
        if m_neg_colon and "negative" not in params:
            val = m_neg_colon.group(2).lower()
            params["negative"] = val in {"true", "yes", "1"}
        m2 = re.search(r"min=([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if m2:
            try:
                params["min"] = float(m2.group(1))
            except Exception:
                pass
        # Colon syntax for min
        m2c = re.search(r"min:([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if m2c and "min" not in params:
            try:
                params["min"] = float(m2c.group(1))
            except Exception:
                pass
        m3 = re.search(r"max=([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if m3:
            try:
                params["max"] = float(m3.group(1))
            except Exception:
                pass
        # Colon syntax for max
        m3c = re.search(r"max:([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if m3c and "max" not in params:
            try:
                params["max"] = float(m3c.group(1))
            except Exception:
                pass

        # X-axis specific transforms: xlog/xmin/xmax (also accept logx)
        mx = re.search(r"(xlog|logx)=(true|false|yes|no|1|0)", input_string, flags=re.IGNORECASE)
        if mx:
            val = mx.group(2).lower()
            params["xlog"] = val in {"true", "yes", "1"}
        mx_colon = re.search(r"(xlog|logx):([^\s]+)", input_string, flags=re.IGNORECASE)
        if mx_colon and "xlog" not in params:
            val = mx_colon.group(2).lower()
            params["xlog"] = val in {"true", "yes", "1"}
        xmin = re.search(r"xmin=([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if xmin:
            try:
                params["xmin"] = float(xmin.group(1))
            except Exception:
                pass
        xmin_c = re.search(r"xmin:([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if xmin_c and "xmin" not in params:
            try:
                params["xmin"] = float(xmin_c.group(1))
            except Exception:
                pass
        xmax = re.search(r"xmax=([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if xmax:
            try:
                params["xmax"] = float(xmax.group(1))
            except Exception:
                pass
        xmax_c = re.search(r"xmax:([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if xmax_c and "xmax" not in params:
            try:
                params["xmax"] = float(xmax_c.group(1))
            except Exception:
                pass
        
        # Outlier filtering parameters
        # outlier_method or outliers: zscore/iqr/percentile
        m_outlier = re.search(r"(outlier_method|outliers|outlier)=(zscore|iqr|percentile)", input_string, flags=re.IGNORECASE)
        if m_outlier:
            params["outlier_method"] = m_outlier.group(2).lower()
        m_outlier_colon = re.search(r"(outlier_method|outliers|outlier):([^\s]+)", input_string, flags=re.IGNORECASE)
        if m_outlier_colon and "outlier_method" not in params:
            val = m_outlier_colon.group(2).lower()
            if val in {"zscore", "iqr", "percentile"}:
                params["outlier_method"] = val
        
        # z_thresh: threshold for zscore method (default 3.0)
        m_zthresh = re.search(r"z_thresh=([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if m_zthresh:
            try:
                params["z_thresh"] = float(m_zthresh.group(1))
            except Exception:
                pass
        m_zthresh_c = re.search(r"z_thresh:([0-9.+-]+)", input_string, flags=re.IGNORECASE)
        if m_zthresh_c and "z_thresh" not in params:
            try:
                params["z_thresh"] = float(m_zthresh_c.group(1))
            except Exception:
                pass
        
        return params
