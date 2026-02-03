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

- Acoustic CSVs: should include at minimum `timestamp` and your measurement column(s), e.g. `backscatter`.
- Position CSV (default `positions.csv`): must contain `timestamp`, `latitude`, `longitude` columns.
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
- Load and merge data:
  - `load` (uses current settings)
  - or `load dir=./data pattern=*.csv positions=positions.csv`
- Temporal aggregation:
  - `aggregate time 5min`
- Plot time series (optionally aggregate inline):
  - `plot y=backscatter 5min`
  - `plot scatter y=backscatter`
- Hexagon map:
  - `map hex y=backscatter res=8`
- Descriptive statistics:
  - `stats columns=backscatter`
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
