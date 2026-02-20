from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import numpy as np
import os
import sys
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
            if task == "coords_info":
                return self._coords_info()
                def _coords_info(self) -> ExecutionResult:
                    coords_cfg = self.config.get("coordinates", {})
                    columns = coords_cfg.get("columns", {})
                    crs_info = f"Input CRS: {coords_cfg.get('input_crs', 'EPSG:4326')}\nOutput CRS: {coords_cfg.get('output_crs', 'EPSG:3006')}\nTransform on load: {coords_cfg.get('transform_on_load', True)}"
                    col_info = "Columns:\n  " + ", ".join(f"{k}: {v}" for k, v in columns.items())
                    active_crs = coords_cfg.get('active_crs', coords_cfg.get('output_crs', 'EPSG:3006'))
                    msg = f"Active CRS: {active_crs}\n{crs_info}\n{col_info}"
                    return ExecutionResult(True, msg)
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
                # Build per-command options (do not persist across commands)
                opts = {
                    "start_date": command.get("start_date"),
                    "end_date": command.get("end_date"),
                    "log": command.get("log", False),
                    "negative": command.get("negative", False),
                    "min": command.get("min"),
                    "max": command.get("max"),
                    "lowess_frac": command.get("lowess_frac"),
                    "outlier_method": command.get("outlier_method"),
                    "z_thresh": command.get("z_thresh", 3.0),
                }
                return self._plot_time_series(
                    self._resolve_column(command["y"]),
                    command.get("interval"),
                    command.get("smooth"),
                    command.get("show"),
                    command.get("save"),
                    command.get("out"),
                    opts,
                )

            if task == "scatter_plot":
                opts = {
                    "start_date": command.get("start_date"),
                    "end_date": command.get("end_date"),
                    "log": command.get("log", False),
                    "negative": command.get("negative", False),
                    "min": command.get("min"),
                    "max": command.get("max"),
                    "xlog": command.get("xlog", False),
                    "xmin": command.get("xmin"),
                    "xmax": command.get("xmax"),
                    "lowess_frac": command.get("lowess_frac"),
                    "outlier_method": command.get("outlier_method"),
                    "z_thresh": command.get("z_thresh", 3.0),
                }
                return self._plot_scatter(
                    command.get("x"),
                    command.get("y"),
                    command.get("interval"),
                    command.get("smooth"),
                    command.get("show"),
                    command.get("save"),
                    command.get("out"),
                    opts,
                )

            if task == "plot_boxplot":
                return self._plot_boxplot(command)

            if task == "hex_map":
                opts = {
                    "start_date": command.get("start_date"),
                    "end_date": command.get("end_date"),
                    "min": command.get("min"),
                    "max": command.get("max"),
                    "negative": command.get("negative", False),
                    "outlier_method": command.get("outlier_method"),
                    "z_thresh": command.get("z_thresh", 3.0),
                }
                return self._hex_map(
                    self._resolve_column(command["y"]),
                    command.get("resolution", 8),
                    command.get("backend"),
                    show=True,
                    coastline_path=command.get("coastline_path"),
                    east_lim=command.get("east_lim"),
                    north_lim=command.get("north_lim"),
                    opts=opts,
                )

            if task == "compute_stats":
                cols = [self._resolve_column(c) for c in command["columns"]]
                return self._compute_stats(cols)

            if task == "compute_stats_by_time":
                cols = [self._resolve_column(c) for c in command["columns"]]
                opts = {
                    "start_date": command.get("start_date"),
                    "end_date": command.get("end_date"),
                    "outlier_method": command.get("outlier_method"),
                    "z_thresh": command.get("z_thresh", 3.0),
                }
                return self._compute_stats_by_time(cols, command["interval"], opts)

            if task == "create_variable":
                return self._create_variable(command.get("name"), command.get("expression"))

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

        # Exclude the positions file from the acoustic file list if the pattern matches it
        # This prevents accidentally loading the positions file as acoustic data when using patterns like '*.txt'.
        pos_name_lower = pos_file.name.lower()
        filtered = [f for f in files if f.name.lower() != pos_name_lower and not f.name.lower().startswith("positions")]
        if len(filtered) != len(files):
            logger.info(
                "Excluded %d file(s) from acoustic inputs because they look like the positions file (%s)",
                len(files) - len(filtered),
                pos_file,
            )
        files = filtered
        if not files:
            return ExecutionResult(False, f"After excluding positions file, no acoustic files remain in {data_dir} for pattern {pattern}")

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

    def _plot_time_series(self, y: str, interval: Optional[str], smooth: Optional[bool], show: Optional[bool], save: Optional[bool], out: Optional[str], opts: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        self._ensure_data()
        df = self.merged.copy()
        opts = opts or {}
        # Apply optional date filtering
        try:
            df = self._filter_by_date_range(
                df,
                opts.get("start_date"),
                opts.get("end_date"),
            )
        except Exception:
            # If no date params present or parse failed silently in state, continue
            pass
        # Select a sensible numeric column if requested one is missing
        y, note = self._choose_plot_column(y, df)
        # Apply transformations if present in state (used by CLI params)
        try:
            df, y = self._apply_transformations(
                df,
                y,
                log=bool(opts.get("log", False)),
                negative=bool(opts.get("negative", False)),
                min_val=self._coerce_float(opts.get("min")),
                max_val=self._coerce_float(opts.get("max")),
                outlier_method=opts.get("outlier_method"),
                z_thresh=float(opts.get("z_thresh", 3.0)),
            )
        except Exception:
            pass
        if interval:
            df = self.temporal.aggregate_by_time(df, interval, {y: "mean"})
        # Interpret smooth parameter: bool or mode string (e.g., 'loess', 'savgol', 'rolling', 'false')
        smooth_input = smooth
        smooth_enabled = True
        smooth_method = "lowess"
        # Determine LOWESS fraction from command or config
        default_frac = float(self.config.get("analysis", {}).get("lowess_fraction", 0.1))
        lowess_frac = float(opts.get("lowess_frac")) if opts.get("lowess_frac") is not None else default_frac
        if isinstance(smooth_input, str):
            val = smooth_input.strip().lower()
            if val in {"false", "off", "0"}:
                smooth_enabled = False
            elif val in {"true", "on", "1", "lowess", "loess"}:
                smooth_enabled = True
                smooth_method = "lowess"
            elif val in {"savgol", "savitzky", "savitzky-golay"}:
                smooth_enabled = True
                smooth_method = "savgol"
            elif val in {"rolling", "avg", "moving"}:
                smooth_enabled = True
                smooth_method = "rolling"
        elif isinstance(smooth_input, bool):
            smooth_enabled = bool(smooth_input)
        fig = self.plotter.plot_line_series(df, x="timestamp", y=y, smooth=smooth_enabled, smooth_method=smooth_method, lowess_frac=lowess_frac)
        result = self._finalize_plot(fig, default_name="timeseries.png", show=show, save=save, out=out)
        if note and result.ok:
            result.message += note
        return result

    def _plot_scatter(self, x: str, y: str, interval: Optional[str], smooth: Optional[bool], show: Optional[bool], save: Optional[bool], out: Optional[str], opts: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        self._ensure_data()
        df = self.merged.copy()
        opts = opts or {}
        # Apply optional date filtering
        try:
            df = self._filter_by_date_range(
                df,
                opts.get("start_date"),
                opts.get("end_date"),
            )
        except Exception:
            pass
        y, note = self._choose_plot_column(y, df)
        x, _ = self._choose_plot_column(x, df)
        # Apply transformations to y
        try:
            df, y = self._apply_transformations(
                df,
                y,
                log=bool(opts.get("log", False)),
                negative=bool(opts.get("negative", False)),
                min_val=self._coerce_float(opts.get("min")),
                max_val=self._coerce_float(opts.get("max")),
                outlier_method=opts.get("outlier_method"),
                z_thresh=float(opts.get("z_thresh", 3.0)),
            )
        except Exception:
            pass
        # Apply transformations to x (only for non-timestamp numeric axes)
        try:
            if x != "timestamp":
                df, x = self._apply_transformations(
                    df,
                    x,
                    log=bool(opts.get("xlog", False)),
                    min_val=self._coerce_float(opts.get("xmin")),
                    max_val=self._coerce_float(opts.get("xmax")),
                )
        except Exception:
            pass
        if interval:
            # When resampling by time, don't try to aggregate the timestamp index itself.
            agg_map = {y: "mean"}
            if x != "timestamp":
                agg_map[x] = "first"
            df = self.temporal.aggregate_by_time(df, interval, agg_map)
        # Interpret smooth parameter similarly to time-series
        smooth_input = smooth
        smooth_enabled = True
        smooth_method = "lowess"
        default_frac = float(self.config.get("analysis", {}).get("lowess_fraction", 0.1))
        lowess_frac = float(opts.get("lowess_frac")) if opts.get("lowess_frac") is not None else default_frac
        if isinstance(smooth_input, str):
            val = smooth_input.strip().lower()
            if val in {"false", "off", "0"}:
                smooth_enabled = False
            elif val in {"true", "on", "1", "lowess", "loess"}:
                smooth_enabled = True
                smooth_method = "lowess"
            else:
                # Only lowess supported for scatter at the moment
                smooth_enabled = True
                smooth_method = "lowess"
        elif isinstance(smooth_input, bool):
            smooth_enabled = bool(smooth_input)
        fig = self.plotter.plot_scatter(df, x=x, y=y, smooth=smooth_enabled, smooth_method=smooth_method, lowess_frac=lowess_frac)
        result = self._finalize_plot(fig, default_name=f"scatter_{y}_vs_{x}.png", show=show, save=save, out=out)
        if note and result.ok:
            result.message += note
        return result

    def _plot_boxplot(self, params: Dict[str, Any]) -> ExecutionResult:
        """Execute boxplot plotting with optional grouping and transforms.

        Expected params keys: 'y' (required), optional 'x'/'group', and date/transform keys.
        """
        self._ensure_data()
        df = self.merged.copy()
        # Date filtering
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        if start_date or end_date:
            try:
                df = self._filter_by_date_range(df, start_date, end_date)
            except Exception as e:
                return ExecutionResult(False, f"Date filtering failed: {e}")

        # Resolve columns
        y_col_in = params.get("y")
        x_col_in = params.get("x") or params.get("group")
        if not y_col_in:
            return ExecutionResult(False, "Parameter 'y' is required for boxplot")
        y = self._resolve_column(y_col_in)
        x = self._resolve_column(x_col_in) if x_col_in else None

        # Optional: bin continuous x into categories for grouped boxplots
        xbins_val = self._coerce_int(params.get("xbins"))
        xqbins_val = self._coerce_int(params.get("xqbins"))
        if x and (xbins_val or xqbins_val):
            try:
                # Only attempt binning if x is numeric-like
                x_series = pd.to_numeric(df[x], errors="coerce")
                # Drop rows where x is NaN to avoid empty bins
                df = df.loc[~x_series.isna()].copy()
                x_series = pd.to_numeric(df[x], errors="coerce")
                if xbins_val:
                    binned = pd.cut(x_series, bins=int(xbins_val), include_lowest=True)
                else:
                    # Quantile bins (may drop duplicate edges if data has ties)
                    binned = pd.qcut(x_series, q=int(xqbins_val), duplicates="drop")
                new_x = f"{x}_binned"
                # Convert intervals to readable labels for categorical axis
                df[new_x] = binned.astype(str)
                x = new_x
            except Exception as e:
                return ExecutionResult(False, f"Binning x failed: {e}")

        # Apply transformations to y
        try:
            df, y = self._apply_transformations(
                df,
                y,
                log=bool(params.get("log", False)),
                negative=bool(params.get("negative", False)),
                min_val=self._coerce_float(params.get("min")),
                max_val=self._coerce_float(params.get("max")),
                outlier_method=params.get("outlier_method"),
                z_thresh=float(params.get("z_thresh", 3.0)),
            )
        except Exception as e:
            return ExecutionResult(False, f"Transformation failed: {e}")

        # Create plot
        try:
            fig = self.plotter.plot_boxplot(df, y_column=y, x_column=x)
        except Exception as e:
            return ExecutionResult(False, f"Boxplot failed: {e}")

        # Save or show
        default_name = f"boxplot_{y}{f'_by_{x}' if x else ''}.png"
        result = self._finalize_plot(fig, default_name=default_name, show=params.get("show"), save=params.get("save"), out=params.get("out"))
        return result

    @staticmethod
    def _coerce_int(val: Any) -> int | None:
        try:
            if val is None:
                return None
            # Allow floats given as strings (e.g., "10.0")
            return int(float(val))
        except Exception:
            return None

    def _finalize_plot(self, fig, default_name: str, show: Optional[bool], save: Optional[bool], out: Optional[str]) -> ExecutionResult:
        # Defaults: show=True, save=False
        effective_show = True if show is None else bool(show)
        effective_save = False if save is None else bool(save)

        # Detect headless/Agg backend
        backend = matplotlib.get_backend().lower() if hasattr(matplotlib, "get_backend") else ""
        # On macOS/Windows, GUI backends don't rely on DISPLAY; treat as non-headless.
        # On Linux, assume headless if DISPLAY is missing or Agg backend is in use.
        headless = (sys.platform.startswith("linux") and not os.environ.get("DISPLAY")) or ("agg" in backend)

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

    def _hex_map(self, y: str, resolution: int, backend: str = None, show: bool = True, coastline_path: str = None, east_lim: list[float] | None = None, north_lim: list[float] | None = None, opts: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        self._ensure_data()
        opts = opts or {}
        # Optional date filtering before spatial aggregation
        try:
            df_src = self._filter_by_date_range(
                self.merged,
                opts.get("start_date"),
                opts.get("end_date"),
            )
        except Exception:
            df_src = self.merged
        if y not in df_src.columns:
            return ExecutionResult(False, self._unknown_column_message(y))
        # Apply thresholds (and optional negative) prior to spatial aggregation
        try:
            df_src, y_used = self._apply_transformations(
                df_src,
                y,
                log=False,
                negative=bool(opts.get("negative", False)),
                min_val=self._coerce_float(opts.get("min")),
                max_val=self._coerce_float(opts.get("max")),
                outlier_method=opts.get("outlier_method"),
                z_thresh=float(opts.get("z_thresh", 3.0)),
            )
        except Exception:
            y_used = y
        df = self.spatial.assign_hex_ids(df_src, resolution)
        agg = self.spatial.aggregate_by_hex(df, {y_used: "mean", "timestamp": "count"}).rename(columns={"timestamp": "count"})
        backend = backend or self.config.get("visualization", {}).get("map", {}).get("default_backend", "matplotlib")
        coords_cfg = self.config.get("coordinates", {})
        columns = coords_cfg.get("columns", {})
        sweref_mode = coords_cfg.get("output_crs", "EPSG:3006") == coords_cfg.get("active_crs", coords_cfg.get("output_crs", "EPSG:3006"))

        # Use default coastline path from config if none provided
        if coastline_path is None:
            coastline_path = (
                self.config.get("visualization", {})
                .get("map", {})
                .get("coastline_path")
            )

        # Coastline cropping and reprojection logic
        cropped_coastline_path = None
        if coastline_path and Path(coastline_path).exists():
            try:
                import geopandas as gpd
                minx, maxx = 12, 20  # Longitude
                miny, maxy = 55, 62  # Latitude
                coast = gpd.read_file(coastline_path)
                coast_cropped = coast.cx[minx:maxx, miny:maxy]
                # Choose CRS for coastline based on backend
                from tempfile import NamedTemporaryFile
                if backend == "matplotlib" and sweref_mode:
                    coast_out = coast_cropped.to_crs("EPSG:3006")
                else:
                    # Keep WGS84 for folium or non-sweref matplotlib
                    coast_out = coast_cropped.to_crs("EPSG:4326")
                with NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
                    coast_out.to_file(tmp.name, driver="GeoJSON")
                    cropped_coastline_path = tmp.name
            except Exception as e:
                print(f"Warning: Could not crop/reproject coastline: {e}")
                cropped_coastline_path = coastline_path
        else:
            cropped_coastline_path = coastline_path

        if backend == "matplotlib":
            from visualization.mpl_map import create_matplotlib_hex_map
            vmin = self._coerce_float(opts.get("min"))
            vmax = self._coerce_float(opts.get("max"))
            fig = create_matplotlib_hex_map(
                agg,
                value_column=y_used,
                show=show,
                coastline_path=cropped_coastline_path,
                east_lim=east_lim,
                north_lim=north_lim,
                vmin=vmin,
                vmax=vmax,
            )
            out = Path("outputs/maps/hex_map.png")
            out.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(out, dpi=300, bbox_inches='tight')
            # Show window is handled in create_matplotlib_hex_map
            return ExecutionResult(True, f"Matplotlib map created and shown. Saved to {out}", artifact=out)
        else:
            m = self.mapgen.create_hexagon_map(agg, value_column=y_used, coastline_path=cropped_coastline_path)
            # Apply bounds if provided
            try:
                if east_lim and north_lim:
                    from pyproj import Transformer
                    if sweref_mode:
                        # Convert SWEREF99 easting/northing to lon/lat for folium bounds
                        t_inv = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)
                        west_lon, south_lat = t_inv.transform(east_lim[0], north_lim[0])
                        east_lon, north_lat = t_inv.transform(east_lim[1], north_lim[1])
                    else:
                        # Interpret limits as lon/lat directly
                        west_lon, east_lon = east_lim[0], east_lim[1]
                        south_lat, north_lat = north_lim[0], north_lim[1]
                    m.fit_bounds([[south_lat, west_lon], [north_lat, east_lon]])
            except Exception as e:
                print(f"Warning: Could not apply folium bounds: {e}")
            out = Path("outputs/maps/hex_map.html")
            self.mapgen.save_map(m, out)
            if show:
                self.mapgen.show_map(m)
            return ExecutionResult(True, f"Folium map created and shown. Saved to {out}", artifact=out)

    def _compute_stats(self, columns: list[str]) -> ExecutionResult:
        self._ensure_data()
        stats = self.stats.calculate_descriptive_stats(self.merged, columns)
        out = Path("outputs/reports/descriptive_stats.txt")
        self.stats.save_stats_to_file(stats, out)
        return ExecutionResult(True, f"Saved stats to {out}", artifact=out)

    def _compute_stats_by_time(self, columns: list[str], interval: str, opts: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Compute descriptive statistics aggregated by time intervals."""
        self._ensure_data()
        opts = opts or {}
        df = self.merged.copy()
        
        # Apply date filtering if specified
        try:
            df = self._filter_by_date_range(
                df,
                opts.get("start_date"),
                opts.get("end_date"),
            )
        except Exception:
            pass
        
        # Apply outlier filtering to each column if specified
        outlier_method = opts.get("outlier_method")
        z_thresh = float(opts.get("z_thresh", 3.0))
        
        if outlier_method == "zscore":
            for col in columns:
                if col in df.columns:
                    try:
                        result_df = self.stats.detect_outliers(df, col, method="zscore", z_thresh=z_thresh)
                        if "outlier" in result_df.columns:
                            # Filter out outliers for this column only
                            mask = ~result_df["outlier"]
                            df.loc[~mask, col] = np.nan
                            if "outlier" in result_df.columns:
                                # Clean up the outlier column if it exists
                                df = df.drop(columns=["outlier"], errors="ignore")
                    except Exception:
                        pass
        
        # Calculate stats by time
        stats = self.stats.calculate_stats_by_time(df, interval, columns)
        
        # Save to file
        out = Path(f"outputs/reports/stats_by_time_{interval.replace(' ', '_')}.txt")
        self.stats.save_stats_by_time_to_file(stats, out)
        
        csv_out = out.with_suffix(".csv")
        return ExecutionResult(True, f"Saved time-aggregated stats to {out} and {csv_out}", artifact=out)

    def _create_variable(self, name: str, expression: str) -> ExecutionResult:
        """Create a new calculated variable and add it to the session data.
        
        Supports:
        - Temporal extractions: timestamp.dt.hour, timestamp.dt.day, etc.
        - Arithmetic: backscatter*2, depth+10, etc.
        - pandas eval expressions
        """
        self._ensure_data()
        if not name or not expression:
            return ExecutionResult(False, "Both 'name' and 'expression' are required")
        
        if name in self.merged.columns:
            return ExecutionResult(False, f"Variable '{name}' already exists. Choose a different name.")
        
        try:
            # Handle datetime accessor patterns (e.g., timestamp.dt.hour)
            if ".dt." in expression:
                # Parse pattern like "timestamp.dt.hour"
                parts = expression.split(".")
                if len(parts) == 3 and parts[1] == "dt":
                    col_name = parts[0]
                    accessor = parts[2]
                    if col_name not in self.merged.columns:
                        return ExecutionResult(False, f"Column '{col_name}' not found")
                    # Ensure datetime type
                    if not pd.api.types.is_datetime64_any_dtype(self.merged[col_name]):
                        self.merged[col_name] = pd.to_datetime(self.merged[col_name], errors="coerce")
                    # Apply datetime accessor
                    try:
                        self.merged[name] = getattr(self.merged[col_name].dt, accessor)
                    except AttributeError:
                        return ExecutionResult(False, f"Invalid datetime accessor: {accessor}")
                else:
                    return ExecutionResult(False, f"Invalid datetime expression: {expression}")
            else:
                # Try pandas eval for arithmetic expressions
                try:
                    self.merged[name] = self.merged.eval(expression)
                except Exception:
                    # Fallback: try direct column operations
                    # This handles simple cases like "backscatter*2"
                    self.merged[name] = eval(expression, {"__builtins__": {}}, self.merged.to_dict("series"))
            
            # Verify the column was created
            if name not in self.merged.columns:
                return ExecutionResult(False, f"Failed to create variable '{name}'")
            
            return ExecutionResult(True, f"Created variable '{name}' from expression '{expression}'. {len(self.merged[name])} values.")
        
        except Exception as e:
            return ExecutionResult(False, f"Error creating variable: {e}")

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
            "  plot y=<alias|column> 5min [smooth=true|false|loess|savgol|rolling] [show=true|false] [save=true|false] [out=path]   # time series\n"
            "  scatter y:<column> [x:<column>] [smooth=true|false|loess|lowess] [frac:<0-1>] [show] [save] [out]   # scatter plot (custom x/y axes)\n"
            "    Transforms & limits:\n"
            "      - Y axis: log/min/max/negative (e.g., log=true min=50 max=500 negative=true). 'negative=true' flips sign (depth → -depth) for downward axes.\n"
            "      - X axis: xlog/xmin/xmax (e.g., xlog=true xmin=1)\n"
            "      - Outlier filtering: outliers=zscore z_thresh=3.0 (default threshold is 3.0)\n"
            "      - Syntax: both '=' and ':' are accepted (log:true)\n"
            "      - Order: outlier filter → date filter → thresholds → negative → log (≤0 excluded before log)\n"
            "      - Note: x-axis transforms are ignored when x=timestamp\n"
            "  scatter <y_col> vs <x_col>\n"
            "  scatter x:<x_col> y:<y_col>\n"
            "    If the specified column is missing, the CLI will choose a numeric column automatically (prefers 'backscatter' or 'depth').\n"
            "  boxplot y:<column> [x:<group_col>] [start_date=YYYY-MM-DD] [end_date=YYYY-MM-DD] [log=true|false] [min=<v>] [max=<v>] [outliers=zscore] [show] [save] [out=<path>]  # boxplot\n"
            "    - Groups by 'x' if provided; otherwise single-series boxplot\n"
            "    - If 'x' is continuous, you can bin it with 'xbins:<n>' (equal-width) or 'xqbins:<n>' (quantiles)\n"
            "    - Applies the same Y transforms (log/min/max), outlier filtering, and date filtering\n"
            "  columns                               # list plottable numeric columns and aliases\n"
            "  map <variable> [resolution:<n>] [agg:<func>] [backend:matplotlib|folium] [east_lim=[x1,x2]] [north_lim=[y1,y2]]  # spatial map\n"
            "    - Applies date filters, outlier filtering, and min/max thresholds before hex aggregation\n"
            "    - Supports 'negative=true' prior to aggregation (e.g., map depth negative=true)\n"
            "    - Transforms/limits are per-command and do not persist; omit them to use defaults (no transform, full range).\n"
            "  stats columns=<alias|column>[,<alias|column>...]  # descriptive statistics\n"
            "  stats by time <interval> columns=<col>[,<col>...] [outliers=zscore] [start_date=...] [end_date=...]  # stats by time aggregation\n"
            "    - Computes statistics for each time bin (long-format output)\n"
            "    - Supports outlier filtering and date filtering\n"
            "    - Saves both CSV and readable text format\n"
            "  create var <name>=<expression>        # create calculated variable (persists in session)\n"
            "  calc <name>=<expression>              # alias for 'create var'\n"
            "  create <attr> from timestamp          # temporal extraction shorthand (hour, day, month, year, dayofweek, etc.)\n"
            "    Examples:\n"
            "      create var hour=timestamp.dt.hour\n"
            "      calc depth_m=depth/1000\n"
            "      create hour from timestamp\n"
            "      calc bs2=backscatter*2\n"
            "  coords info                            # show coordinate system info and columns\n"
            "Examples:\n"
            "  alias bs=backscatter temp=temp_water\n"
            "  plot y=bs 5min smooth=loess frac=0.15 show=true save=true out=outputs/plots/bs_5min.png\n"
            "  scatter depth vs temperature smooth=loess frac=0.1 outliers=zscore z_thresh=2.5\n"
            "  scatter x:salinity y:depth xlog:true xmin:1e-3 xmax:1e2 save:true show:false\n"
            "  boxplot y:backscatter x:depth xbins:10 start_date:2024-10-06 end_date:2024-10-07 log:true min:50 max:200 outliers:zscore save:true\n"
            "  map depth\n"
            "  map depth backend:folium outliers=zscore\n"
            "  map depth resolution:9 agg:max\n"
            "  map depth negative:true min:5 max:50\n"
            "  stats columns=bs,temp\n"
            "  stats by time 10min columns=backscatter,depth outliers=zscore\n"
            "  create var hour=timestamp.dt.hour\n"
            "  create hour from timestamp\n"
            "  calc depth_negative=depth*-1\n"
            "  coords info\n"
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

    def _choose_plot_column(self, requested: str, df: pd.DataFrame) -> tuple[str, str | None]:
        """Return a valid numeric column to plot.

        - If `requested` exists, use it.
        - Else prefer 'backscatter' or 'depth' if present.
        - Else pick the first numeric column excluding obvious non-plot columns.
        Returns (column, note) where note is a message suffix indicating fallback.
        """
        if requested in df.columns:
            return requested, None
        ignore = {"timestamp", "latitude", "longitude", "position_matched"}
        numeric_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in ignore]
        for candidate in ("backscatter", "depth"):
            if candidate in numeric_cols:
                return candidate, f" (column '{requested}' missing; used '{candidate}' instead)"
        if numeric_cols:
            chosen = numeric_cols[0]
            return chosen, f" (column '{requested}' missing; used '{chosen}' instead)"
        # If no numeric columns, propagate original requested to trigger error downstream
        return requested, None

    # === Helpers: date filtering and transformations ===
    def _filter_by_date_range(self, data: pd.DataFrame, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        """Filter dataframe by date range on a timestamp-like column."""
        if not start_date and not end_date:
            return data
        # Identify timestamp column
        ts_col = None
        for c in ("timestamp", "time", "datetime", "date"):
            if c in data.columns:
                ts_col = c
                break
        if ts_col is None:
            raise ValueError("No timestamp column found for date filtering")
        df = data.copy()
        # Ensure datetime
        if not pd.api.types.is_datetime64_any_dtype(df[ts_col]):
            df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        # Parse bounds
        start_dt = pd.to_datetime(start_date) if start_date else df[ts_col].min()
        end_dt = pd.to_datetime(end_date) if end_date else df[ts_col].max()
        if isinstance(end_date, str) and len(end_date) == 10:
            end_dt = end_dt + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        if start_dt > end_dt:
            raise ValueError("start_date is after end_date")
        mask = (df[ts_col] >= start_dt) & (df[ts_col] <= end_dt)
        return df.loc[mask].copy()

    def _apply_transformations(
        self,
        data: pd.DataFrame,
        column: str,
        log: bool = False,
        negative: bool = False,
        min_val: float | None = None,
        max_val: float | None = None,
        outlier_method: str | None = None,
        z_thresh: float = 3.0,
    ) -> tuple[pd.DataFrame, str]:
        """Apply outlier filtering, min/max filtering and optional natural log transform on a column.

        Returns the (possibly filtered) dataframe and the column name to use (new name if log).
        Order: outlier filter → date filter → thresholds → negative → log
        """
        if column not in data.columns:
            raise ValueError(f"Column '{column}' not in data")
        df = data.copy()
        # Ensure numeric
        if not pd.api.types.is_numeric_dtype(df[column]):
            df[column] = pd.to_numeric(df[column], errors="coerce")
        
        # Outlier filtering (before min/max thresholds)
        if outlier_method == "zscore":
            result_df = self.stats.detect_outliers(df, column, method="zscore", z_thresh=z_thresh)
            if "outlier" in result_df.columns:
                df = result_df.loc[~result_df["outlier"]].copy()
                df = df.drop(columns=["outlier"], errors="ignore")
        
        # Threshold filters
        if min_val is not None:
            df = df.loc[df[column] >= float(min_val)].copy()
        if max_val is not None:
            df = df.loc[df[column] <= float(max_val)].copy()
        if df.empty:
            return df, column
        # Negative transform (x / -1)
        if negative:
            new_col_neg = f"{column}_neg"
            df[new_col_neg] = df[column].apply(lambda x: (None if pd.isna(x) else float(x / -1.0)))
            column = new_col_neg
        # Log transform
        if log:
            new_col = f"{column}_log"
            df[new_col] = df[column].apply(lambda x: (None if pd.isna(x) else (None if x <= 0 else float(np.log(x)))))
            return df, new_col
        return df, column

    @staticmethod
    def _coerce_float(val: Any) -> float | None:
        try:
            return float(val) if val is not None else None
        except Exception:
            return None
