from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

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

    def execute(self, command: Dict[str, Any]) -> ExecutionResult:
        task = command.get("task")
        try:
            if task == "set":
                self.state.update(command.get("params", {}))
                return ExecutionResult(True, f"Updated settings: {command.get('params', {})}")

            if task == "load":
                return self._load_data(command.get("params", {}))

            if task == "aggregate_time":
                return self._aggregate_time(command["interval"])

            if task == "time_series_plot":
                return self._plot_time_series(command["y"], command.get("interval"))

            if task == "scatter_plot":
                return self._plot_scatter(command["y"], command.get("interval"))

            if task == "hex_map":
                return self._hex_map(command["y"], command.get("resolution", 8))

            if task == "compute_stats":
                return self._compute_stats(command["columns"])

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

    def _load_data(self, params: Dict[str, Any]) -> ExecutionResult:
        data_dir = Path(params.get("dir", self.state["data_dir"]))
        pattern = params.get("pattern", self.state["pattern"])
        pos_file = Path(params.get("positions", self.state["positions"]))

        loader = AcousticsDataLoader()
        files = loader.get_file_list(data_dir, pattern)
        if not files:
            return ExecutionResult(False, f"No files found in {data_dir} with pattern {pattern}")
        df = loader.load_csv_files(files, lazy=False)

        if not pos_file.exists():
            return ExecutionResult(False, f"Position file not found: {pos_file}")
        positions = pd.read_csv(pos_file, parse_dates=["timestamp"])

        merger = PositionMerger()
        merged = merger.merge_positions(df, positions, tolerance=self.config["processing"]["time_merge_tolerance"])

        self.data = df
        self.positions = positions
        self.merged = merged
        return ExecutionResult(True, f"Loaded {len(df)} rows; merged with positions ({len(merged)} rows)")

    def _ensure_data(self) -> None:
        if self.merged is None:
            raise RuntimeError("No data loaded. Use 'load' command.")

    def _aggregate_time(self, interval: str) -> ExecutionResult:
        self._ensure_data()
        agg = self.temporal.aggregate_by_time(self.merged, interval, {"backscatter": "mean"})
        self.merged = agg
        return ExecutionResult(True, f"Aggregated by {interval}; rows: {len(agg)}")

    def _plot_time_series(self, y: str, interval: Optional[str]) -> ExecutionResult:
        self._ensure_data()
        df = self.merged.copy()
        if interval:
            df = self.temporal.aggregate_by_time(df, interval, {y: "mean"})
        fig = self.plotter.plot_line_series(df, x="timestamp", y=y)
        out = Path("outputs/plots/timeseries.png")
        self.plotter.save_plot(fig, out)
        return ExecutionResult(True, f"Saved plot to {out}", artifact=out)

    def _plot_scatter(self, y: str, interval: Optional[str]) -> ExecutionResult:
        self._ensure_data()
        df = self.merged.copy()
        if interval:
            df = self.temporal.aggregate_by_time(df, interval, {y: "mean"})
        fig = self.plotter.plot_scatter(df, x="timestamp", y=y)
        out = Path("outputs/plots/scatter.png")
        self.plotter.save_plot(fig, out)
        return ExecutionResult(True, f"Saved plot to {out}", artifact=out)

    def _hex_map(self, y: str, resolution: int) -> ExecutionResult:
        self._ensure_data()
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

    def help_text(self) -> str:
        return (
            "Commands:\n"
            "  set key=value [...]                # set dir, pattern, positions\n"
            "  load dir=./data pattern=*.csv positions=positions.csv\n"
            "  aggregate time 5min                # or 'aggregate_time interval=5min'\n"
            "  plot y=backscatter 5min            # time series plot with optional interval\n"
            "  plot scatter y=backscatter         # scatter plot\n"
            "  map hex y=backscatter res=8        # hexagonal map\n"
            "  stats columns=backscatter,temperature\n"
            "  help | exit\n"
        )
