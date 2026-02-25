# Implementation Plan: Acoustics Analysis System

## Overview

A modular Python system for processing acoustic backscatter data with flexible temporal/spatial aggregation, statistical analysis, mapping, and natural language interface. Built with Pandas/Dask for data handling, H3 for hexagonal gridding, and LLM integration for interactive commands.

## System Requirements

### Functional Requirements
- Load and combine multiple CSV files with acoustic backscatter measurements from network storage
- Merge timestamped acoustic data with geographic position data from separate files
- Handle high-resolution data (one point per 2 seconds) with large data gaps
- Provide flexible time-based aggregation (adjustable intervals)
- Provide spatial aggregation using hexagonal grids of configurable size
- Generate time series plots (line and scatter) with fitted smoothing lines
- Create maps with geo-aggregated data in hexagons
- Calculate descriptive statistics and save to text files
- Interactive system where user describes tasks in natural language

## Technology Stack

### Core Data Processing
- **Pandas** - CSV loading, time series operations, initial data merging
- **Dask** - Lazy loading for handling many large CSV files without memory overflow
- **NumPy** - Numerical operations and statistics

### Geospatial Operations
- **H3-py** (Uber's H3) - Hexagonal gridding with multiple resolution levels
- **GeoPandas** - Geospatial dataframe operations, coordinate handling
- **Shapely** - Geometric operations if needed

### Visualization
- **Matplotlib + Seaborn** - Time series and statistical plots, smoothing lines
- **Folium** or **Plotly** - Interactive maps with hexagonal overlays
- **SciPy** - Statistical smoothing (LOWESS, splines)

### Interactive Interface
- **LangChain + OpenAI/Anthropic API** - Natural language understanding for task interpretation
- **Rich** - Enhanced CLI with beautiful formatting
- **Jupyter Notebook** (optional) - Alternative interactive environment

### Data Management
- **PyYAML** - Configuration files
- **Pathlib** - Cross-platform path handling for network storage

## Project Structure

```
acoustics_postprocessing/
├── config/
│   └── settings.yaml              # Network paths, default parameters
├── data_loader/
│   ├── __init__.py
│   ├── csv_loader.py              # Dask-based CSV ingestion
│   ├── position_merger.py         # Time-based position matching
│   └── cache_manager.py           # Optional: cache merged data
├── aggregation/
│   ├── __init__.py
│   ├── temporal_aggregator.py     # Flexible time binning
│   └── spatial_aggregator.py      # H3 hexagonal gridding
├── analysis/
│   ├── __init__.py
│   ├── statistics.py              # Descriptive stats calculation
│   └── smoothing.py               # LOWESS, splines, rolling averages
├── visualization/
│   ├── __init__.py
│   ├── time_series_plots.py       # Line/scatter plots
│   └── map_generator.py           # Hexagonal map visualization
├── interface/
│   ├── __init__.py
│   ├── nlp_interpreter.py         # Parse natural language commands
│   ├── task_executor.py           # Execute interpreted tasks
│   └── cli.py                     # Main interactive loop
├── utils/
│   ├── __init__.py
│   ├── validators.py              # Data validation
│   └── io_helpers.py              # File I/O utilities
├── main.py                        # Entry point
├── requirements.txt
└── README.md
```

## Module Specifications

### 1. Data Loader Module (`data_loader/`)

**Purpose:** Efficient data ingestion from network storage with position merging

**Components:**

#### `csv_loader.py`
- **Class:** `AcousticsDataLoader`
- **Methods:**
  - `load_csv_files(file_paths: List[Path], lazy: bool = True) -> dask.DataFrame`
    - Load multiple CSV files using Dask for memory efficiency
    - Support glob patterns for bulk file discovery
    - Progress tracking with Rich progress bars
    - Schema validation and type inference
  - `get_file_list(root_dir: Path, pattern: str) -> List[Path]`
    - Discover CSV files in network storage
    - Handle network path errors gracefully
- **Key Features:**
  - Chunked reading to avoid memory overflow
  - Automatic date parsing for timestamp columns
  - Duplicate detection and removal options
  - Configurable column name mapping

#### `position_merger.py`
- **Class:** `PositionMerger`
- **Methods:**
  - `merge_positions(acoustic_data: pd.DataFrame, position_data: pd.DataFrame, tolerance: str = '5s') -> pd.DataFrame`
    - Time-based merge using `pd.merge_asof()`
    - Configurable time tolerance for nearest-neighbor matching
    - Handle timezone-aware timestamps
    - Flag records with no position match
  - `interpolate_positions(data: pd.DataFrame, method: str = 'linear') -> pd.DataFrame`
    - Optional: fill small position gaps with interpolation
- **Key Features:**
  - Efficient temporal join algorithm
  - Quality metrics (match rate, gap distribution)
  - Support for multiple position file formats

#### `cache_manager.py`
- **Class:** `CacheManager`
- **Methods:**
  - `save_to_cache(data: pd.DataFrame, cache_key: str) -> None`
    - Save processed data to Parquet format
    - Generate cache keys based on input file hashes
  - `load_from_cache(cache_key: str) -> Optional[pd.DataFrame]`
    - Load cached data if available and valid
  - `clear_cache(older_than: timedelta = None) -> None`
    - Manage cache storage
- **Key Features:**
  - 10x faster reads with Parquet vs CSV
  - Automatic cache invalidation
  - Configurable cache directory

### 2. Aggregation Module (`aggregation/`)

**Purpose:** Temporal and spatial data transformation

**Components:**

#### `temporal_aggregator.py`
- **Class:** `TemporalAggregator`
- **Methods:**
  - `aggregate_by_time(data: pd.DataFrame, interval: str, agg_func: Dict[str, str]) -> pd.DataFrame`
    - Resample to configurable intervals (e.g., '1min', '5min', '1h')
    - Support multiple aggregation functions per column (mean, median, std, count)
    - Handle data gaps explicitly
  - `apply_rolling_window(data: pd.DataFrame, window: str) -> pd.DataFrame`
    - Rolling aggregations for smoothing
- **Key Features:**
  - Pandas resample functionality
  - Gap-aware aggregation (report coverage)
  - Preserve metadata about aggregation parameters

#### `spatial_aggregator.py`
- **Class:** `SpatialAggregator`
- **Methods:**
  - `assign_hex_ids(data: pd.DataFrame, resolution: int) -> pd.DataFrame`
    - Convert lat/lon to H3 hexagon IDs
    - Support H3 resolutions 0-15 (1000km to 1km cells)
  - `aggregate_by_hex(data: pd.DataFrame, agg_func: Dict[str, str]) -> gpd.GeoDataFrame`
    - Group by hex ID and aggregate
    - Return GeoDataFrame with hex geometries
  - `get_hex_statistics(hex_data: gpd.GeoDataFrame) -> pd.DataFrame`
    - Summary stats per hexagon (sample size, coverage, etc.)
- **Key Features:**
  - H3 library integration for fast hexagonal gridding
  - Multiple resolution support
  - Export hexagon centroids and boundaries

### 3. Analysis Module (`analysis/`)

**Purpose:** Statistical computation and smoothing

**Components:**

#### `statistics.py`
- **Class:** `StatisticsCalculator`
- **Methods:**
  - `calculate_descriptive_stats(data: pd.DataFrame, columns: List[str]) -> pd.DataFrame`
    - Mean, median, std, min, max, percentiles (5, 25, 75, 95)
    - Count, missing values
    - Confidence intervals where applicable
  - `save_stats_to_file(stats: pd.DataFrame, output_path: Path) -> None`
    - Export to formatted text files
    - Include metadata (timestamp, data source info)
  - `detect_outliers(data: pd.DataFrame, method: str = 'iqr') -> pd.DataFrame`
    - Identify outliers using IQR or z-score methods
- **Key Features:**
  - Robust statistics (resistant to outliers)
  - Formatted output for reports
  - Data quality metrics (gap sizes, coverage)

#### `smoothing.py`
- **Class:** `DataSmoother`
- **Methods:**
  - `apply_lowess(data: pd.Series, frac: float = 0.1) -> pd.Series`
    - Locally weighted scatterplot smoothing
  - `apply_savgol(data: pd.Series, window: int, polyorder: int) -> pd.Series`
    - Savitzky-Golay filter for smooth derivatives
  - `apply_rolling_average(data: pd.Series, window: str) -> pd.Series`
    - Simple moving average
  - `fit_spline(x: pd.Series, y: pd.Series, smoothing: float = None) -> Callable`
    - Cubic spline interpolation
- **Key Features:**
  - Multiple smoothing algorithms
  - Configurable parameters
  - Handle missing values appropriately

### 4. Visualization Module (`visualization/`)

**Purpose:** Generate plots and maps

**Components:**

#### `time_series_plots.py`
- **Class:** `TimeSeriesPlotter`
- **Methods:**
  - `plot_line_series(data: pd.DataFrame, x: str, y: Union[str, List[str]], smooth: bool = True) -> Figure`
    - Line plots with optional smoothing overlay
    - Support multiple series
    - Configurable styling
  - `plot_scatter(data: pd.DataFrame, x: str, y: str, hue: str = None) -> Figure`
    - Scatter plots with optional color grouping
    - Add fitted smoothing curves
  - `save_plot(fig: Figure, output_path: Path, format: str = 'png') -> None`
    - Export to PNG, SVG, or PDF
- **Key Features:**
  - Publication-quality figures
  - Automatic legend and axis labels
  - Gap visualization in time series
  - Configurable figure size and DPI

#### `map_generator.py`
- **Class:** `HexagonalMapGenerator`
- **Methods:**
  - `create_hexagon_map(hex_data: gpd.GeoDataFrame, value_column: str, center: Tuple[float, float] = None) -> folium.Map`
    - Interactive map with hexagonal overlay
    - Color hexagons by aggregated values
    - Configurable color scheme
  - `add_colorbar(map_obj: folium.Map, values: pd.Series, cmap: str) -> folium.Map`
    - Add legend/colorbar
  - `save_map(map_obj: folium.Map, output_path: Path) -> None`
    - Export to HTML
- **Key Features:**
  - Interactive zoom and pan
  - Tooltip with hexagon statistics
  - Multiple basemap options (OpenStreetMap, satellite)
  - Export to standalone HTML

### 5. Interface Module (`interface/`)

**Purpose:** Natural language command interpretation and execution

**Components:**

#### `nlp_interpreter.py`
- **Class:** `CommandInterpreter`
- **Methods:**
  - `parse_command(user_input: str) -> Dict[str, Any]`
    - Use LangChain + LLM to interpret natural language
    - Extract task type, parameters, and options
    - Return structured command dictionary
  - `validate_command(command: Dict) -> Tuple[bool, str]`
    - Check if command is valid and complete
    - Request missing parameters if needed
- **Key Features:**
  - Few-shot prompting with examples
  - Context retention across conversation
  - Clarification questions for ambiguous requests
  - Support for command chaining

**Example Command Parsing:**
```
User: "Plot acoustic backscatter over time with 5-minute averages"
Parsed: {
  "task": "time_series_plot",
  "aggregation": {"temporal": "5min"},
  "plot_type": "line",
  "y_column": "backscatter",
  "smooth": False
}
```

#### `task_executor.py`
- **Class:** `TaskExecutor`
- **Methods:**
  - `execute(command: Dict) -> ExecutionResult`
    - Orchestrate module calls based on command
    - Handle errors gracefully
    - Return results and metadata
  - `dry_run(command: Dict) -> str`
    - Preview what will be executed
    - Estimate execution time and memory
- **Key Features:**
  - Pipeline construction from commands
  - Progress reporting
  - Error recovery and suggestions

#### `cli.py`
- **Function:** `main()`
- **Features:**
  - Interactive REPL loop
  - Command history
  - Rich formatting for output
  - Help system with examples
  - Configuration management

### 6. Utilities Module (`utils/`)

**Purpose:** Cross-cutting concerns

**Components:**

#### `validators.py`
- **Functions:**
  - `validate_csv_schema(df: pd.DataFrame, required_columns: List[str]) -> bool`
  - `validate_timestamps(df: pd.DataFrame, time_column: str) -> Tuple[bool, List[str]]`
  - `validate_coordinates(df: pd.DataFrame, lat_col: str, lon_col: str) -> Tuple[bool, List[str]]`
  - `check_data_gaps(df: pd.DataFrame, time_column: str, expected_freq: str) -> pd.DataFrame`

#### `io_helpers.py`
- **Functions:**
  - `read_config(config_path: Path) -> Dict`
  - `setup_logging(log_level: str, log_file: Path) -> None`
  - `ensure_directory(path: Path) -> None`
  - `safe_network_read(path: Path, retry: int = 3) -> Any`

## Configuration (`config/settings.yaml`)

```yaml
data:
  network_storage_path: "/path/to/network/storage"
  acoustic_csv_pattern: "acoustic_*.csv"
  position_file: "positions.csv"
  cache_directory: "./cache"
  
processing:
  default_temporal_resolution: "5min"
  default_hex_resolution: 8  # ~0.5km cells
  time_merge_tolerance: "5s"
  
analysis:
  outlier_method: "iqr"
  smoothing_method: "lowess"
  lowess_fraction: 0.1
  
visualization:
  default_colormap: "viridis"
  figure_dpi: 300
  map_basemap: "OpenStreetMap"
  
interface:
  llm_provider: "openai"  # or "anthropic"
  api_key_env_var: "OPENAI_API_KEY"
  command_history_file: ".command_history"
  
logging:
  level: "INFO"
  file: "acoustics_analysis.log"
```

## Implementation Phases

### Phase 1: Core Data Processing (Priority 1)
**Goal:** Load, merge, and aggregate data

**Tasks:**
1. Set up project structure and `requirements.txt`
2. Implement `csv_loader.py` with Dask integration
3. Implement `position_merger.py` with temporal join
4. Implement `temporal_aggregator.py`
5. Implement `spatial_aggregator.py` with H3
6. Add basic validators and error handling
7. Write unit tests for each component

**Deliverables:**
- Working data pipeline from CSV to aggregated dataframes
- Command-line script for testing (without NLP)

### Phase 2: Analysis & Visualization (Priority 2)
**Goal:** Generate outputs

**Tasks:**
1. Implement `statistics.py` with descriptive stats
2. Implement `smoothing.py` with multiple algorithms
3. Implement `time_series_plots.py` with Matplotlib
4. Implement `map_generator.py` with Folium
5. Add output export functionality
6. Write visualization tests

**Deliverables:**
- Statistical reports saved to text files
- Time series plots with smoothing
- Interactive hexagonal maps

### Phase 3: Natural Language Interface (Priority 3)
**Goal:** Interactive user experience

**Tasks:**
1. Set up LangChain with chosen LLM provider
2. Implement `nlp_interpreter.py` with few-shot examples
3. Implement `task_executor.py` for workflow orchestration
4. Implement `cli.py` with Rich formatting
5. Add command history and help system
6. User testing and refinement

**Deliverables:**
- Fully interactive CLI accepting natural language
- Documentation with example commands

### Phase 4: Optimization & Polish (Priority 4)
**Goal:** Production-ready system

**Tasks:**
1. Implement caching system for performance
2. Add comprehensive error handling
3. Profile and optimize memory usage
4. Create user documentation
5. Add example datasets and tutorials
6. Package for distribution

## Key Implementation Considerations

### Memory Management
- **Use Dask for lazy loading** - Only load data into memory when needed
- **Implement chunked processing** - Process large files in batches
- **Consider Parquet for intermediate storage** - 10x faster than CSV
- **Use categorical dtypes** - Save memory for repeated string values
- **Profile memory usage** - Use memory_profiler to identify bottlenecks

### Time Series Alignment
- **Large data gaps require careful handling**
- **Use `pd.merge_asof()` for efficient temporal joins**
- **Set appropriate time tolerance** - Balance between precision and match rate
- **Handle timezone-aware timestamps consistently**
- **Consider interpolation strategies** - But document assumptions

### Hexagonal Gridding
- **H3 provides 15 resolution levels** - From ~1km to ~1000km cell edges
- **Pre-calculate hex IDs for all positions** - Then group by hex for aggregation
- **Store resolution as parameter** - Allow users to experiment
- **Support multiple aggregation functions** - Mean, median, count, std, etc.

### User Interface Design
- **Two-tier architecture:**
  1. Structured Python API for programmatic use
  2. NLP wrapper for natural language interaction
- **Use few-shot prompting** - Provide examples to guide LLM
- **Validate interpreted commands** - Prevent errors from misinterpretation
- **Provide dry-run mode** - Show what will be executed before running
- **Save command history** - Enable reproducibility

### Statistical Robustness
- **Handle outliers explicitly** - Offer median/percentile options
- **Provide confidence intervals** - Where statistically appropriate
- **Report data quality metrics** - Gap sizes, sample sizes, coverage
- **Document assumptions** - Especially for smoothing and aggregation

## Decision Points

### 1. Caching Strategy
**Question:** Should intermediate results be cached to disk?

**Options:**
- **Always cache** - Faster repeated analysis, requires storage management
- **Optional caching** - User decides, more flexible
- **No caching** - Always process from source, simpler but slower

**Recommendation:** Optional caching with automatic invalidation

### 2. NLP Provider
**Question:** Which LLM provider to use for natural language interface?

**Options:**
- **OpenAI GPT-4** - Best performance, requires API key and costs money
- **Anthropic Claude** - Similar quality, different pricing
- **Local open-source model** - Free but requires more setup and less capable

**Recommendation:** OpenAI GPT-4 for best results, with provider as configurable option

### 3. Development Approach
**Question:** Build incrementally or prototype first?

**Options:**
- **Phased approach** - Build Phase 1 → 2 → 3, more robust
- **End-to-end prototype** - Quick feedback, more refactoring later

**Recommendation:** Phased approach with minimal working examples at each phase

### 4. Map Visualization Library
**Question:** Folium or Plotly for hexagonal maps?

**Options:**
- **Folium** - Simpler for geospatial data, exports to standalone HTML
- **Plotly** - More interactive features, better for dashboards

**Recommendation:** Folium for simplicity, Plotly as optional upgrade

## Testing Strategy

### Unit Tests
- Test each module independently
- Mock external dependencies (file I/O, LLM calls)
- Test edge cases (empty data, missing columns, extreme values)

### Integration Tests
- Test full pipeline from CSV to output
- Test with realistic data sizes
- Test error handling and recovery

### Performance Tests
- Benchmark with various data volumes
- Profile memory usage
- Test network storage access speed

## Documentation Requirements

1. **README.md** - Overview, installation, quick start
2. **API Documentation** - Docstrings for all public methods
3. **User Guide** - Example workflows and common tasks
4. **Configuration Guide** - Explain all settings
5. **Example Notebooks** - Jupyter notebooks with tutorials

## Success Criteria

- ✅ Load and merge 1000+ CSV files without memory errors
- ✅ Process high-resolution data (1 point per 2 seconds) efficiently
- ✅ Generate time series plots with smoothing in <30 seconds
- ✅ Create hexagonal maps at multiple resolutions
- ✅ Calculate and export statistics accurately
- ✅ Interpret 90%+ of common natural language commands correctly
- ✅ Handle data gaps gracefully with appropriate warnings
- ✅ Run interactively with <2 second response time for most commands
