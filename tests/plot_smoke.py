from pathlib import Path
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from interface.task_executor import TaskExecutor

# Use sample files in repo
params = {
    "dir": "./data/data",
    "pattern": "*.csv",
    "positions": "./data/positions/positions.txt",
}

executor = TaskExecutor(Path("config/settings.yaml"))
res = executor.execute({"task": "load", "params": params})
print(res.message)
assert res.ok, res.message

# Choose a sensible numeric column to plot
df = executor.merged.copy()
ignore = {"timestamp", "latitude", "longitude", "position_matched"}
numeric_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in ignore]

preferred = None
for candidate in ("backscatter", "depth"):
    if candidate in numeric_cols:
        preferred = candidate
        break
if preferred is None:
    assert numeric_cols, "No numeric columns available to plot"
    preferred = numeric_cols[0]
print("Plotting column:", preferred)

# Plot time series without heavy aggregation to ensure visible data
cmd = {
    "task": "time_series_plot",
    "y": preferred,
    # Use raw data (no resample) to avoid collapsing to few points
    "interval": None,
    "smooth": True,
    "show": False,
    "save": True,
    "out": "outputs/plots/smoke_timeseries.png",
}
res2 = executor.execute(cmd)
print(res2.message)
assert res2.ok, res2.message
assert res2.artifact is not None

# Ensure file exists and has non-trivial size
out_path = Path(str(res2.artifact))
assert out_path.exists(), f"Missing plot file: {out_path}"
size = out_path.stat().st_size
print("Plot size bytes:", size)
assert size > 10_000, "Plot file seems too small; may be blank"
