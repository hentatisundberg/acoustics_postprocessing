# Implementation Plan: Major System Changes

**Date**: February 4, 2026  
**Implementation Order**: Change #3 → Change #2 → Change #1  
**Coordinate System**: SWEREF99 TM (EPSG:3006)  
**Coordinate Naming**: easting/northing  
**Dependencies**: contextily for basemaps, pyproj for coordinate transforms

---

## Overview

This document provides a detailed implementation plan for three major system enhancements:

1. **Change #3**: Enable custom X and Y axes for scatter plots (PRIORITY 1 - Easiest)
2. **Change #2**: Add interactive matplotlib maps with pan/zoom and color scale (PRIORITY 2 - Moderate)
3. **Change #1**: Add SWEREF99 coordinate system support (PRIORITY 3 - Most Complex)

---

## CHANGE #3: Custom Scatter Plot Axes

**Priority**: Implement First  
**Complexity**: Low  
**Risk**: Minimal  
**Estimated Effort**: 1-2 hours

### Current Behavior
- Scatter plots always use 'timestamp' as X-axis
- Only Y-axis is configurable via user command
- Method `plot_scatter()` in `time_series_plots.py` already accepts X parameter but it's never used

### Desired Behavior
- Users can specify both X and Y columns for scatter plots
- Command example: `"scatter depth vs temperature"` or `"scatter x:depth y:salinity"`
- Default to 'timestamp' for X-axis if not specified (backward compatible)

### Files to Modify

#### 1. `interface/nlp_interpreter.py`

**Location**: Method `_parse_command()`, scatter_plot task handling (~line 160-170)

**Current Pattern**:
```python
if "scatter" in s:
    y = self._find_param(raw, ["y", "variable", "column"])
    # ... other parameters ...
    return {"task": "scatter_plot", "y": y, **base}
```

**New Implementation**:
```python
if "scatter" in s:
    # Extract Y parameter (required)
    y = self._find_param(raw, ["y", "variable", "column"])
    
    # Extract X parameter (optional, defaults to timestamp)
    x = self._find_param(raw, ["x"])
    if not x:
        # Check for "vs" syntax: "scatter depth vs temperature"
        vs_match = re.search(r'scatter\s+(\w+)\s+vs\s+(\w+)', raw, re.IGNORECASE)
        if vs_match:
            y = vs_match.group(1)
            x = vs_match.group(2)
        else:
            x = "timestamp"  # default
    
    # ... extract other parameters (interval, smooth, show, save, out) ...
    
    return {"task": "scatter_plot", "x": x, "y": y, **base}
```

**Testing Commands**:
- `"scatter depth"` → x=timestamp, y=depth (backward compatible)
- `"scatter y:depth x:temperature"` → x=temperature, y=depth
- `"scatter depth vs temperature"` → x=temperature, y=depth
- `"scatter x:salinity y:depth"` → x=salinity, y=depth

---

#### 2. `interface/task_executor.py`

**Location**: Method `_plot_scatter()` (~line 300-320)

**Current Signature**:
```python
def _plot_scatter(self, y, interval, smooth, show, save, out):
    # ...
    fig = self.plotter.plot_scatter(df, x="timestamp", y=y, ...)
```

**New Implementation**:
```python
def _plot_scatter(self, x, y, interval, smooth, show, save, out):
    """Execute scatter plot task with custom x and y axes."""
    if self.merged_df is None:
        return "No data loaded. Load data and merge with positions first."
    
    if not y:
        return "No Y column specified."
    
    # Resolve Y column through aliases
    y_col = self._resolve_column(y)
    if y_col not in self.merged_df.columns:
        return f"Column '{y}' not found. Available: {list(self.merged_df.columns)}"
    
    # Resolve X column through aliases (default to timestamp)
    x = x or "timestamp"
    x_col = self._resolve_column(x)
    if x_col not in self.merged_df.columns:
        return f"Column '{x}' not found. Available: {list(self.merged_df.columns)}"
    
    # Apply temporal aggregation if specified
    df = self._apply_interval(self.merged_df, interval)
    
    # Generate plot
    try:
        fig = self.plotter.plot_scatter(
            df,
            x=x_col,
            y=y_col,
            smooth_method=smooth,
            title=f"{y_col} vs {x_col}"
        )
        
        # Handle show/save
        if save or out:
            path = self._generate_output_path(out, "scatter", f"{y_col}_vs_{x_col}")
            fig.savefig(path, dpi=300, bbox_inches='tight')
            result = f"Scatter plot saved to {path}"
        else:
            result = f"Scatter plot created: {y_col} vs {x_col}"
        
        if show:
            plt.show()
        else:
            plt.close(fig)
        
        return result
        
    except Exception as e:
        return f"Error creating scatter plot: {str(e)}"
```

