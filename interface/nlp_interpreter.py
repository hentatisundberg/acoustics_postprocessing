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
            smooth = self._find_bool(raw, ["smooth"])  # optional
            show = self._find_bool(raw, ["show"])      # optional
            save = self._find_bool(raw, ["save"])      # optional
            out = self._find_param(raw, ["out", "file", "path"])  # optional
            base = {"y": y, "interval": interval, "smooth": smooth, "show": show, "save": save, "out": out}
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
            return {"task": "hex_map", "y": y, "resolution": res}

        # list available columns (especially for plotting)
        if re.match(r"^(\s*(show|list)\s+)?columns\b", s) and "=" not in s:
            return {"task": "list_columns"}

        if s.startswith("stats") or "statistics" in s:
            cols = self._find_list(raw, r"columns=([\w,]+)") or ["backscatter"]
            return {"task": "compute_stats", "columns": cols}

        if s in {"exit", "quit"}:
            return {"task": "exit"}

        if s in {"help", "?"}:
            return {"task": "help"}

        # default: attempt timeseries plot
        return {"task": "time_series_plot", "y": "backscatter", "interval": self._find_interval(s)}

    def validate_command(self, command: Dict[str, Any]) -> Tuple[bool, str | None]:
        task = command.get("task")
        if task in {"time_series_plot", "scatter_plot"}:
            if not command.get("y"):
                return False, "Missing y/column for plotting"
        if task == "aggregate_time" and not command.get("interval"):
            return False, "Missing interval"
        if task == "hex_map" and not command.get("y"):
            return False, "Missing value column for map"
        return True, None

    def _find_interval(self, s: str) -> str | None:
        m = re.search(r"(\d+min|\d+h|\d+d)", s)
        return m.group(1) if m else None

    def _find_param(self, raw: str, keys: list[str]) -> str | None:
        for k in keys:
            m = re.search(rf"{k}=([^\s]+)", raw, flags=re.IGNORECASE)
            if m:
                return m.group(1)
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
