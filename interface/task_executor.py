from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import os
import matplotlib
import matplotlib.pyplot as plt

from aggregation.spatial_aggregator import SpatialAggregator
from aggregation.temporal_aggregator import TemporalAggregator
from analysis.statistics import StatisticsCalculator
from data_loader.csv_loader import AcousticsDataLoader
from data_loader.position_merger import PositionMerger
from visualization.map_generator import HexagonalMapGenerator
from visualization.time_series_plots import TimeSeriesPlotter
from utils.io_helpers import read_config, setup_logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    ok: bool
    message: str
    artifact: Optional[Path] = None


class TaskExecutor:
    def __init__(self, config_path: Path = Path("config/settings.yaml")):
        self.config = read_config(config_path)
        setup_logging(self.config.get("logging", {}).get("level", "INFO"))
        self.data: Optional[pd.DataFrame] = None
        self.positions: Optional[pd.DataFrame] = None
        self.merged: Optional[pd.DataFrame] = None
        self.temporal = TemporalAggregator()
        self.spatial = SpatialAggregator()
        self.stats = StatisticsCalculator()
        self.plotter = TimeSeriesPlotter()
        self.mapgen = HexagonalMapGenerator()
        self.state: Dict[str, Any] = {
            "data_dir": self.config["data"]["network_storage_path"],
            "pattern": self.config["data"]["acoustic_csv_pattern"],
            "positions": self.config["data"]["position_file"],
        }
        # User-defined CLI variable aliases, e.g., {"bs": "backscatter"}
        self.aliases: Dict[str, str] = {}

    def execute(self, command: Dict[str, Any]) -> ExecutionResult:
        task = command.get("task")
        try:
            if task == "set":
                self.state.update(command.get("params", {}))
                return ExecutionResult(True, f"Updated settings: {command.get('params', {})}")

            if task == "alias":
                new_aliases = command.get("aliases", {})
                self.aliases.update(new_aliases)
                return ExecutionResult(True, f"Added aliases: {new_aliases}")

            if task == "load":
                return self._load_data(command.get("params", {}))

            if task == "aggregate_time":
                return self._aggregate_time(command["interval"], command.get("y"))

            if task == "time_series_plot":
                return self._plot_time_series(
                    self._resolve_column(command["y"]),
                    command.get("interval"),
                    command.get("smooth"),
                    command.get("show"),
                    command.get("save"),
                    command.get("out"),
                )

            if task == "scatter_plot":
                return self._plot_scatter(
                    self._resolve_column(command["y"]),
                    command.get("interval"),
                    command.get("smooth"),
                    command.get("show"),
                    command.get("save"),
                    command.get("out"),
                )

            if task == "hex_map":
                return self._hex_map(self._resolve_column(command["y"]), command.get("resolution", 8))

            if task == "compute_stats":
                cols = [self._resolve_column(c) for c in command["columns"]]
                return self._compute_stats(cols)

            if task == "list_columns":
                return self._list_columns()

            if task == "help":
                return ExecutionResult(True, self.help_text())

            if task == "exit":
                return ExecutionResult(True, "exit")

            return ExecutionResult(False, f"Unknown task: {task}")
        except Exception as e:  # noqa: BLE001
            logger.exception("Error executing task")
            return ExecutionResult(False, f"Error: {e}")

    def dry_run(self, command: Dict[str, Any]) -> str:
        return f"Would execute: {command}"

    def _resolve_column(self, name: str) -> str:
        """Resolve a CLI variable or column name via aliases.

        If an alias is defined for 'name', return the mapped column.
        Otherwise, return 'name' unchanged.
        """
        # Prefer an explicit column present in current data over an alias
        alias = self.aliases.get(name)
        cols = set()
        if self.merged is not None:
            cols = set(self.merged.columns)
        elif self.data is not None:
            cols = set(self.data.columns)
        # If the literal name exists as a column, use it (avoid alias shadowing)
        if name in cols:
            return name
        # Otherwise, fall back to alias if defined
        if alias is not None:
            return alias
        return name

    def _load_data(self, params: Dict[str, Any]) -> ExecutionResult:
        data_dir = Path(params.get("dir", self.state["data_dir"]))
        pattern = params.get("pattern", self.state["pattern"])
        pos_file = Path(params.get("positions", self.state["positions"]))

        # Load acoustic data: source column is 'time' -> normalize to 'timestamp'
        loader = AcousticsDataLoader(column_map={"time": "timestamp"}, timestamp_col="time")
        files = loader.get_file_list(data_dir, pattern)
        if not files:
            return ExecutionResult(False, f"No files found in {data_dir} with pattern {pattern}")
        df = loader.load_csv_files(files, lazy=False)

        # Resolve positions path: accept absolute, relative, or relative to data_dir
        if not pos_file.exists():
            alt1 = data_dir / pos_file
            alt2 = data_dir / pos_file.name
            if alt1.exists():
                pos_file = alt1
            elif alt2.exists():
                pos_file = alt2
            else:
                return ExecutionResult(False, f"Position file not found: {pos_file}")
        # Load positions with robust, case-insensitive column handling
        # Accept variants like 'Time'/'time', 'Lat'/'lat'/'latitude', 'Long'/'lon'/'longitude'
        sep = "\t" if pos_file.suffix.lower() in {".tsv", ".txt"} else ","
        positions = pd.read_csv(pos_file, sep=sep)
        col_lut = {c.lower().strip(): c for c in positions.columns}
        # Identify canonical columns
        time_key = next((k for k in ("time", "timestamp", "datetime", "date") if k in col_lut), None)
        lat_key = next((k for k in ("lat", "latitude", "y") if k in col_lut), None)
        lon_key = next((k for k in ("long", "lon", "longitude", "x") if k in col_lut), None)
        if not time_key:
            raise ValueError(f"Positions file missing time column (looked for one of time/timestamp/datetime/date). Columns: {list(positions.columns)}")
        if not lat_key or not lon_key:
            raise ValueError(f"Positions file missing latitude/longitude columns. Columns: {list(positions.columns)}")
        positions = positions.rename(
            columns={
                col_lut[time_key]: "timestamp",
                col_lut[lat_key]: "latitude",
                col_lut[lon_key]: "longitude",
            }
        )
        # Ensure timestamp is datetime
        positions["timestamp"] = pd.to_datetime(positions["timestamp"], errors="coerce")
        # Drop rows where timestamp failed to parse to avoid merge issues
        positions = positions.dropna(subset=["timestamp"]).reset_index(drop=True)

        merger = PositionMerger(acoustic_time_col="timestamp", position_time_col="timestamp", lat_col="latitude", lon_col="longitude")
        # Use interpolation-based assignment to handle non-matching timestamps robustly
        merged = merger.merge_positions_interpolated(df, positions)

        self.data = df
        self.positions = positions
        self.merged = merged
        return ExecutionResult(True, f"Loaded {len(df)} rows; merged with positions ({len(merged)} rows)")

    def _ensure_data(self) -> None:
        if self.merged is None:
            raise RuntimeError("No data loaded. Use 'load' command.")

    def _aggregate_time(self, interval: str, y: Optional[str]) -> ExecutionResult:
        self._ensure_data()
        target_col = self._resolve_column(y) if y else "backscatter"
        if target_col not in self.merged.columns:
            return ExecutionResult(False, self._unknown_column_message(target_col))
        agg = self.temporal.aggregate_by_time(self.merged, interval, {target_col: "mean"})
        self.merged = agg
        return ExecutionResult(True, f"Aggregated {target_col} by {interval}; rows: {len(agg)}")

    def _plot_time_series(self, y: str, interval: Optional[str], smooth: Optional[bool], show: Optional[bool], save: Optional[bool], out: Optional[str]) -> ExecutionResult:
        self._ensure_data()
        df = self.merged.copy()
        if y not in df.columns:
            return ExecutionResult(False, self._unknown_column_message(y))
        if interval:
            df = self.temporal.aggregate_by_time(df, interval, {y: "mean"})
        fig = self.plotter.plot_line_series(df, x="timestamp", y=y, smooth=True if smooth is None else bool(smooth))
        return self._finalize_plot(fig, default_name="timeseries.png", show=show, save=save, out=out)

    def _plot_scatter(self, y: str, interval: Optional[str], smooth: Optional[bool], show: Optional[bool], save: Optional[bool], out: Optional[str]) -> ExecutionResult:
        self._ensure_data()
        df = self.merged.copy()
        if y not in df.columns:
            return ExecutionResult(False, self._unknown_column_message(y))
        if interval:
            df = self.temporal.aggregate_by_time(df, interval, {y: "mean"})
        fig = self.plotter.plot_scatter(df, x="timestamp", y=y, smooth=True if smooth is None else bool(smooth))
        return self._finalize_plot(fig, default_name="scatter.png", show=show, save=save, out=out)

    def _finalize_plot(self, fig, default_name: str, show: Optional[bool], save: Optional[bool], out: Optional[str]) -> ExecutionResult:
        # Defaults: show=True, save=False
        effective_show = True if show is None else bool(show)
        effective_save = False if save is None else bool(save)

        # Detect headless/Agg backend
        backend = matplotlib.get_backend().lower() if hasattr(matplotlib, "get_backend") else ""
        headless = (not os.environ.get("DISPLAY")) or ("agg" in backend)

        note = ""
        out_path: Optional[Path] = None
        if effective_show and headless:
            # Can't show; fallback to saving
            effective_show = False
            if not effective_save:
                effective_save = True
            note = " (no display detected; saved instead)"

        if effective_save:
            out_path = Path(out) if out else Path("outputs/plots") / default_name
            # If also showing, don't close here
            self.plotter.save_plot(fig, out_path, close=not effective_show)

        if effective_show:
            try:
                plt.show()
            finally:
                plt.close(fig)

        if out_path is not None:
            return ExecutionResult(True, f"Saved plot to {out_path}{note}", artifact=out_path)
        # Neither shown (in this environment) nor saved
        if note:
            return ExecutionResult(False, f"Unable to display plot{note}. Use save=true to write to file.")
        return ExecutionResult(True, "Displayed plot.")

    def _hex_map(self, y: str, resolution: int) -> ExecutionResult:
        self._ensure_data()
        if y not in self.merged.columns:
            return ExecutionResult(False, self._unknown_column_message(y))
        df = self.spatial.assign_hex_ids(self.merged, resolution)
        agg = self.spatial.aggregate_by_hex(df, {y: "mean", "timestamp": "count"}).rename(columns={"timestamp": "count"})
        m = self.mapgen.create_hexagon_map(agg, value_column=y)
        out = Path("outputs/maps/hex_map.html")
        self.mapgen.save_map(m, out)
        return ExecutionResult(True, f"Saved map to {out}", artifact=out)

    def _compute_stats(self, columns: list[str]) -> ExecutionResult:
        self._ensure_data()
        stats = self.stats.calculate_descriptive_stats(self.merged, columns)
        out = Path("outputs/reports/descriptive_stats.txt")
        self.stats.save_stats_to_file(stats, out)
        return ExecutionResult(True, f"Saved stats to {out}", artifact=out)

    def _list_columns(self) -> ExecutionResult:
        self._ensure_data()
        df = self.merged
        ignore = {"timestamp", "latitude", "longitude", "position_matched"}
        num_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in ignore]
        if not num_cols:
            return ExecutionResult(True, "No plottable numeric columns found.")
        alias_lines = []
        if self.aliases:
            alias_lines.append("Aliases:")
            for k, v in sorted(self.aliases.items()):
                alias_lines.append(f"  {k} -> {v}")
        msg = "Plottable columns: " + ", ".join(num_cols)
        if alias_lines:
            msg += "\n" + "\n".join(alias_lines)
        return ExecutionResult(True, msg)

    def help_text(self) -> str:
        return (
            "Commands:\n"
            "  set key=value [...]                # set dir, pattern, positions\n"
            "  alias name=column [...]             # define CLI variables (aliases) for columns\n"
            "  load dir=./data pattern=*.csv positions=positions.csv\n"
            "  aggregate time 5min y=<alias|column>  # default y=backscatter if omitted\n"
            "  plot y=<alias|column> 5min [smooth=true|false] [show=true|false] [save=true|false] [out=path]   # time series\n"
            "  plot scatter y=<alias|column> [smooth=true|false] [show=true|false] [save=true|false] [out=path] # scatter\n"
            "  columns                               # list plottable numeric columns and aliases\n"
            "  map hex y=<alias|column> res=8        # hexagonal map\n"
            "  stats columns=<alias|column>[,<alias|column>...]\n"
            "Examples:\n"
            "  alias bs=backscatter temp=temp_water\n"
            "  plot y=bs 5min smooth=false show=true save=true out=outputs/plots/bs_5min.png\n"
            "  map hex y=bs res=8\n"
            "  stats columns=bs,temp\n"
            "  help | exit\n"
        )

    def _unknown_column_message(self, col: str) -> str:
        # Provide a helpful error with nearby suggestions and current aliases
        cols = []
        if self.merged is not None:
            cols = list(self.merged.columns)
        sample = ", ".join(c for c in cols if c != "timestamp")[:200]
        alias_info = f" Aliases: {self.aliases}" if self.aliases else ""
        return f"Column not found: {col}. Available columns include: {sample}.{alias_info}"
