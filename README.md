# Acoustics Postprocessing System

A modular Python toolkit for loading, merging, aggregating, analyzing, plotting, and mapping acoustic backscatter data. It supports temporal aggregation, H3 hexagonal spatial aggregation, descriptive statistics, time series plots with smoothing, and interactive maps.

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
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

Note: `geopandas` and `shapely` have prebuilt wheels for macOS. If installation fails, ensure you have an up-to-date pip (`pip install --upgrade pip`) and Xcode command line tools.

### 2) Prepare your data

- Acoustic CSVs: should include at minimum `timestamp` and your measurement column(s), e.g. `backscatter`. The CLI also accepts a column named `time` and normalizes it to `timestamp` automatically.
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
  - `alias bs=backscatter temp=temp_water`
- Load and merge data:
  - `load` (uses current settings)
  - or `load dir=./data pattern=*.csv positions=positions.csv`
  - Position merging uses time-based interpolation to assign geo-coordinates to acoustic timestamps when they don't exactly match.
- Temporal aggregation:
  - `aggregate time 5min y=bs`  (omit `y=` to default to `backscatter`)
- Plot time series (optionally aggregate inline):
  - `plot y=bs 5min`
  - `plot scatter y=bs`
- Hexagon map:
  - `map hex y=bs res=8`
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
- Acoustic data (CSV): `timestamp` (parseable datetime), plus measurement columns like `backscatter`.
- Positions (CSV): `timestamp`, `latitude`, `longitude` (WGS84 decimal degrees).

## Notes on Large Datasets
- The loader supports Dask for lazy loading, but the CLI currently loads eagerly by default for simplicity. If you need lazy loading, switch `lazy=True` in `AcousticsDataLoader.load_csv_files` or adapt the CLI.
- Consider converting to Parquet for faster I/O.

## Optional NLP Integration
This version includes a rule-based interpreter for common phrasing. Integration with LangChain + OpenAI can be added by extending `interface/nlp_interpreter.py` and configuring your API key.

## Troubleshooting
- If plots or maps don’t appear, check the console messages for the saved artifact paths.
- Ensure timestamps parse correctly; they should be in ISO format or detectable by Pandas.
- If hex maps show no polygons, verify that positions were merged (see match rate in logs).

## License
Internal/research use. Add a license if you plan to distribute.

## Typical path for data files: 
load dir=../../../../../../mnt/BSP_NAS2_work/Acoustics_output_data/Echopype_results/Finngrundet2025/csv/ data pattern=SLUAquaSailor2020V2-Phase0-*.csv

## Typical path for position files: 
load dir=./data pattern=*.txt positions=positions.txt


## Custom Variables (Aliases)
You can plot, map, aggregate, and compute stats on any column by defining your own CLI variables (aliases) or by using the raw column names directly.

- Define aliases:
  - `alias bs=backscatter temp=temp_water`
- Use aliases in commands:
  - Plot: `plot y=bs 5min`  (or `plot y=backscatter 5min` without alias)
  - Scatter: `plot scatter y=bs`
  - Aggregate: `aggregate time 5min y=bs`  (default is `backscatter` if `y` omitted)
  - Map: `map hex y=bs res=8`
  - Stats: `stats columns=bs,temp`

Notes:
- Aliases are session-scoped (they persist until you exit the CLI).
- If you prefer, you can skip `alias` entirely and pass the actual column name via `y=` and `columns=`.