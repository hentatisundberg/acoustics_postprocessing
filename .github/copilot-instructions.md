# Copilot Instructions for Acoustics Postprocessing

These instructions help AI coding agents work effectively in this repository by describing architecture, workflows, key conventions, and integration points.

## Architecture Overview
- **Interactive CLI**: Entry in [main.py](main.py) calls [interface/cli.py](interface/cli.py), which uses [interface/nlp_interpreter.py](interface/nlp_interpreter.py) to parse commands and [interface/task_executor.py](interface/task_executor.py) to run tasks.
- **Data Loading/Merge**: Acoustic CSVs via [data_loader/csv_loader.py](data_loader/csv_loader.py); positions merged/time-interpolated in [data_loader/position_merger.py](data_loader/position_merger.py). Loads honor CRS settings in [config/settings.yaml](config/settings.yaml).
- **Aggregation**:
  - Temporal in [aggregation/temporal_aggregator.py](aggregation/temporal_aggregator.py)
  - Spatial H3 hex aggregation in [aggregation/spatial_aggregator.py](aggregation/spatial_aggregator.py)
- **Analysis/Transforms**: Statistics in [analysis/statistics.py](analysis/statistics.py). Column transforms (min/max, log, negative) applied centrally via `TaskExecutor._apply_transformations()` in [interface/task_executor.py](interface/task_executor.py#L704).
- **Visualization**:
  - Time series & scatter in [visualization/time_series_plots.py](visualization/time_series_plots.py)
  - Maps (Matplotlib) in [visualization/mpl_map.py](visualization/mpl_map.py) and (Folium HTML) in [visualization/map_generator.py](visualization/map_generator.py)
- **Outputs**: Plots → [outputs/plots](outputs/plots), Maps → [outputs/maps](outputs/maps), Stats → [outputs/reports](outputs/reports).

## Developer Workflows
- **Environment**: Use the project venv.
  - macOS/Linux:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
- **Run CLI**:
  - ```bash
    .venv/bin/python -m main
    ```
- **Run tests** (smoke-style scripts under [tests](tests)):
  - ```bash
    .venv/bin/python tests/transform_smoke.py
    .venv/bin/python tests/map_smoke.py
    .venv/bin/python tests/scatter_smoke.py
    ```
- **Artifacts**: Execution prints saved file paths and returns them from `TaskExecutor._finalize_plot()`.

## Command Parsing & Conventions
- **Flexible syntax**: The interpreter accepts both `key=value` and `key:value` forms.
- **Common tasks** (handled in `TaskExecutor.execute()`):
  - Load: `load dir=... pattern=... positions=...`
  - Aggregate: `aggregate time 5min y:<col>`
  - Plot line: `plot y:<col> 5min [smooth=loess|savgol|rolling]`
  - Scatter: `scatter <y> [vs <x>] [smooth=true|false|loess]`
  - Boxplot: `boxplot y:<col> [x:<group>] [xbins:<n>|xqbins:<n>]`
  - Map: `map <variable> [resolution:<n>] [backend:matplotlib|folium] [east_lim=[x1,x2]] [north_lim=[y1,y2]]`
  - Stats: `stats columns=a,b`
  - Aliases: `alias bs=backscatter temp=temp_water` (persist in session)
- **Transforms**:
  - Y-axis: `log`, `min`, `max`, `negative` (e.g., `log=true min=50 max=500 negative=true`)
  - X-axis (scatter): `xlog`, `xmin`, `xmax` (ignored if x=`timestamp`)
  - Order: date filter → thresholds → negative → log
- **Auto column resolution**: If a requested column is missing, `TaskExecutor` picks a sensible numeric column (prefers `backscatter` or `depth`). See [interface/task_executor.py](interface/task_executor.py#L704).

## Mapping Details
- **CRS**:
  - SWEREF99 TM (EPSG:3006) active mode uses Matplotlib axes in easting/northing; `contextily` basemap when installed.
  - Folium maps work in WGS84 (EPSG:4326) with bounds conversion when `east_lim`/`north_lim` are given in SWEREF.
- **Color limits**: Matplotlib maps honor `min`/`max` via `vmin`/`vmax` in [visualization/mpl_map.py](visualization/mpl_map.py#L1). Folium polygons currently use default color ramp via aggregation; adjust in `map_generator` if needed.
- **Coastline overlay**: Provide `coastline=...` (GeoJSON/shapefile). Coastline is cropped and reprojected in `TaskExecutor._hex_map()`.

## Configuration
- Main settings in [config/settings.yaml](config/settings.yaml): data directories/patterns, coordinate columns/CRS, visualization defaults.
- Coordinate handling: Position files can be transformed on load; both WGS84 and SWEREF columns may be present and used.

## External Dependencies
- Pandas, NumPy, Matplotlib, Seaborn
- H3, Folium; optional Contextily for basemaps
- GeoPandas/Shapely for coastline overlays
- PyProj for CRS transforms

## Practical Examples
- Line series with LOWESS and thresholds:
  - `plot y=backscatter 5min smooth=loess min=50 max=500 save=true`
- Scatter with transforms:
  - `scatter depth vs salinity xlog=true xmin=1e-3 xmax=1e2 negative=true`
- Map with bounds and limits:
  - `map nasc0 resolution:6 east_lim:[600000,720000] north_lim:[6650000,6800000] max:0.5 backend:matplotlib`

If anything is unclear or missing (e.g., additional test commands, data schemas), tell us what you need and we’ll refine these instructions.

# Use of virtual environments
When suggesting code executions, always ensure that the are run withing the project's virtual environment to maintain dependency consistency. That is, every time something should be executed, the path is supposed to be: /Users/jonas/Documents/Programming/python/acoustics_postprocessing/.venv/bin/python <program_to_run>