**Also update the execute_task() method** to pass x parameter:
```python
elif task == "scatter_plot":
    return self._plot_scatter(
        x=params.get("x"),  # Add this
        y=params.get("y"),
        interval=params.get("interval"),
        smooth=params.get("smooth"),
        show=params.get("show"),
        save=params.get("save"),
        out=params.get("out")
    )
```

---

#### 3. `interface/cli.py`

**Location**: Method `_get_help_text()` (~line 100-150)

**Find the scatter_plot section and update**:
```python
scatter_plot: Create scatter plot (default x=timestamp)
  - scatter y:<column> [x:<column>]
  - scatter <column>
  - scatter <y_col> vs <x_col>
  Examples:
    - scatter depth (plots depth vs timestamp)
    - scatter y:salinity x:temperature
    - scatter depth vs temperature
```

---

#### 4. `visualization/time_series_plots.py`

**Verification Only** - This method already accepts `x` parameter! Just verify it uses it correctly.

**Current signature** (~line 80):
```python
def plot_scatter(self, df, x="timestamp", y=None, smooth_method=None, title=None):
```

✅ Already correct - no changes needed!

---

### Testing Checklist for Change #3

- [ ] Load data and merge positions
- [ ] Test: `scatter depth` → plots depth vs timestamp (backward compatible)
- [ ] Test: `scatter depth vs salinity` → plots depth vs salinity
- [ ] Test: `scatter x:temperature y:depth` → plots depth vs temperature
- [ ] Test invalid column: `scatter x:invalid y:depth` → clear error message
- [ ] Test missing Y: should error gracefully
- [ ] Verify plot titles show correct "Y vs X"
- [ ] Test save functionality: `scatter depth vs temp save`

---

## CHANGE #2: Interactive Matplotlib Maps

