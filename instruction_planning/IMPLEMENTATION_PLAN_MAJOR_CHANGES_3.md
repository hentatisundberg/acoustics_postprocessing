# Implementation Plan: Major Changes 3
## Boxplots, Date Filtering, and Data Transformations

**Document Version:** 1.0  
**Date:** 2026-02-04  
**Target System:** Acoustics Postprocessing CLI

---

## Table of Contents

1. [Overview](#overview)
2. [Feature 1: Boxplot Visualization](#feature-1-boxplot-visualization)
3. [Feature 2: Date Range Filtering](#feature-2-date-range-filtering)
4. [Feature 3: Data Transformations](#feature-3-data-transformations)
5. [Integration Strategy](#integration-strategy)
6. [Configuration Updates](#configuration-updates)
7. [Testing Plan](#testing-plan)
8. [Implementation Order](#implementation-order)
9. [Code Examples](#code-examples)

---

## Overview

### Objective
Extend the existing CLI functionality to support:
1. Boxplot generation with configurable x and y axes
2. Date range filtering for all visualization types
3. Data transformations (logarithmic scaling and value thresholding)

### Design Principles
- **Consistency**: Follow existing CLI command patterns
- **Integration**: Seamlessly integrate with current task executor architecture
- **Flexibility**: Support multiple use cases through parameter combinations
- **Robustness**: Handle edge cases and provide clear error messages
- **Configuration**: Respect YAML config → state → command parameter hierarchy

### Files to Modify
1. `visualization/time_series_plots.py` - Add boxplot method
2. `interface/task_executor.py` - Add handlers and helper methods
3. `interface/nlp_interpreter.py` - Add command parsing
4. `interface/cli.py` - Update help text
5. `config/settings.yaml` - Add configuration defaults

---

## Feature 1: Boxplot Visualization

### 1.1 Requirements

**Functional Requirements:**
- Generate boxplots with user-specified y-axis variable
- Support optional grouping/categorization variable (x-axis)
- Handle both categorical and continuous grouping variables
- Save plots to `outputs/plots/` directory
- Display plots in GUI mode, auto-save in headless mode
- Support all existing styling conventions

**CLI Syntax:**
```
boxplot y:column_name                          # Single boxplot
boxplot y:column_name x:group_column          # Grouped boxplot
boxplot y:backscatter x:depth group:zone      # Alternative syntax
boxplot column_name                            # Shorthand (y defaults)
```

**Parameters:**
- `y` (required): Column for boxplot values
- `x` or `group` (optional): Column for grouping/categorization
- Standard parameters: `start_date`, `end_date`, `log`, `min`, `max`

### 1.2 Implementation Details

#### 1.2.1 TimeSeriesPlotter.plot_boxplot()

**File:** `visualization/time_series_plots.py`

**Method Signature:**
```python
def plot_boxplot(
    self,
    data: pd.DataFrame,
    y_column: str,
    x_column: str | None = None,
    title: str | None = None,
    ylabel: str | None = None,
    xlabel: str | None = None,
    output_path: str | None = None,
    show: bool = True,
    figsize: tuple[int, int] = (10, 6),
    showfliers: bool = True,
    vert: bool = True,
    whis: float = 1.5
) -> str | None:
    """
    Create a boxplot visualization.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Input data
    y_column : str
        Column name for boxplot values (y-axis)
    x_column : str | None
        Optional column for grouping (x-axis)
        If None, creates a single boxplot
    title : str | None
        Plot title (auto-generated if None)
    ylabel : str | None
        Y-axis label (defaults to y_column)
    xlabel : str | None
        X-axis label (defaults to x_column or empty)
    output_path : str | None
        Path to save plot (auto-generated if None)
    show : bool
        Whether to display plot (False in headless mode)
    figsize : tuple[int, int]
        Figure size in inches
    showfliers : bool
        Whether to show outlier points
    vert : bool
        If True, vertical boxplots; if False, horizontal
    whis : float
        Whisker length as multiple of IQR (default 1.5)
    
    Returns:
    --------
    str | None
        Path to saved plot file
    """
```

**Implementation Steps:**
1. **Validate inputs:**
   - Check y_column exists in data
   - If x_column specified, check it exists
   - Ensure y_column is numeric
   - Handle missing values (drop NaN in y_column)

2. **Prepare data:**
   - If x_column is None: Single boxplot
   - If x_column is categorical: Group by categories
   - If x_column is continuous: Bin into ranges (use pd.cut)

3. **Create figure:**
   ```python
   fig, ax = plt.subplots(figsize=figsize)
   sns.set_style("whitegrid")
   ```

4. **Generate boxplot:**
   - If no grouping: `ax.boxplot([data[y_column].dropna()])`
   - If grouped (categorical): Use seaborn `sns.boxplot(data=data, x=x_column, y=y_column)`
   - If grouped (continuous): Bin first, then boxplot
   - Apply styling: colors, whisker properties, flier markers

5. **Format plot:**
   - Set title (default: f"Boxplot of {y_column}" or f"{y_column} by {x_column}")
   - Set axis labels
   - Rotate x-tick labels if needed (for long category names)
   - Add grid
   - Adjust layout (`plt.tight_layout()`)

6. **Save and/or show:**
   - Generate output path if not provided: `outputs/plots/boxplot_{y_column}_{timestamp}.png`
   - Save figure
   - Display if show=True and not headless
   - Close figure
   - Return saved path

**Edge Cases:**
- **Empty data:** Raise ValueError with clear message
- **All NaN in y_column:** Raise ValueError
- **Too many categories in x_column (>50):** Warn and suggest aggregation
- **Single unique value:** Still plot, but warn about no variance
- **Continuous x_column:** Auto-bin with sensible defaults (10 bins, equal-width)

#### 1.2.2 TaskExecutor._plot_boxplot()

**File:** `interface/task_executor.py`

**Method Signature:**
```python
def _plot_boxplot(self, params: dict[str, Any]) -> ExecutionResult:
    """
    Execute boxplot task.
    
    Expected params:
    - y: str (required) - Column for boxplot values
    - x or group: str (optional) - Column for grouping
    - start_date, end_date: str (optional) - Date filtering
    - log: bool (optional) - Apply log transform
    - min, max: float (optional) - Value thresholding
    """
```

**Implementation Logic:**
```python
def _plot_boxplot(self, params: dict[str, Any]) -> ExecutionResult:
    # 1. Check data loaded
    if self.merged is None or self.merged.empty:
        return ExecutionResult(
            success=False,
            message="No data loaded. Use 'load' command first.",
            data=None
        )
    
    # 2. Extract parameters
    y_column = params.get('y')
    x_column = params.get('x') or params.get('group')  # Support both syntaxes
    
    if not y_column:
        return ExecutionResult(
            success=False,
            message="Parameter 'y' is required for boxplot",
            data=None
        )
    
    # 3. Resolve column aliases
    y_column = self._resolve_column_name(y_column)
    if x_column:
        x_column = self._resolve_column_name(x_column)
    
    # 4. Filter by date range (if specified)
    data = self._filter_by_date_range(
        self.merged,
        params.get('start_date'),
        params.get('end_date')
    )
    
    # 5. Apply transformations (log, min, max)
    data, y_column = self._apply_transformations(
        data,
        y_column,
        log=params.get('log', False),
        min_val=params.get('min'),
        max_val=params.get('max')
    )
    
    # 6. Validate columns exist
    if y_column not in data.columns:
        available = [c for c in data.select_dtypes(include=[np.number]).columns]
        return ExecutionResult(
            success=False,
            message=f"Column '{y_column}' not found. Available numeric columns: {', '.join(available)}",
            data=None
        )
    
    if x_column and x_column not in data.columns:
        return ExecutionResult(
            success=False,
            message=f"Column '{x_column}' not found. Available columns: {', '.join(data.columns)}",
            data=None
        )
    
    # 7. Generate boxplot
    try:
        output_path = self.plotter.plot_boxplot(
            data=data,
            y_column=y_column,
            x_column=x_column,
            show=not self.headless
        )
        
        return ExecutionResult(
            success=True,
            message=f"Boxplot created successfully",
            data=None,
            artifacts=[output_path] if output_path else []
        )
    
    except Exception as e:
        self.logger.error(f"Boxplot generation failed: {e}")
        return ExecutionResult(
            success=False,
            message=f"Boxplot generation failed: {str(e)}",
            data=None
        )
```

#### 1.2.3 Command Parsing

**File:** `interface/nlp_interpreter.py`

**Add to `parse_command()` method:**

```python
# Boxplot patterns
if any(word in lower_input for word in ['boxplot', 'box']):
    # Pattern 1: "boxplot y:column x:group"
    y_match = re.search(r'y:(\w+)', lower_input)
    x_match = re.search(r'(?:x|group):(\w+)', lower_input)
    
    # Pattern 2: "boxplot column" (y defaults)
    if not y_match:
        words = lower_input.split()
        if len(words) >= 2:
            y_match = words[1]  # First word after 'boxplot'
    
    if y_match:
        y_col = y_match.group(1) if hasattr(y_match, 'group') else y_match
        params = {
            'task': 'plot_boxplot',
            'y': y_col
        }
        
        if x_match:
            params['x'] = x_match.group(1)
        
        # Extract common parameters (dates, transforms)
        params.update(self._extract_date_params(lower_input))
        params.update(self._extract_transform_params(lower_input))
        
        return params
```

**Add validation in `validate_command()`:**

```python
elif task == 'plot_boxplot':
    required = ['y']
    missing = [p for p in required if p not in params]
    if missing:
        return False, f"Missing required parameters for boxplot: {', '.join(missing)}"
```

### 1.3 Boxplot Testing Strategy

**Test Cases:**
1. Single boxplot (no grouping)
2. Boxplot grouped by categorical variable
3. Boxplot grouped by continuous variable (auto-binning)
4. Boxplot with date filtering
5. Boxplot with log transformation
6. Boxplot with min/max thresholding
7. Combined: boxplot with all filters
8. Error cases: missing column, empty data, all NaN

**Test Files to Create:**
- `tests/boxplot_smoke.py` - Basic smoke test
- Add cases to existing test suites

---

## Feature 2: Date Range Filtering

### 2.1 Requirements

**Functional Requirements:**
- Filter data by start date, end date, or both
- Apply to all visualization types: time_series, scatter, boxplot, hex_map
- Support multiple date formats with intelligent parsing
- Handle timezone-aware and timezone-naive datetimes
- Preserve data integrity (non-destructive filtering)

**CLI Syntax:**
```
scatter depth start_date=2024-10-06 end_date=2024-10-07
line backscatter start_date="2024-10-06 08:00:00"
boxplot y:temperature start_date=2024-10-06
map backscatter resolution=8 start_date=2024-10-06 end_date=2024-10-06
```

**Supported Date Formats:**
- `YYYY-MM-DD` (e.g., `2024-10-06`)
- `YYYY-MM-DD HH:MM:SS` (e.g., `2024-10-06 14:30:00`)
- ISO 8601 with timezone (e.g., `2024-10-06T14:30:00+02:00`)

**Parameters:**
- `start_date` (optional): Inclusive lower bound
- `end_date` (optional): Inclusive upper bound
- Both optional (either, neither, or both can be specified)

### 2.2 Implementation Details

#### 2.2.1 TaskExecutor._filter_by_date_range()

**File:** `interface/task_executor.py`

**Method Signature:**
```python
def _filter_by_date_range(
    self,
    data: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None
) -> pd.DataFrame:
    """
    Filter dataframe by date range.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Input dataframe with timestamp column
    start_date : str | None
        Start date (inclusive) in format YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
    end_date : str | None
        End date (inclusive) in format YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
    
    Returns:
    --------
    pd.DataFrame
        Filtered dataframe
    
    Raises:
    -------
    ValueError
        If date parsing fails or timestamp column not found
    """
```

**Implementation Logic:**
```python
def _filter_by_date_range(
    self,
    data: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None
) -> pd.DataFrame:
    # 1. Early return if no filtering needed
    if not start_date and not end_date:
        return data
    
    # 2. Identify timestamp column
    timestamp_col = None
    for col in ['timestamp', 'time', 'datetime', 'date']:
        if col in data.columns:
            timestamp_col = col
            break
    
    if timestamp_col is None:
        raise ValueError(
            f"No timestamp column found in data. "
            f"Available columns: {', '.join(data.columns)}"
        )
    
    # 3. Ensure timestamp column is datetime type
    if not pd.api.types.is_datetime64_any_dtype(data[timestamp_col]):
        try:
            data = data.copy()  # Avoid modifying original
            data[timestamp_col] = pd.to_datetime(data[timestamp_col])
        except Exception as e:
            raise ValueError(f"Could not convert '{timestamp_col}' to datetime: {e}")
    
    # 4. Parse start_date
    if start_date:
        try:
            start_dt = pd.to_datetime(start_date)
            self.logger.info(f"Filtering data from {start_dt}")
        except Exception as e:
            raise ValueError(f"Invalid start_date format '{start_date}': {e}")
    else:
        start_dt = data[timestamp_col].min()
    
    # 5. Parse end_date
    if end_date:
        try:
            end_dt = pd.to_datetime(end_date)
            # If only date specified (no time), include entire day
            if len(end_date) == 10:  # YYYY-MM-DD format
                end_dt = end_dt + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            self.logger.info(f"Filtering data until {end_dt}")
        except Exception as e:
            raise ValueError(f"Invalid end_date format '{end_date}': {e}")
    else:
        end_dt = data[timestamp_col].max()
    
    # 6. Validate date range
    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_dt}) is after end_date ({end_dt})")
    
    # 7. Apply filter
    mask = (data[timestamp_col] >= start_dt) & (data[timestamp_col] <= end_dt)
    filtered = data[mask].copy()
    
    # 8. Log results
    original_count = len(data)
    filtered_count = len(filtered)
    self.logger.info(
        f"Date filtering: {original_count} rows -> {filtered_count} rows "
        f"({filtered_count/original_count*100:.1f}% retained)"
    )
    
    if filtered_count == 0:
        self.logger.warning(
            f"Date filter returned no data. "
            f"Data range: {data[timestamp_col].min()} to {data[timestamp_col].max()}"
        )
    
    return filtered
```

#### 2.2.2 Integration into Existing Handlers

**Modify these methods in `interface/task_executor.py`:**

1. **`_plot_time_series()`**
2. **`_plot_scatter()`**
3. **`_plot_boxplot()`** (new)
4. **`_generate_hex_map()`**

**Pattern to apply (example for `_plot_scatter()`):**

```python
def _plot_scatter(self, params: dict[str, Any]) -> ExecutionResult:
    # ... existing code ...
    
    # Add after data loading, before transformations:
    try:
        data = self._filter_by_date_range(
            data,
            params.get('start_date'),
            params.get('end_date')
        )
    except ValueError as e:
        return ExecutionResult(
            success=False,
            message=f"Date filtering failed: {str(e)}",
            data=None
        )
    
    if data.empty:
        return ExecutionResult(
            success=False,
            message="No data remaining after date filtering",
            data=None
        )
    
    # ... continue with existing code (transformations, plotting) ...
```

#### 2.2.3 Command Parsing for Date Parameters

**File:** `interface/nlp_interpreter.py`

**Add helper method:**

```python
def _extract_date_params(self, input_string: str) -> dict[str, str]:
    """
    Extract start_date and end_date parameters from input.
    
    Parameters:
    -----------
    input_string : str
        Lower-cased user input
    
    Returns:
    --------
    dict[str, str]
        Dictionary with 'start_date' and/or 'end_date' keys
    """
    params = {}
    
    # Match start_date=YYYY-MM-DD or start_date="YYYY-MM-DD HH:MM:SS"
    start_pattern = r'start_date=["\'"]?([0-9\-\s:T+]+)["\'"]?(?:\s|$)'
    start_match = re.search(start_pattern, input_string)
    if start_match:
        params['start_date'] = start_match.group(1).strip('"\'')
    
    # Match end_date=YYYY-MM-DD or end_date="YYYY-MM-DD HH:MM:SS"
    end_pattern = r'end_date=["\'"]?([0-9\-\s:T+]+)["\'"]?(?:\s|$)'
    end_match = re.search(end_pattern, input_string)
    if end_match:
        params['end_date'] = end_match.group(1).strip('"\'')
    
    return params
```

**Update all command parsers to call `_extract_date_params()`:**

```python
# In scatter, line, boxplot, map parsing sections:
params.update(self._extract_date_params(lower_input))
```

### 2.3 Date Filtering Testing Strategy

**Test Cases:**
1. Filter with start_date only
2. Filter with end_date only
3. Filter with both start_date and end_date
4. Various date formats (YYYY-MM-DD, with time, ISO 8601)
5. Edge case: start_date = end_date (single day)
6. Edge case: filter returns empty dataset
7. Edge case: dates outside data range
8. Error case: invalid date format
9. Error case: start_date > end_date
10. Integration: date filtering + other parameters

---

## Feature 3: Data Transformations

### 3.1 Requirements

**Functional Requirements:**
- Apply natural logarithm transformation to numeric columns
- Filter data by minimum value threshold
- Filter data by maximum value threshold
- Support combinations of transformations
- Create new columns for transformed data (preserve original)
- Handle invalid values gracefully (e.g., log of non-positive)

**CLI Syntax:**
```
scatter depth log=true                              # Log transform y-axis
scatter depth min=10 max=100                        # Value thresholding
boxplot y:backscatter log=true min=50 max=200      # Combined transforms
line temperature log=false min=5                   # Explicit false, min only
```

**Parameters:**
- `log` (optional): `true|false|yes|no|1|0` - Apply natural logarithm
- `min` (optional): float - Minimum value threshold (inclusive)
- `max` (optional): float - Maximum value threshold (inclusive)

**Transformation Logic:**
- **Logarithm:** `log_column = log(column)` for positive values
- **Min filter:** Keep rows where `column >= min`
- **Max filter:** Keep rows where `column <= max`
- **Order:** Filter date range → Apply min/max → Apply log transform

### 3.2 Implementation Details

#### 3.2.1 TaskExecutor._apply_transformations()

**File:** `interface/task_executor.py`

**Method Signature:**
```python
def _apply_transformations(
    self,
    data: pd.DataFrame,
    column: str,
    log: bool = False,
    min_val: float | None = None,
    max_val: float | None = None
) -> tuple[pd.DataFrame, str]:
    """
    Apply transformations to a data column.
    
    Parameters:
    -----------
    data : pd.DataFrame
        Input dataframe
    column : str
        Column name to transform
    log : bool
        If True, apply natural logarithm transformation
    min_val : float | None
        Minimum value threshold (inclusive)
    max_val : float | None
        Maximum value threshold (inclusive)
    
    Returns:
    --------
    tuple[pd.DataFrame, str]
        (Transformed dataframe, name of transformed column)
        If no transformations applied, returns (data, column)
        If transformations applied, returns (data_with_new_column, new_column_name)
    
    Notes:
    ------
    - Creates new column for log transform (e.g., 'backscatter_log')
    - Min/max filtering modifies dataframe in-place (rows removed)
    - Log transform skips non-positive values with warning
    - Validates column exists and is numeric
    """
```

**Implementation Logic:**
```python
def _apply_transformations(
    self,
    data: pd.DataFrame,
    column: str,
    log: bool = False,
    min_val: float | None = None,
    max_val: float | None = None
) -> tuple[pd.DataFrame, str]:
    # 1. Validate column exists
    if column not in data.columns:
        raise ValueError(f"Column '{column}' not found in data")
    
    # 2. Validate column is numeric
    if not pd.api.types.is_numeric_dtype(data[column]):
        raise ValueError(f"Column '{column}' is not numeric (type: {data[column].dtype})")
    
    # 3. Early return if no transformations
    if not log and min_val is None and max_val is None:
        return data, column
    
    # 4. Apply min/max filtering first (reduces data before log)
    original_count = len(data)
    
    if min_val is not None:
        data = data[data[column] >= min_val].copy()
        self.logger.info(
            f"Min filter ({column} >= {min_val}): "
            f"{original_count} rows -> {len(data)} rows"
        )
    
    if max_val is not None:
        data = data[data[column] <= max_val].copy()
        self.logger.info(
            f"Max filter ({column} <= {max_val}): "
            f"{original_count} rows -> {len(data)} rows"
        )
    
    if data.empty:
        self.logger.warning("Filtering resulted in empty dataset")
        return data, column
    
    # 5. Apply log transformation
    if log:
        log_column_name = f"{column}_log"
        
        # Check for non-positive values
        non_positive = (data[column] <= 0).sum()
        if non_positive > 0:
            self.logger.warning(
                f"Log transform: {non_positive} non-positive values in '{column}' "
                f"will be excluded"
            )
            # Only log positive values, rest become NaN
            data[log_column_name] = data[column].apply(
                lambda x: np.log(x) if x > 0 else np.nan
            )
        else:
            data[log_column_name] = np.log(data[column])
        
        self.logger.info(f"Applied log transform: {column} -> {log_column_name}")
        
        # Return transformed column as the active column
        return data, log_column_name
    
    return data, column
```

#### 3.2.2 Command Parsing for Transformation Parameters

**File:** `interface/nlp_interpreter.py`

**Add helper method:**

```python
def _extract_transform_params(self, input_string: str) -> dict[str, Any]:
    """
    Extract transformation parameters from input.
    
    Parameters:
    -----------
    input_string : str
        Lower-cased user input
    
    Returns:
    --------
    dict[str, Any]
        Dictionary with 'log' (bool), 'min' (float), 'max' (float) keys
    """
    params = {}
    
    # Extract log parameter
    log_match = re.search(r'log=(true|false|yes|no|1|0)', input_string)
    if log_match:
        log_value = log_match.group(1)
        params['log'] = log_value in ['true', 'yes', '1']
    
    # Extract min parameter
    min_match = re.search(r'min=([0-9.+-]+)', input_string)
    if min_match:
        try:
            params['min'] = float(min_match.group(1))
        except ValueError:
            pass  # Invalid format, skip
    
    # Extract max parameter
    max_match = re.search(r'max=([0-9.+-]+)', input_string)
    if max_match:
        try:
            params['max'] = float(max_match.group(1))
        except ValueError:
            pass  # Invalid format, skip
    
    return params
```

**Update command parsers to call `_extract_transform_params()`:**

```python
# In scatter, line, boxplot parsing sections:
params.update(self._extract_transform_params(lower_input))
```

#### 3.2.3 Integration into Plot Handlers

**Pattern to apply in all plot methods:**

```python
def _plot_scatter(self, params: dict[str, Any]) -> ExecutionResult:
    # ... existing code ...
    # ... after date filtering ...
    
    # Apply transformations
    try:
        data, y_column = self._apply_transformations(
            data,
            y_column,
            log=params.get('log', False),
            min_val=params.get('min'),
            max_val=params.get('max')
        )
        
        # If x_column also needs transformation (for scatter plots):
        # Note: Only apply log to y by default, unless explicitly requested for x
        # This keeps behavior intuitive
        
    except ValueError as e:
        return ExecutionResult(
            success=False,
            message=f"Transformation failed: {str(e)}",
            data=None
        )
    
    if data.empty:
        return ExecutionResult(
            success=False,
            message="No data remaining after transformations",
            data=None
        )
    
    # ... continue with plotting using potentially new column name ...
```

### 3.3 Data Transformation Testing Strategy

**Test Cases:**
1. Log transform on positive values only
2. Log transform with non-positive values (should warn and skip)
3. Min threshold filtering
4. Max threshold filtering
5. Combined min and max filtering
6. Log transform after min/max filtering
7. All transformations combined with date filtering
8. Edge case: filter leaves no data
9. Edge case: log transform all-negative values
10. Integration: transformations across different plot types

---

## Integration Strategy

### 4.1 Call Sequence in Task Handlers

**Standard pattern for all plot/map handlers:**

```python
def _plot_handler(self, params: dict[str, Any]) -> ExecutionResult:
    # 1. Validate data loaded
    if self.merged is None or self.merged.empty:
        return ExecutionResult(success=False, message="No data loaded", data=None)
    
    # 2. Extract and resolve parameters
    column = params.get('column')
    column = self._resolve_column_name(column)
    
    # 3. Start with merged data
    data = self.merged.copy()
    
    # 4. Apply date range filtering
    try:
        data = self._filter_by_date_range(
            data,
            params.get('start_date'),
            params.get('end_date')
        )
    except ValueError as e:
        return ExecutionResult(success=False, message=str(e), data=None)
    
    # 5. Apply data transformations
    try:
        data, column = self._apply_transformations(
            data,
            column,
            log=params.get('log', False),
            min_val=params.get('min'),
            max_val=params.get('max')
        )
    except ValueError as e:
        return ExecutionResult(success=False, message=str(e), data=None)
    
    # 6. Validate data not empty
    if data.empty:
        return ExecutionResult(
            success=False,
            message="No data remaining after filtering/transformations",
            data=None
        )
    
    # 7. Proceed with task-specific processing
    # ... aggregation, plotting, etc. ...
```

### 4.2 Task Executor Method Organization

**Recommended order in `task_executor.py`:**

```python
class TaskExecutor:
    # ... existing init, config, state methods ...
    
    # === Data Loading Methods ===
    def _load_data(self, params: dict[str, Any]) -> ExecutionResult:
        # ... existing ...
    
    # === Helper Methods (NEW) ===
    def _filter_by_date_range(self, data, start_date, end_date) -> pd.DataFrame:
        """Filter data by date range."""
        # Implementation above
    
    def _apply_transformations(self, data, column, log, min_val, max_val) -> tuple:
        """Apply log/min/max transformations."""
        # Implementation above
    
    # === Task Handler Methods ===
    def _aggregate_time(self, params: dict[str, Any]) -> ExecutionResult:
        # ... existing ...
    
    def _plot_time_series(self, params: dict[str, Any]) -> ExecutionResult:
        # ... update to use helpers ...
    
    def _plot_scatter(self, params: dict[str, Any]) -> ExecutionResult:
        # ... update to use helpers ...
    
    def _plot_boxplot(self, params: dict[str, Any]) -> ExecutionResult:
        # ... NEW ...
    
    def _generate_hex_map(self, params: dict[str, Any]) -> ExecutionResult:
        # ... update to use helpers ...
    
    # ... rest of existing methods ...
```

### 4.3 Dispatcher Updates

**In `TaskExecutor.execute()` method:**

```python
def execute(self, command: dict[str, Any]) -> ExecutionResult:
    task = command.get('task')
    params = {k: v for k, v in command.items() if k != 'task'}
    
    # Dispatch to handlers
    task_handlers = {
        'load': self._load_data,
        'aggregate_time': self._aggregate_time,
        'time_series_plot': self._plot_time_series,
        'scatter_plot': self._plot_scatter,
        'plot_boxplot': self._plot_boxplot,  # NEW
        'hex_map': self._generate_hex_map,
        'compute_stats': self._compute_stats,
        'list_columns': self._list_columns,
        'set': self._update_state,
        'alias': self._set_alias,
        'help': lambda p: ExecutionResult(True, self._get_help_text(), None),
        'exit': lambda p: ExecutionResult(True, "Exiting...", None)
    }
    
    # ... rest of existing dispatch logic ...
```

---

## Configuration Updates

### 5.1 Config File Changes

**File:** `config/settings.yaml`

**Add new sections:**

```yaml
# Existing sections...

visualization:
  default_colormap: "viridis"
  figure_dpi: 300
  
  # Boxplot settings (NEW)
  boxplot:
    figsize: [10, 6]
    showfliers: true          # Show outlier points
    vert: true                # Vertical orientation
    whis: 1.5                 # Whisker length (IQR multiple)
    color: "#3498db"
    edge_color: "#2c3e50"
    edge_width: 1.5
    max_categories: 50        # Warn if more categories
  
  # Map settings
  map:
    default_backend: "matplotlib"
    show_colorbar: true
    use_basemap: true
    basemap_source: "OpenStreetMap.Mapnik"
    hex_edge_color: "none"
    hex_alpha: 0.7
    coastline_path: "./data/geodata/CNTR_RG_03M_2024_4326.geojson"

processing:
  default_temporal_resolution: "5min"
  default_hex_resolution: 8
  time_merge_tolerance: "5s"
  
  # Date filtering (NEW)
  date_filtering:
    default_format: "%Y-%m-%d"  # For parsing
    supported_formats:
      - "%Y-%m-%d"
      - "%Y-%m-%d %H:%M:%S"
      - "%Y-%m-%dT%H:%M:%S"
      - "%Y-%m-%dT%H:%M:%S%z"
  
  # Data transformations (NEW)
  transformations:
    log:
      handle_non_positive: "exclude"  # "exclude" or "offset"
      offset_value: 1.0                # For log(x + offset) if "offset"
    thresholding:
      inclusive: true                  # Min/max are inclusive bounds
      warn_large_filter: true          # Warn if >50% data filtered

analysis:
  outlier_method: "iqr"
  smoothing_method: "lowess"
  lowess_fraction: 0.1

# ... rest of config ...
```

### 5.2 Configuration Usage

**In TaskExecutor.__init__():**

```python
def __init__(self, config_path: str = "config/settings.yaml"):
    # ... existing config loading ...
    
    # Load new configuration sections
    self.boxplot_config = self.config.get('visualization', {}).get('boxplot', {})
    self.date_filter_config = self.config.get('processing', {}).get('date_filtering', {})
    self.transform_config = self.config.get('processing', {}).get('transformations', {})
    
    # Set defaults if not in config
    self.boxplot_figsize = self.boxplot_config.get('figsize', (10, 6))
    self.boxplot_whis = self.boxplot_config.get('whis', 1.5)
    # ... etc ...
```

---

## Testing Plan

### 6.1 Unit Tests

**Create test file:** `tests/test_transformations.py`

```python
"""Unit tests for data transformations and filtering."""

import pandas as pd
import numpy as np
from datetime import datetime
from interface.task_executor import TaskExecutor

def test_date_filtering_start_only():
    """Test filtering with only start_date."""
    pass

def test_date_filtering_end_only():
    """Test filtering with only end_date."""
    pass

def test_date_filtering_both():
    """Test filtering with both dates."""
    pass

def test_log_transform_positive():
    """Test log transform on positive values."""
    pass

def test_log_transform_non_positive():
    """Test log transform handles non-positive values."""
    pass

def test_min_threshold():
    """Test minimum value thresholding."""
    pass

def test_max_threshold():
    """Test maximum value thresholding."""
    pass

def test_combined_transforms():
    """Test combined date filter + transformations."""
    pass
```

### 6.2 Integration Tests

**Create test file:** `tests/test_cli_integration.py`

```python
"""Integration tests for new CLI features."""

def test_boxplot_single():
    """Test single boxplot generation."""
    # Simulate: boxplot y:backscatter
    pass

def test_boxplot_grouped():
    """Test grouped boxplot generation."""
    # Simulate: boxplot y:backscatter x:depth
    pass

def test_scatter_with_date_filter():
    """Test scatter plot with date filtering."""
    # Simulate: scatter depth start_date=2024-10-06
    pass

def test_scatter_with_log_transform():
    """Test scatter plot with log transform."""
    # Simulate: scatter depth log=true
    pass

def test_all_features_combined():
    """Test all new features together."""
    # Simulate: boxplot y:backscatter start_date=2024-10-06 end_date=2024-10-07 log=true min=50 max=200
    pass
```

### 6.3 Smoke Tests

**Create test files:**

1. **`tests/boxplot_smoke.py`**
```python
"""Quick smoke test for boxplot functionality."""

from interface.task_executor import TaskExecutor
from interface.nlp_interpreter import CommandInterpreter

if __name__ == "__main__":
    executor = TaskExecutor()
    interpreter = CommandInterpreter()
    
    # Load data
    load_cmd = interpreter.parse_command(
        "load dir=data/data pattern=*.csv positions=data/positions/positions.txt"
    )
    executor.execute(load_cmd)
    
    # Test boxplot
    boxplot_cmd = interpreter.parse_command("boxplot y:backscatter")
    result = executor.execute(boxplot_cmd)
    
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    if result.artifacts:
        print(f"Saved to: {result.artifacts[0]}")
```

2. **`tests/date_filter_smoke.py`**
3. **`tests/transform_smoke.py`**

### 6.4 Manual Test Cases

**Test scenarios to verify manually:**

1. **Boxplot Scenarios:**
   - [ ] Single boxplot with numeric column
   - [ ] Grouped boxplot with categorical column (<10 categories)
   - [ ] Grouped boxplot with many categories (>50, should warn)
   - [ ] Grouped boxplot with continuous column (auto-binning)
   - [ ] Boxplot with all NaN values (should error gracefully)

2. **Date Filter Scenarios:**
   - [ ] Filter all plot types with date range
   - [ ] Single day filter (start = end)
   - [ ] Invalid date format (should error with message)
   - [ ] Date range outside data range (should return empty with warning)
   - [ ] Partial date (YYYY-MM-DD) vs full datetime

3. **Transform Scenarios:**
   - [ ] Log transform positive values
   - [ ] Log transform with zeros/negatives
   - [ ] Min/max thresholding
   - [ ] Combined transformations
   - [ ] Transform on column with all invalid values

4. **Combined Scenarios:**
   - [ ] Boxplot + date filter + log transform
   - [ ] Scatter + date filter + min/max
   - [ ] Map + date filter
   - [ ] All features with aliases

---

## Implementation Order

### Phase 1: Foundation (Day 1)
1. Add `_filter_by_date_range()` helper to TaskExecutor
2. Add `_apply_transformations()` helper to TaskExecutor
3. Add `_extract_date_params()` to CommandInterpreter
4. Add `_extract_transform_params()` to CommandInterpreter
5. Update config file with new settings

### Phase 2: Boxplot (Day 2)
1. Implement `TimeSeriesPlotter.plot_boxplot()`
2. Implement `TaskExecutor._plot_boxplot()`
3. Add boxplot parsing to CommandInterpreter
4. Add boxplot validation
5. Create boxplot smoke test

### Phase 3: Integration (Day 3)
1. Integrate date filtering into `_plot_time_series()`
2. Integrate date filtering into `_plot_scatter()`
3. Integrate date filtering into `_generate_hex_map()`
4. Integrate transformations into all plot handlers
5. Update dispatcher to include boxplot task

### Phase 4: Polish (Day 4)
1. Update help text in CLI with new examples
2. Add comprehensive error messages
3. Test all combinations manually
4. Fix edge cases and bugs
5. Write integration tests

### Phase 5: Documentation (Day 5)
1. Update README with new features
2. Add usage examples
3. Document configuration options
4. Create troubleshooting guide

---

## Code Examples

### 8.1 CLI Usage Examples

**Example 1: Basic Boxplot**
```
> boxplot y:backscatter
✓ Boxplot created successfully
Saved to: outputs/plots/boxplot_backscatter_20260204_143022.png
```

**Example 2: Grouped Boxplot**
```
> boxplot y:temperature x:depth
✓ Boxplot created successfully (5 groups)
Saved to: outputs/plots/boxplot_temperature_by_depth_20260204_143045.png
```

**Example 3: Scatter with Date Filter**
```
> scatter depth start_date=2024-10-06 end_date=2024-10-07
ℹ Filtering data from 2024-10-06 00:00:00
ℹ Filtering data until 2024-10-07 23:59:59
ℹ Date filtering: 15234 rows -> 2847 rows (18.7% retained)
✓ Scatter plot created successfully
```

**Example 4: Log Transform**
```
> scatter backscatter log=true
ℹ Applied log transform: backscatter -> backscatter_log
✓ Scatter plot created successfully
```

**Example 5: All Features Combined**
```
> boxplot y:backscatter x:depth start_date=2024-10-06 end_date=2024-10-07 log=true min=50 max=200
ℹ Filtering data from 2024-10-06 00:00:00
ℹ Filtering data until 2024-10-07 23:59:59
ℹ Date filtering: 15234 rows -> 2847 rows (18.7% retained)
ℹ Min filter (backscatter >= 50): 2847 rows -> 2103 rows
ℹ Max filter (backscatter <= 200): 2103 rows -> 1987 rows
ℹ Applied log transform: backscatter -> backscatter_log
✓ Boxplot created successfully (8 groups)
```

### 8.2 Code Snippets

**Helper Method Usage:**

```python
# In any task handler:
def _some_plot_handler(self, params: dict[str, Any]) -> ExecutionResult:
    data = self.merged.copy()
    
    # Apply filters and transforms
    data = self._filter_by_date_range(data, params.get('start_date'), params.get('end_date'))
    data, column = self._apply_transformations(
        data, 
        column,
        log=params.get('log', False),
        min_val=params.get('min'),
        max_val=params.get('max')
    )
    
    # Continue with plotting
    # ...
```

**Boxplot Generation:**

```python
# Simple usage:
output_path = plotter.plot_boxplot(
    data=df,
    y_column='backscatter',
    show=True
)

# Grouped usage:
output_path = plotter.plot_boxplot(
    data=df,
    y_column='temperature',
    x_column='depth',
    title='Temperature Distribution by Depth',
    show=True
)
```

---

## Error Handling Matrix

| Scenario | Error Type | Message | Recovery |
|----------|-----------|---------|----------|
| No data loaded | ExecutionResult | "No data loaded. Use 'load' command first." | Load data first |
| Missing required param | ExecutionResult | "Parameter 'y' is required for boxplot" | Add parameter |
| Column not found | ExecutionResult | "Column 'x' not found. Available: ..." | Use valid column |
| Invalid date format | ValueError | "Invalid start_date format 'abc': ..." | Use YYYY-MM-DD |
| Date range invalid | ValueError | "start_date (X) is after end_date (Y)" | Fix date order |
| Empty after filter | ExecutionResult | "No data remaining after filtering" | Adjust filters |
| Non-numeric column | ValueError | "Column 'x' is not numeric (type: object)" | Use numeric column |
| Log of non-positive | Warning | "Log transform: N non-positive values excluded" | Data with NaN |
| Too many categories | Warning | "Boxplot has 75 categories, consider aggregation" | Continue anyway |

---

## Appendix A: File Modification Summary

### Files to Create
- `tests/test_transformations.py` (new unit tests)
- `tests/test_cli_integration.py` (new integration tests)
- `tests/boxplot_smoke.py` (smoke test)
- `tests/date_filter_smoke.py` (smoke test)
- `tests/transform_smoke.py` (smoke test)

### Files to Modify

**`visualization/time_series_plots.py`**
- Add `plot_boxplot()` method (≈100 lines)

**`interface/task_executor.py`**
- Add `_filter_by_date_range()` helper (≈80 lines)
- Add `_apply_transformations()` helper (≈80 lines)
- Add `_plot_boxplot()` handler (≈80 lines)
- Modify `_plot_time_series()` to integrate filters (≈10 lines)
- Modify `_plot_scatter()` to integrate filters (≈10 lines)
- Modify `_generate_hex_map()` to integrate filters (≈10 lines)
- Update `execute()` dispatcher to add boxplot (≈1 line)

**`interface/nlp_interpreter.py`**
- Add `_extract_date_params()` helper (≈25 lines)
- Add `_extract_transform_params()` helper (≈25 lines)
- Add boxplot parsing logic (≈30 lines)
- Update scatter/line/map parsing to call helpers (≈3 lines each)
- Add validation for boxplot in `validate_command()` (≈5 lines)

**`interface/cli.py`**
- Update help text with new examples (≈20 lines)

**`config/settings.yaml`**
- Add boxplot section (≈10 lines)
- Add date_filtering section (≈8 lines)
- Add transformations section (≈8 lines)

---

## Appendix B: API Quick Reference

### New Helper Methods

```python
TaskExecutor._filter_by_date_range(
    data: pd.DataFrame,
    start_date: str | None,
    end_date: str | None
) -> pd.DataFrame

TaskExecutor._apply_transformations(
    data: pd.DataFrame,
    column: str,
    log: bool,
    min_val: float | None,
    max_val: float | None
) -> tuple[pd.DataFrame, str]

CommandInterpreter._extract_date_params(
    input_string: str
) -> dict[str, str]

CommandInterpreter._extract_transform_params(
    input_string: str
) -> dict[str, Any]

TimeSeriesPlotter.plot_boxplot(
    data: pd.DataFrame,
    y_column: str,
    x_column: str | None,
    **kwargs
) -> str | None
```

### CLI Parameter Reference

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| `y` | str | `y:backscatter` | Boxplot value column |
| `x` or `group` | str | `x:depth` | Boxplot grouping column |
| `start_date` | str | `start_date=2024-10-06` | Start date (inclusive) |
| `end_date` | str | `end_date=2024-10-07` | End date (inclusive) |
| `log` | bool | `log=true` | Apply natural logarithm |
| `min` | float | `min=50` | Minimum value threshold |
| `max` | float | `max=200` | Maximum value threshold |

---

## Appendix C: Configuration Reference

### Boxplot Configuration

```yaml
visualization:
  boxplot:
    figsize: [10, 6]         # Figure size (width, height)
    showfliers: true         # Show outlier points beyond whiskers
    vert: true               # Vertical (true) or horizontal (false)
    whis: 1.5                # Whisker length as IQR multiple
    color: "#3498db"         # Box fill color
    edge_color: "#2c3e50"    # Box edge color
    edge_width: 1.5          # Box edge line width
    max_categories: 50       # Warn if more categories than this
```

### Date Filtering Configuration

```yaml
processing:
  date_filtering:
    default_format: "%Y-%m-%d"
    supported_formats:
      - "%Y-%m-%d"
      - "%Y-%m-%d %H:%M:%S"
      - "%Y-%m-%dT%H:%M:%S"
      - "%Y-%m-%dT%H:%M:%S%z"
```

### Transformation Configuration

```yaml
processing:
  transformations:
    log:
      handle_non_positive: "exclude"  # "exclude" or "offset"
      offset_value: 1.0                # For log(x + offset)
    thresholding:
      inclusive: true                  # Min/max are inclusive
      warn_large_filter: true          # Warn if >50% filtered
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-04 | Implementation Team | Initial detailed specification |

---

**END OF IMPLEMENTATION PLAN**
