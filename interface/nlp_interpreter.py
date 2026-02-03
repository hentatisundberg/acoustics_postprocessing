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
    """

    def parse_command(self, user_input: str) -> Dict[str, Any]:
        s = user_input.strip().lower()
        # Settings
        if s.startswith("set "):
            # set key=value
            m = re.findall(r"(\w+)=([^\s]+)", s)
            return {"task": "set", "params": dict(m)}

        if s.startswith("load"):
            params = dict(re.findall(r"(pattern|positions|dir)=([^\s]+)", s))
            return {"task": "load", "params": params}

        if "plot" in s or s.startswith("plot"):
            interval = self._find_interval(s)
            y = self._find_param(s, ["y", "column", "value", "backscatter"]) or "backscatter"
            if "scatter" in s:
                return {"task": "scatter_plot", "y": y, "interval": interval}
            return {"task": "time_series_plot", "y": y, "interval": interval}

        if "aggregate" in s and ("time" in s or re.search(r"\d+min|\d+h", s)):
            interval = self._find_interval(s) or "5min"
            return {"task": "aggregate_time", "interval": interval}

        if "map" in s or "hex" in s:
            y = self._find_param(s, ["y", "value", "column", "backscatter"]) or "backscatter"
            res = self._find_int(s, r"res=(\d+)") or 8
            return {"task": "hex_map", "y": y, "resolution": res}

        if s.startswith("stats") or "statistics" in s:
            cols = self._find_list(s, r"columns=([\w,]+)") or ["backscatter"]
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

    def _find_param(self, s: str, keys: list[str]) -> str | None:
        for k in keys:
            m = re.search(rf"{k}=([^\s]+)", s)
            if m:
                return m.group(1)
        return None

    def _find_int(self, s: str, pattern: str) -> int | None:
        m = re.search(pattern, s)
        return int(m.group(1)) if m else None

    def _find_list(self, s: str, pattern: str) -> list[str] | None:
        m = re.search(pattern, s)
        if not m:
            return None
        return [t.strip() for t in m.group(1).split(",") if t.strip()]