**Priority**: Implement Second  
**Complexity**: Moderate  
**Risk**: Low (additive, doesn't break existing Folium maps)  
**Estimated Effort**: 4-6 hours

### Current Behavior
- Maps are generated as Folium HTML files
- Static, saved to disk, opens in browser
- No colorbar/legend

### Desired Behavior
- Option to generate matplotlib-based interactive maps
- Pan/zoom capability via matplotlib interactive window
- Colorbar showing value scale
- Optional basemap tiles via contextily
- Folium backend still available

### Design Decisions

- Add `map_backend` parameter: `"folium"` or `"matplotlib"`
- Default to matplotlib for desktop use
- Use contextily for background tiles (requires internet)
- Fall back to plain hexagons if contextily unavailable

---

### Files to Modify

#### 1. `requirements.txt`

**Add**:
```
contextily>=1.3.0
```

---

#### 2. `config/settings.yaml`

**Add new section** (around line 20-30):
```yaml
visualization:
  colormap: "viridis"  # Already exists
  dpi: 300  # Already exists
  
  # New map settings
  map:
    default_backend: "matplotlib"  # "matplotlib" or "folium"
    show_colorbar: true
    use_basemap: true  # Use contextily basemap tiles
    basemap_source: "OpenStreetMap.Mapnik"  # Or "Stamen.Terrain", etc.
    basemap_zoom: "auto"  # Or integer 10-15
    hex_edge_color: "none"  # Edge color for hexagons
    hex_alpha: 0.7  # Transparency for hexagons
```

---

#### 3. `visualization/map_generator.py`

**Add new method** after existing `create_map()` method:

```python
def create_matplotlib_map(
    self,
    df,
    hex_col,
    value_col,
    agg_func="mean",
    title=None,
    use_basemap=True,
    show_colorbar=True,
    cmap="viridis",
    hex_alpha=0.7,
    hex_edge_color='none',
    figsize=(12, 10)
):
    """
    Create interactive matplotlib map with hexagons and optional basemap.
    
    Parameters
    ----------
    df : DataFrame
        Data with hexagon IDs and values
    hex_col : str
        Column containing H3 hex IDs
    value_col : str
        Column to visualize
    agg_func : str
        Aggregation function for values per hex
    title : str, optional
        Map title
    use_basemap : bool
        Whether to add contextily basemap
    show_colorbar : bool
        Whether to show colorbar
    cmap : str
        Matplotlib colormap name
    hex_alpha : float
        Hexagon transparency (0-1)
    hex_edge_color : str
        Edge color for hexagons
    figsize : tuple
        Figure size (width, height)
    
    Returns
    -------
    fig : matplotlib.figure.Figure
        The generated figure
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.collections import PatchCollection
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable
    import h3
    import numpy as np
    
    # Try to import contextily for basemap
    contextily_available = False
    if use_basemap:
        try:
            import contextily as ctx
            contextily_available = True
        except ImportError:
            print("Warning: contextily not available. Map will be created without basemap.")
            contextily_available = False
    
    # Aggregate data by hexagon
    grouped = df.groupby(hex_col)[value_col].agg(agg_func).reset_index()
    
    if grouped.empty:
        raise ValueError(f"No data to plot for {value_col}")
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=figsize)
    
    # Prepare hexagon polygons
    patches = []
    values = []
    
    for _, row in grouped.iterrows():
        hex_id = row[hex_col]
        value = row[value_col]
        
        # Get hexagon boundary (returns list of (lat, lon) tuples)
        boundary = h3.h3_to_geo_boundary(hex_id, geo_json=True)
        
        # boundary is in (lon, lat) order with geo_json=True
        coords = boundary
        
        # Create polygon patch
        polygon = mpatches.Polygon(coords, closed=True)
        patches.append(polygon)
        values.append(value)
    
    # Normalize values for colormap
    norm = Normalize(vmin=min(values), vmax=max(values))
    cmap_obj = plt.get_cmap(cmap)
    
    # Create PatchCollection with colors
    collection = PatchCollection(
        patches,
        cmap=cmap_obj,
        norm=norm,
        alpha=hex_alpha,
        edgecolor=hex_edge_color,
        linewidth=0.5 if hex_edge_color != 'none' else 0
    )
    collection.set_array(values)
    
    # Add collection to axis
    ax.add_collection(collection)
    
    # Set axis limits based on data
    all_coords = []
    for patch in patches:
        all_coords.extend(patch.get_path().vertices)
    all_coords = np.array(all_coords)
    
    margin = 0.02  # 2% margin around data
    lon_range = all_coords[:, 0].max() - all_coords[:, 0].min()
    lat_range = all_coords[:, 1].max() - all_coords[:, 1].min()
    
    ax.set_xlim(
        all_coords[:, 0].min() - margin * lon_range,
        all_coords[:, 0].max() + margin * lon_range
    )
    ax.set_ylim(
        all_coords[:, 1].min() - margin * lat_range,
        all_coords[:, 1].max() + margin * lat_range
    )
    
    # Add basemap if requested and available
    if use_basemap and contextily_available:
        try:
            ax.set_aspect('equal')
            ctx.add_basemap(
                ax,
                crs="EPSG:4326",  # Input CRS (WGS84)
                source=ctx.providers.OpenStreetMap.Mapnik,
                attribution=False
            )
        except Exception as e:
            print(f"Warning: Could not add basemap: {e}")
    
    # Add colorbar
    if show_colorbar:
        sm = ScalarMappable(cmap=cmap_obj, norm=norm)
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, orientation='vertical', pad=0.02, fraction=0.046)
        cbar.set_label(value_col, rotation=270, labelpad=20)
    
    # Set labels and title
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title(title or f"Map of {value_col} (aggregated by {agg_func})")
    ax.set_aspect('equal')
    
    # Enable grid
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
    
    plt.tight_layout()
    
    return fig
```

---

**Also update existing `create_map()` method** to route to backends:

```python
def create_map(
    self,
    df,
    hex_col,
    value_col,
    agg_func="mean",
    title=None,
    backend="matplotlib",
    **kwargs
):
    """
    Create a map visualization.
    
    Parameters
    ----------
    df : DataFrame
        Data with hexagon IDs and values
    hex_col : str
        Column containing H3 hex IDs
    value_col : str
        Column to visualize
    agg_func : str
        Aggregation function
    title : str, optional
        Map title
    backend : str
        Map backend: "matplotlib" or "folium"
    **kwargs
        Additional parameters passed to backend-specific method
    
    Returns
    -------
    map_object
        Folium map or matplotlib figure depending on backend
    """
    if backend == "matplotlib":
        # Get defaults from config
        use_basemap = kwargs.get('use_basemap', self.settings.get('visualization', {}).get('map', {}).get('use_basemap', True))
        show_colorbar = kwargs.get('show_colorbar', self.settings.get('visualization', {}).get('map', {}).get('show_colorbar', True))
        cmap = kwargs.get('cmap', self.settings.get('visualization', {}).get('colormap', 'viridis'))
        hex_alpha = kwargs.get('hex_alpha', self.settings.get('visualization', {}).get('map', {}).get('hex_alpha', 0.7))
        hex_edge_color = kwargs.get('hex_edge_color', self.settings.get('visualization', {}).get('map', {}).get('hex_edge_color', 'none'))
        
        return self.create_matplotlib_map(
            df=df,
            hex_col=hex_col,
            value_col=value_col,
            agg_func=agg_func,
            title=title,
            use_basemap=use_basemap,
            show_colorbar=show_colorbar,
            cmap=cmap,
            hex_alpha=hex_alpha,
            hex_edge_color=hex_edge_color
        )
    
    elif backend == "folium":
        return self.create_folium_map(
            df=df,
            hex_col=hex_col,
            value_col=value_col,
            agg_func=agg_func,
            title=title
        )
    
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'matplotlib' or 'folium'")


def create_folium_map(self, df, hex_col, value_col, agg_func="mean", title=None):
    """Original Folium map creation (renamed from create_map)."""
    # ... keep all existing Folium implementation ...
    # (just rename the method if it doesn't already have this name)
```

---

#### 4. `interface/nlp_interpreter.py`

**Location**: Map command parsing (~line 200-220)

**Update the map parsing section**:
```python
if "map" in s:
    var = self._find_param(raw, ["variable", "column", "of"])
    res = self._find_param(raw, ["resolution", "res"])
    agg = self._find_param(raw, ["agg", "aggregation"]) or "mean"
    show = "show" in s or "display" in s
    save = "save" in s
    out = self._find_param(raw, ["out", "output"])
    
    # Extract backend parameter
    backend = None
    if "matplotlib" in s or "mpl" in s:
        backend = "matplotlib"
    elif "folium" in s or "html" in s:
        backend = "folium"
    # If not specified, will use default from config
    
    return {
        "task": "map",
        "variable": var,
        "resolution": res,
        "agg": agg,
        "show": show,
        "save": save,
        "out": out,
        "backend": backend
    }
```

---

#### 5. `interface/task_executor.py`

**Location**: Method `_create_map()` (~line 350-400)

**Update to handle both backends**:
```python
def _create_map(self, variable, resolution, agg, show, save, out, backend=None):
    """Execute map creation task."""
    if self.merged_df is None:
        return "No data loaded. Load and merge with positions first."
    
    if not variable:
        return "No variable specified for mapping."
    
    # Resolve variable through aliases
    var_col = self._resolve_column(variable)
    if var_col not in self.merged_df.columns:
        return f"Column '{variable}' not found."
    
    # Check for required lat/lon columns
    required_cols = ['latitude', 'longitude']
    if not all(col in self.merged_df.columns for col in required_cols):
        return f"Position data required. Missing columns: {required_cols}"
    
    # Determine backend
    if backend is None:
        backend = self.settings.get('visualization', {}).get('map', {}).get('default_backend', 'matplotlib')
    
    try:
        # Create spatial aggregation
        hex_df = self.spatial_agg.aggregate_to_hexagons(
            self.merged_df,
            value_col=var_col,
            resolution=resolution or 8,
            agg_func=agg
        )
        
        # Generate map with selected backend
        map_obj = self.map_gen.create_map(
            df=hex_df,
            hex_col='hex_id',
            value_col=var_col,
            agg_func=agg,
            title=f"Map of {var_col}",
            backend=backend
        )
        
        # Handle show/save based on backend
        if backend == "folium":
            # Folium map (HTML)
            if save or out:
                path = self._generate_output_path(out, "map", f"{var_col}_map", ext=".html")
                map_obj.save(path)
                result = f"Map saved to {path}"
            else:
                result = "Folium map created (not saved)"
            
            if show:
                import webbrowser
                import tempfile
                if not (save or out):
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                        map_obj.save(f.name)
                        path = f.name
                webbrowser.open(f'file://{path}')
        
        elif backend == "matplotlib":
            # Matplotlib map
            if save or out:
                path = self._generate_output_path(out, "map", f"{var_col}_map", ext=".png")
                map_obj.savefig(path, dpi=300, bbox_inches='tight')
                result = f"Map saved to {path}"
            else:
                result = f"Map created for {var_col}"
            
            if show:
                import matplotlib.pyplot as plt
                plt.show()
            else:
                import matplotlib.pyplot as plt
                plt.close(map_obj)
        
        return result
        
    except Exception as e:
        return f"Error creating map: {str(e)}"
```

**Also update execute_task()** to pass backend parameter:
```python
elif task == "map":
    return self._create_map(
        variable=params.get("variable"),
        resolution=params.get("resolution"),
        agg=params.get("agg"),
        show=params.get("show"),
        save=params.get("save"),
        out=params.get("out"),
        backend=params.get("backend")  # Add this
    )
```

---

#### 6. `interface/cli.py`

**Update help text**:
```python
map: Create spatial map (default: matplotlib backend)
  - map <variable> [resolution:<n>] [agg:<func>] [backend:matplotlib|folium]
  Examples:
    - map depth (interactive matplotlib map)
    - map salinity resolution:9 (higher resolution hexagons)
    - map temperature backend:folium (HTML map for sharing)
    - map depth agg:max save (save matplotlib map as PNG)
```

---

### Testing Checklist for Change #2

- [ ] Install contextily: `pip install contextily>=1.3.0`
- [ ] Update config/settings.yaml with map settings
- [ ] Test matplotlib map: `map depth`
- [ ] Verify colorbar displays
- [ ] Test pan/zoom functionality in matplotlib window
- [ ] Test basemap loads (requires internet)
- [ ] Test without internet (should fall back gracefully)
- [ ] Test folium backend: `map depth backend:folium`
- [ ] Test save PNG: `map depth save`
- [ ] Test save HTML: `map depth backend:folium save`
- [ ] Test with different resolutions: `map depth resolution:9`
- [ ] Test with different aggregations: `map depth agg:max`
- [ ] Verify default backend from config works

---

## CHANGE #1: SWEREF99 Coordinate System Support

**Priority**: Implement Third  
**Complexity**: High  
**Risk**: Moderate (affects data pipeline)  
**Estimated Effort**: 8-12 hours

### Current Behavior
- System uses WGS84 lat/lon (EPSG:4326)
- Position data loaded as-is
- H3 operates on lat/lon
- Folium maps use lat/lon

### Desired Behavior
- Support SWEREF99 TM (EPSG:3006)
- Transform from WGS84 to SWEREF99 on load
- Store data in SWEREF99 (easting/northing)
- Transform back to WGS84 for H3 and web maps
- Configurable via settings

### Key Constraints

**H3 Requirement**: H3 MUST use WGS84 lat/lon - cannot use projected coordinates  
**Folium Requirement**: Web maps require WGS84  
**Solution**: Maintain dual coordinate systems (recommended)

### Strategy: Dual Coordinate Storage

- Store both WGS84 (latitude/longitude) AND SWEREF99 (easting/northing)
- Use SWEREF99 as primary for analysis and matplotlib
- Use WGS84 for H3 aggregation and Folium

---

### Files to Modify

#### 1. `requirements.txt`

**Verify** (should already be present via geopandas):
```
pyproj>=3.4.0
geopandas>=0.10.0
```

---

#### 2. `config/settings.yaml`

**Add new section** (after data section, around line 15):
```yaml
coordinates:
  # Input coordinate system (from position files)
  input_crs: "EPSG:4326"  # WGS84 lat/lon
  
  # Output coordinate system (for processing)
  output_crs: "EPSG:3006"  # SWEREF99 TM
  
  # Transform coordinates on load
  transform_on_load: true
  
  # Column names
  columns:
    input_lon: "longitude"
    input_lat: "latitude"
    output_easting: "easting"
    output_northing: "northing"
    keep_original: true  # Keep WGS84 for H3
    original_lon_suffix: "_wgs84"
    original_lat_suffix: "_wgs84"
```

---

#### 3. `data_loader/position_merger.py`

**Add imports at top**:
```python
from pyproj import Transformer
import logging

logger = logging.getLogger(__name__)
```

**Update class __init__**:
```python
class PositionMerger:
    """Merges position data with acoustic data."""
    
    def __init__(self, settings=None):
        self.settings = settings or {}
        self._setup_coordinate_transformer()
```

**Add new methods**:
```python
def _setup_coordinate_transformer(self):
    """Initialize coordinate transformer based on settings."""
    coord_config = self.settings.get('coordinates', {})
    self.transform_enabled = coord_config.get('transform_on_load', False)
    
    if self.transform_enabled:
        input_crs = coord_config.get('input_crs', 'EPSG:4326')
        output_crs = coord_config.get('output_crs', 'EPSG:3006')
        
        # Create transformer (always_xy=True ensures lon, lat order)
        self.transformer = Transformer.from_crs(
            input_crs,
            output_crs,
            always_xy=True
        )
        
        logger.info(f"Coordinate transformation enabled: {input_crs} → {output_crs}")
    else:
        self.transformer = None
        logger.info("Coordinate transformation disabled")

def _transform_coordinates(self, df):
    """
    Transform coordinates from WGS84 to SWEREF99.
    
    Parameters
    ----------
    df : DataFrame
        DataFrame with latitude and longitude columns
    
    Returns
    -------
    DataFrame
        DataFrame with added easting and northing columns
    """
    if not self.transform_enabled or self.transformer is None:
        return df
    
    coord_config = self.settings.get('coordinates', {})
    
    # Get column names from config
    lon_col = coord_config.get('columns', {}).get('input_lon', 'longitude')
    lat_col = coord_config.get('columns', {}).get('input_lat', 'latitude')
    easting_col = coord_config.get('columns', {}).get('output_easting', 'easting')
    northing_col = coord_config.get('columns', {}).get('output_northing', 'northing')
    keep_original = coord_config.get('columns', {}).get('keep_original', True)
    
    # Check if columns exist
    if lon_col not in df.columns or lat_col not in df.columns:
        logger.warning(f"Coordinate columns not found: {lon_col}, {lat_col}")
        return df
    
    # Transform coordinates
    easting, northing = self.transformer.transform(
        df[lon_col].values,
        df[lat_col].values
    )
    
    # Add transformed coordinates
    df[easting_col] = easting
    df[northing_col] = northing
    
    # Keep original WGS84 for H3 (optional but recommended)
    if keep_original:
        lon_suffix = coord_config.get('columns', {}).get('original_lon_suffix', '_wgs84')
        lat_suffix = coord_config.get('columns', {}).get('original_lat_suffix', '_wgs84')
        
        df[f'{lon_col}{lon_suffix}'] = df[lon_col]
        df[f'{lat_col}{lat_suffix}'] = df[lat_col]
    
    logger.info(f"Transformed {len(df)} coordinate pairs to SWEREF99")
    logger.info(f"Ranges: E=[{easting.min():.1f}, {easting.max():.1f}], "
               f"N=[{northing.min():.1f}, {northing.max():.1f}]")
    
    return df
```

**Update merge_positions() method** - add at the end before return:
```python
def merge_positions(self, acoustic_df, position_df):
    """Merge position data with acoustic data using time interpolation."""
    # ... existing merge logic ...
    
    # Transform coordinates if enabled
    merged_df = self._transform_coordinates(merged_df)
    
    return merged_df
```

---

#### 4. `aggregation/spatial_aggregator.py`

**Update __init__**:
```python
class SpatialAggregator:
    """Performs spatial aggregation using H3 hexagons."""
    
    def __init__(self, settings=None):
        self.settings = settings or {}
        self.coord_config = self.settings.get('coordinates', {})
```

**Add helper method**:
```python
def _get_wgs84_coords(self, df):
    """
    Get WGS84 lat/lon coordinates from dataframe.
    Handles both original WGS84 and transformed SWEREF99 data.
    
    Returns
    -------
    tuple (lat_col, lon_col)
        Names of columns containing WGS84 coordinates
    """
    transform_enabled = self.coord_config.get('transform_on_load', False)
    
    if transform_enabled:
        # Data transformed to SWEREF99, use original WGS84 columns
        keep_original = self.coord_config.get('columns', {}).get('keep_original', True)
        
        if keep_original:
            # Original coordinates preserved
            return 'latitude', 'longitude'
        else:
            raise ValueError(
                "Cannot perform H3 aggregation: WGS84 coordinates not available. "
                "Set coordinates.columns.keep_original to true in settings."
            )
    else:
        # No transformation, use original columns
        return 'latitude', 'longitude'
```

**Update aggregate_to_hexagons() method**:
```python
def aggregate_to_hexagons(self, df, value_col, resolution=8, agg_func="mean"):
    """
    Aggregate data to H3 hexagons.
    
    Parameters
    ----------
    df : DataFrame
        Data with position and value columns
    value_col : str
        Column to aggregate
    resolution : int
        H3 resolution (0-15)
    agg_func : str or callable
        Aggregation function
    
    Returns
    -------
    DataFrame
        Aggregated data with hex_id and values
    """
    # Get WGS84 coordinates for H3 (H3 requires WGS84)
    lat_col, lon_col = self._get_wgs84_coords(df)
    
    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(f"Required columns not found: {lat_col}, {lon_col}")
    
    if value_col not in df.columns:
        raise ValueError(f"Value column not found: {value_col}")
    
    # Generate H3 hex IDs using WGS84
    df = df.copy()
    df['hex_id'] = df.apply(
        lambda row: h3.geo_to_h3(
            row[lat_col],
            row[lon_col],
            resolution
        ),
        axis=1
    )
    
    # Aggregate by hexagon
    agg_df = df.groupby('hex_id')[value_col].agg(agg_func).reset_index()
    
    # Add hex center coordinates (WGS84)
    agg_df['hex_lat'], agg_df['hex_lon'] = zip(*agg_df['hex_id'].apply(
        lambda h: h3.h3_to_geo(h)
    ))
    
    # If SWEREF99 enabled, also add hex centers in SWEREF99
    if self.coord_config.get('transform_on_load', False):
        from pyproj import Transformer
        transformer = Transformer.from_crs(
            self.coord_config.get('input_crs', 'EPSG:4326'),
            self.coord_config.get('output_crs', 'EPSG:3006'),
            always_xy=True
        )
        
        hex_easting, hex_northing = transformer.transform(
            agg_df['hex_lon'].values,
            agg_df['hex_lat'].values
        )
        
        agg_df['hex_easting'] = hex_easting
        agg_df['hex_northing'] = hex_northing
    
    return agg_df
```

---

#### 5. `visualization/map_generator.py`

**Update for matplotlib backend** (in the create_matplotlib_map method you added in Change #2):

**Add comment in the coordinate handling section**:
```python
# Get hexagon boundary (returns WGS84 lat/lon)
# H3 always returns WGS84 coordinates
boundary = h3.h3_to_geo_boundary(hex_id, geo_json=True)

# For now, plot in WGS84 to maintain compatibility with contextily
# Future: support SWEREF99 plotting without basemap
coords = boundary
```

**Update axis labels** to be aware of coordinate system:
```python
# Set labels
coord_config = self.settings.get('coordinates', {})
transform_enabled = coord_config.get('transform_on_load', False)

if transform_enabled and not use_basemap:
    # Could plot in SWEREF99 without basemap (future enhancement)
    ax.set_xlabel('Longitude (plotted in WGS84)')
    ax.set_ylabel('Latitude (plotted in WGS84)')
else:
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
```

**Folium backend** - no changes needed, already uses WGS84 from H3

---

#### 6. `interface/task_executor.py`

**Update coordinate checks** in `_create_map()` method:

**Find the section that checks for required columns** and update:
```python
# Check for position columns (support both coordinate systems)
coord_config = self.settings.get('coordinates', {})
transform_enabled = coord_config.get('transform_on_load', False)

if transform_enabled:
    # SWEREF99 mode: need both WGS84 (for H3) and SWEREF99
    required_cols = ['latitude', 'longitude', 'easting', 'northing']
    missing = [col for col in required_cols if col not in self.merged_df.columns]
    if missing:
        return f"Position data incomplete. Missing: {missing}"
else:
    # WGS84 mode only
    required_cols = ['latitude', 'longitude']
    if not all(col in self.merged_df.columns for col in required_cols):
        return f"Position data required. Missing: {required_cols}"
```

**Add new method** for coordinate info:
```python
def _coords_info(self):
    """Display coordinate system information."""
    coord_config = self.settings.get('coordinates', {})
    transform_enabled = coord_config.get('transform_on_load', False)
    
    info = []
    info.append("=== Coordinate System Settings ===")
    info.append(f"Transformation: {'Enabled' if transform_enabled else 'Disabled'}")
    
    if transform_enabled:
        info.append(f"Input CRS: {coord_config.get('input_crs', 'EPSG:4326')}")
        info.append(f"Output CRS: {coord_config.get('output_crs', 'EPSG:3006')}")
        info.append(f"Primary columns: easting, northing")
        info.append(f"WGS84 columns (for H3): latitude, longitude")
    else:
        info.append(f"CRS: {coord_config.get('input_crs', 'EPSG:4326')}")
        info.append(f"Columns: latitude, longitude")
    
    if self.merged_df is not None:
        coord_cols = [col for col in self.merged_df.columns 
                     if any(x in col.lower() for x in ['lat', 'lon', 'east', 'north'])]
        info.append(f"\nAvailable coordinate columns: {coord_cols}")
        
        # Show coordinate ranges
        if transform_enabled and 'easting' in self.merged_df.columns:
            info.append(f"Easting range: {self.merged_df['easting'].min():.1f} - {self.merged_df['easting'].max():.1f} m")
            info.append(f"Northing range: {self.merged_df['northing'].min():.1f} - {self.merged_df['northing'].max():.1f} m")
    
    return "\n".join(info)
```

**Add to execute_task() method**:
```python
elif task == "coords_info":
    return self._coords_info()
```

---

#### 7. `interface/nlp_interpreter.py`

**Add coords command parsing**:
```python
if "coords" in s or "crs" in s or "coordinate" in s:
    if "info" in s or "show" in s or "display" in s:
        return {"task": "coords_info"}
```

---

#### 8. `interface/cli.py`

**Add to help text**:
```python
coords: Show coordinate system information
  - show coords
  - coords info
```

---

### Testing Checklist for Change #1

**Before implementing, verify position file format**:
- [ ] Check data/data/positions.txt format
- [ ] Determine if coordinates are WGS84 or already SWEREF99
- [ ] Adjust config accordingly

**After implementation**:
- [ ] Verify pyproj is installed
- [ ] Update config/settings.yaml with coordinates section
- [ ] Test coordinate transformation:
  - Load and merge data
  - Run `show coords` - verify transformation enabled
  - Check columns: should have latitude, longitude, easting, northing
- [ ] Test coordinate ranges:
  - Run `stats easting` and `stats northing`
  - Verify ranges appropriate for Sweden (E: ~250k-900k, N: ~6.1M-7.7M)
- [ ] Test H3 aggregation:
  - Run `map depth`
  - Verify map plots in correct location (Sweden)
- [ ] Test scatter with SWEREF99:
  - `scatter easting vs northing` (should show position scatter)
  - `scatter depth vs easting` (should show depth along east-west)
- [ ] Test round-trip accuracy:
  - Original WGS84 → SWEREF99 → stored
  - Use stored WGS84 for H3 → should match original
- [ ] Visual verification:
  - Create map and verify location is in Sweden
  - Compare with known landmarks

---

## Implementation Sequence

### Phase 1: Change #3 (1-2 hours)
1. Modify `interface/nlp_interpreter.py` - add x extraction
2. Modify `interface/task_executor.py` - update _plot_scatter
3. Update `interface/cli.py` - help text
4. Test scatter commands

### Phase 2: Change #2 (4-6 hours)
1. Install contextily
2. Add map settings to config
3. Create matplotlib map method
4. Update map routing
5. Add backend parsing
6. Update task executor
7. Test both backends

### Phase 3: Change #1 (8-12 hours)
1. Verify position file format
2. Add coordinate config
3. Add transformation to position_merger
4. Update spatial_aggregator
5. Update map_generator awareness
6. Update task_executor checks
7. Add coords info command
8. Comprehensive testing

### Phase 4: Integration Testing (2-3 hours)
1. Test all three changes together
2. Test edge cases
3. Performance testing
4. Documentation updates

---

## Success Criteria

### Change #3 ✓
- Users can specify x and y for scatter
- Default x=timestamp works (backward compatible)
- Multiple syntaxes supported
- Clear error messages

### Change #2 ✓
- Interactive matplotlib maps with pan/zoom
- Colorbar displays value scale
- Basemap tiles load (when available)
- Both backends work
- Save works for both formats

### Change #1 ✓
- Coordinates transform to SWEREF99
- Dual storage (WGS84 + SWEREF99)
- H3 aggregation works
- Maps plot in correct location
- System configurable
- Coords info command works

---

## Troubleshooting

### Contextily Issues
- **No basemap appears**: Check internet connection
- **Import error**: Run `pip install contextily`
- **Basemap in wrong location**: Check CRS is EPSG:4326

### Coordinate Transform Issues
- **Values out of range**: Check input CRS is correct
- **H3 fails**: Verify latitude/longitude columns preserved
- **Map in wrong location**: Verify transformation direction

### Scatter Plot Issues
- **Column not found**: Check aliases, use lowercase
- **No x parameter**: Verify parameter extraction in nlp_interpreter

---

## Total Estimated Time

- **Change #3**: 1.5-2.5 hours
- **Change #2**: 4-6 hours
- **Change #1**: 9-12 hours
- **Integration**: 2-3 hours
- **Total**: **16.5-23.5 hours**

---

## Dependencies to Install

```bash
pip install contextily>=1.3.0
```

(pyproj should already be installed via geopandas)

---

**END OF IMPLEMENTATION PLAN**
