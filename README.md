# Acoustics Postprocessing System

A modular Python toolkit for loading, merging, aggregating, analyzing, plotting, and mapping acoustic depth data. It supports temporal aggregation, H3 hexagonal spatial aggregation, descriptive statistics, time series plots with smoothing, and interactive maps.

## Features
- Load many CSVs (supports network paths) and merge with timestamped positions
- Temporal aggregation with flexible intervals (e.g., 5min, 1h)
- Spatial aggregation using H3 hexagons at configurable resolution
- Time series and scatter plots with smoothing (LOWESS/Savitzky–Golay)
- Interactive hexagon map export (HTML)
- Descriptive statistics exported to text files
- **Outlier filtering** using Z-score method for cleaner plots and statistics
- **Calculated variables** for creating new columns (temporal features, arithmetic expressions) that persist in session
- **Time-aggregated statistics** with detailed output for temporal pattern analysis
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
  - `plot y=depth 5min outliers=zscore` (filter outliers, new in Feb 2026)
- Hexagon map:
  - `map hex y=bs res=8` (now supports interactive matplotlib and folium backends)
  - `map hex y=bs res=8 coastline=path/to/sweden_coastline.geojson` (overlay Sweden coastline from GeoJSON or shapefile)
- Descriptive statistics:
  - `stats columns=bs,temp`
  - `stats by time 10min columns=bs,temp` (time-aggregated stats, new in Feb 2026)
- Create calculated variables (new in Feb 2026):
  - `create hour from timestamp` (extract hour from timestamp)
  - `calc depth_m=depth/1000` (arithmetic expressions)
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
scatter nasc0 vs depth 10min max=10000 outliers=zscore ylog=true
scatter fish_depth0 vs depth 10min max=100 

map hex y=depth res=6 max=100
map hex y=bottom_hardness negative=false res=7              # should revert to full data scale (no carry-over max)
map hex y=nasc0 10min res=7 max=1000
map hex y=nasc0 res=7 max=100      # colorbar rescales to 100
map hex y=depth negative:true      # legend label shows transformed column

boxplot depth vs latitude          # depth vs latitude
boxplot nasc0 vs hour outliers=zscore z_thresh=3.0

# New features (Feb 2026):
create hour from timestamp                                  # Create temporal variable
stats by time 10min columns=depth,nasc0 outliers=zscore    # Time-aggregated stats
plot y=depth 5min outliers=zscore z_thresh=2.5             # Filter outliers in plots
calc depth_negative=depth*-1                               # Create calculated variable
scatter hour vs depth                                       # Plot using created variable

```

This works for both matplotlib and folium backends. The coastline file can be in GeoJSON or shapefile format. If not provided, the map will be shown without the overlay.

## New Features (2026)

- **Custom scatter plot axes**: Specify both x and y columns for scatter plots. Example: `scatter depth vs temperature` or `scatter x:depth y:salinity`.
- **Interactive matplotlib maps**: Use `map <variable>` for interactive maps with pan/zoom and colorbar. Add `backend:folium` for HTML maps.
- **SWEREF99 coordinate support**: System now supports SWEREF99 TM (EPSG:3006) for analysis and mapping. Both WGS84 and SWEREF99 are stored and used as needed.
- **Coordinate info command**: Use `coords info` or `show coords` to display current coordinate system details.
- **Outlier filtering (Feb 2026)**: Filter extreme values using Z-score method before plotting or computing statistics. Example: `plot y=depth outliers=zscore z_thresh=2.5`.
- **Calculated variables (Feb 2026)**: Create new variables from existing data that persist in the session. Extract temporal features (hour, day, month) or compute arithmetic expressions. Example: `create hour from timestamp` or `calc depth_m=depth/1000`.
- **Time-aggregated statistics (Feb 2026)**: Compute descriptive statistics for each time bin with long-format output. Example: `stats by time 10min columns=depth,nasc0 outliers=zscore`.

Note: If you do use a broad pattern like `*.txt`, the CLI now automatically excludes the positions file from the acoustic inputs to prevent mixing. Prefer targeting only acoustic files (e.g., `*.csv` or a specific prefix) to ensure expected measurement columns (e.g., `depth`, `nasc0`) are present.

## Advanced Features

### Outlier Filtering
Remove statistical outliers from your data before plotting or analysis using Z-score method:

```bash
# Filter outliers from time series plot (default threshold: 3.0)
plot y=depth 5min outliers=zscore

# Use custom Z-score threshold (more aggressive filtering)
plot y=nasc0 10min outliers=modified_zscore z_thresh=1000
plot y=nasc0 10min ylog=true outliers=modified_zscore z_thresh=10


# Combine with other transforms
scatter depth vs temperature outliers=modified_score z_thresh=2.0

# Filter outliers in maps
map nasc0 res=7 outliers=zscore

# Boxplot with outlier filtering
boxplot depth vs latitude outliers=zscore z_thresh=3.0
```

**How it works**: The Z-score method removes data points that are more than N standard deviations from the mean (default N=3.0). This happens before min/max thresholds and other transforms.

### Calculated Variables
Create new variables that persist throughout your session. Extract temporal features or compute arithmetic expressions:

```bash
# Extract temporal features from timestamp
create hour from timestamp        # Extract hour (0-23)
create day from timestamp         # Extract day of month (1-31)
create month from timestamp       # Extract month (1-12)
create dayofweek from timestamp   # Extract day of week (0=Monday, 6=Sunday)

# Arithmetic expressions using 'create var' or 'calc'
calc depth_m=depth/1000          # Convert depth to meters
calc nasc_log=nasc0+1            # Offset before log transform

# Echo integration calculations
calc abund_km2=(nasc0/(10**(-46.2/10)))/(1852*1852)  # sigma
calc tonnes_km2=abund_km2*0.0059*20**3.09/(1000*1000)

# Use calculated variables in subsequent commands
plot y=tonnes_km2 10min outliers=modified_zscore z_thresh=100                 # Plot by hour of day
boxplot nasc0 vs hour 30min logy=true outliers=modified_zscore z_thresh=100   # NASC0 vs hour
map bs_squared res=7             # Map the squared values
stats columns=hour,dayofweek     # Stats on temporal variables
```

**Notes**: 
- Variables persist until you exit the CLI
- Use `.dt.` accessor for datetime attributes: `create var custom=timestamp.dt.year`
- Arithmetic works with any numeric columns
- Once created, variables appear in `columns` output

### Time-Aggregated Statistics
Compute descriptive statistics for each time bin with detailed output:

```bash
# Basic time-aggregated stats (default 5min intervals)
stats by time 10min columns=depth

# Multiple columns
stats by time 5min columns=depth,nasc0,temperature

# With outlier filtering
stats by time 10min columns=depth outliers=zscore z_thresh=2.5

# With date filtering
stats by time 15min columns=nasc0 start_date=2025-10-23 end_date=2025-10-24

# Combine all filters
stats by time 5min columns=depth,nasc0 outliers=zscore start_date=2025-10-23
```

**Output format**:
- **Text file** (`outputs/reports/stats_by_time_<interval>.txt`): Human-readable with stats grouped by time
- **CSV file** (`outputs/reports/stats_by_time_<interval>.csv`): Long-format table for further analysis
  - Columns: `timestamp`, `variable`, `count`, `mean`, `std`, `min`, `p05`, `p25`, `median`, `p75`, `p95`, `max`, `missing`
  - Each row = one variable's stats for one time bin

Perfect for tracking how your data changes over time or identifying temporal patterns!


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



# Run examples
plot y=nasc0 outliers=zscore z_thresh=.01