# Acoustics Postprocessing System

A modular Python toolkit for loading, merging, aggregating, analyzing, plotting, and mapping acoustic depth data. It supports temporal aggregation, H3 hexagonal spatial aggregation, descriptive statistics, time series plots with smoothing, and interactive maps.

## Features
- Load many CSVs (supports network paths) and merge with timestamped positions
- Temporal aggregation with flexible intervals (e.g., 5min, 1h)
- Spatial aggregation using H3 hexagons at configurable resolution
- Time series and scatter plots with smoothing (LOWESS/Savitzky–Golay)
- Interactive hexagon map export (HTML)
- Descriptive statistics exported to text files
- Interactive CLI with lightweight natural language parsing

## Quick Start

### 1) Create environment and install

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```



Note: `geopandas` and `shapely` have prebuilt wheels for macOS. If installation fails, ensure you have an up-to-date pip (`pip install --upgrade pip`) and Xcode command line tools.

### 2) Prepare your data

- Acoustic CSVs: should include at minimum `timestamp` and your measurement column(s), e.g. `depth`. The CLI also accepts a column named `time` and normalizes it to `timestamp` automatically.
- Position CSV/TSV (default `positions.csv`): must contain `timestamp`, `latitude`, `longitude` columns. The CLI also accepts files with columns named `Time`, `Lat`, `Long` (as in `positions.txt`) and normalizes them automatically; tab-delimited `.txt`/`.tsv` files are supported.
- Place files under `./data` by default, or point to your location via CLI `set` command.

Example structure:
```
acoustics_postprocessing/
├── data/
│   ├── acoustic_001.csv
│   ├── acoustic_002.csv
│   └── positions.csv
└── config/settings.yaml
```

### 3) Run the CLI

```bash
python -m main
```

You’ll get an interactive prompt. Common commands:

- Configure paths (optional):
  - `set dir=./data pattern=*.csv positions=positions.csv`
- Define aliases (optional):
  - `alias bs=depth temp=temp_water`
- Load and merge data:
  - `load` (uses current settings)
  - or `load dir=./data pattern=*.csv positions=positions.csv`
  - Position merging uses time-based interpolation to assign geo-coordinates to acoustic timestamps when they don't exactly match.
- Temporal aggregation:
  - `aggregate time 5min y=bs`  (omit `y=` to default to `depth`)
- Plot time series (optionally aggregate inline):
  - `plot y=bs 5min`
  - `plot scatter y=bs` (now supports custom x and y axes)
- Hexagon map:
  - `map hex y=bs res=8` (now supports interactive matplotlib and folium backends)
  - `map hex y=bs res=8 coastline=path/to/sweden_coastline.geojson` (overlay Sweden coastline from GeoJSON or shapefile)
- Descriptive statistics:
  - `stats columns=bs,temp`
- Help / Exit:
  - `help`  |  `exit`

Outputs are written to:
- Plots: `outputs/plots/*.png`
- Maps: `outputs/maps/*.html`
- Reports: `outputs/reports/*.txt`

## Configuration
Default settings live in `config/settings.yaml`. Key fields:
- `data.network_storage_path`: base folder for CSVs
- `data.acoustic_csv_pattern`: glob pattern for acoustic files
- `data.position_file`: path to positions CSV
- `processing.default_temporal_resolution`: default resample interval
- `processing.default_hex_resolution`: default H3 resolution

You can override these interactively with the `set` command.

## Data Columns
- Acoustic data (CSV): `timestamp` (parseable datetime), plus measurement columns like `depth`.
- Positions (CSV): `timestamp`, `latitude`, `longitude` (WGS84 decimal degrees).
- Positions now support SWEREF99 TM (EPSG:3006) coordinates (easting/northing) in addition to WGS84. The system stores both and uses SWEREF99 for analysis and matplotlib, WGS84 for H3 and web maps.

## Notes on Large Datasets
- The loader supports Dask for lazy loading, but the CLI currently loads eagerly by default for simplicity. If you need lazy loading, switch `lazy=True` in `AcousticsDataLoader.load_csv_files` or adapt the CLI.
- Consider converting to Parquet for faster I/O.

## Optional NLP Integration
This version includes a rule-based interpreter for common phrasing. You can now use flexible scatter/map commands:

- Scatter plot examples:
  - `scatter depth` (plots depth vs timestamp)
  - `scatter depth vs temperature` (plots depth vs temperature)
  - `scatter x:salinity y:depth` (plots depth vs salinity)
- Map examples:
  - `map depth` (matplotlib backend by default)
  - `map depth backend:folium` (uses folium)
  - `map depth resolution:9 agg:max`

Integration with LangChain + OpenAI can be added by extending `interface/nlp_interpreter.py` and configuring your API key.

## Troubleshooting
- If plots or maps don’t appear, check the console messages for the saved artifact paths.
- Ensure timestamps parse correctly; they should be in ISO format or detectable by Pandas.
- If hex maps show no polygons, verify that positions were merged (see match rate in logs).
- For contextily basemaps, ensure you have internet and `contextily` installed. If no basemap appears, the map will fall back to plain hexagons.
- For coordinate issues, check that your position file uses the correct CRS (WGS84 or SWEREF99) and update `config/settings.yaml` accordingly.

## License
Internal/research use. Add a license if you plan to distribute.

## Typical path for data and position files: 
load dir=./data/data pattern=SLUAquaSailor* positions=./positions/positions.txt


## Map Coastline Overlay (Sweden)

You can overlay the Sweden coastline on your maps by providing a GeoJSON or shapefile. Example usage:

```
map hex y=depth res=8 coastline=./data/geodata/CNTR_RG_20M_2024_4326.geojson


map hex y=depth res=7
map hex y=depth res=7 negative=true
map hex y=depth res=6 east_lim=[600000,720000] north_lim=[6650000,6800000]
map hex y=nasc0 res=6 east_lim=[600000,720000] north_lim=[6650000,6800000] max=1000
scatter nasc0 vs depth 10min max=100
scatter fish_depth0 vs depth 10min max=100

boxplot y:nasc0 x:northing xbins:10 ylog=true 

map hex y=depth res=7 max=50
map hex y=bottom_hardness negative=false res=7              # should revert to full data scale (no carry-over max)
map hex y=nasc0 res=7 max=1000
map hex y=nasc0 res=7 max=100      # colorbar rescales to 100
map hex y=depth negative:true      # legend label shows transformed column




```

This works for both matplotlib and folium backends. The coastline file can be in GeoJSON or shapefile format. If not provided, the map will be shown without the overlay.

## New Features (2026)

- **Custom scatter plot axes**: Specify both x and y columns for scatter plots. Example: `scatter depth vs temperature` or `scatter x:depth y:salinity`.
- **Interactive matplotlib maps**: Use `map <variable>` for interactive maps with pan/zoom and colorbar. Add `backend:folium` for HTML maps.
- **SWEREF99 coordinate support**: System now supports SWEREF99 TM (EPSG:3006) for analysis and mapping. Both WGS84 and SWEREF99 are stored and used as needed.
- **Coordinate info command**: Use `coords info` or `show coords` to display current coordinate system details.

Note: If you do use a broad pattern like `*.txt`, the CLI now automatically excludes the positions file from the acoustic inputs to prevent mixing. Prefer targeting only acoustic files (e.g., `*.csv` or a specific prefix) to ensure expected measurement columns (e.g., `depth`, `nasc0`) are present.


## Custom Variables (Aliases)
You can plot, map, aggregate, and compute stats on any column by defining your own CLI variables (aliases) or by using the raw column names directly.

- Define aliases:
  - `alias bs=depth temp=temp_water`
- Use aliases in commands:
  - Plot: `plot y=bs 5min`  (or `plot y=depth 5min` without alias)
  - Scatter: `plot scatter y=bs`
  - Aggregate: `aggregate time 5min y=bs`  (default is `depth` if `y` omitted)
  - Map: `map hex y=depth res=8`
  - Stats: `stats columns=depth,temp`

Notes:
- Aliases are session-scoped (they persist until you exit the CLI).
- If you prefer, you can skip `alias` entirely and pass the actual column name via `y=` and `columns=`.