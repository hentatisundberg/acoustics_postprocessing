from pathlib import Path
import os, sys
import argparse

# Make repo importable
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from interface.task_executor import TaskExecutor

# Prefer repo sample files if available; fall back to README's typical paths
params_candidates = [
    {
        "dir": "./data/data",
        "pattern": "SLUAquaSailor*",
        "positions": "./data/data/positions.txt",
    },
    {
        "dir": "./data",
        "pattern": "SLUAquaSailor*",
        "positions": "./data/positions.txt",
    },
]

parser = argparse.ArgumentParser(description="Scatter smoke: quick scatter plots with optional smoothing")
parser.add_argument("--y", help="Y column to plot (default: auto-detected)")
parser.add_argument("--x", help="X column for XY scatter (default: auto-detected different numeric column)")
parser.add_argument("--interval", help="Optional aggregation interval (e.g., 5min, 30min)")
parser.add_argument("--frac", type=float, help="LOWESS fraction (0-1). Overrides config if provided")
args = parser.parse_args()

executor = TaskExecutor(Path("config/settings.yaml"))
res = None
for params in params_candidates:
    res = executor.execute({"task": "load", "params": params})
    print(res.message)
    if res.ok:
        break
assert res and res.ok, res.message if res else "Load failed"

# Pick columns for scatter
df = executor.merged.copy()
ignore = {"timestamp", "latitude", "longitude", "position_matched"}
num_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in ignore]
assert num_cols, "No numeric columns available for scatter"

# Choose Y column: honor CLI arg if provided and valid
preferred_y = None
if args.y and args.y in num_cols:
    preferred_y = args.y
else:
    for candidate in ("nasc0", "depth", "wave_depth"):
        if candidate in num_cols:
            preferred_y = candidate
            break
    preferred_y = preferred_y or num_cols[0]
print("Scatter Y:", preferred_y)

# XY scatter (two numeric columns) with LOESS smoothing if possible
x_candidates = [c for c in num_cols if c != preferred_y]
if args.x:
    if args.x in x_candidates:
        x_col = args.x
    else:
        print(f"Requested x column '{args.x}' not found or not numeric; falling back to auto.")
        x_col = x_candidates[0] if x_candidates else None
else:
    x_col = x_candidates[0] if x_candidates else None

if x_col:
    print("Scatter X:", x_col)
    cmd_xy_scatter = {
        "task": "scatter_plot",
        "x": x_col,
        "y": preferred_y,
        "interval": args.interval,
        "smooth": "loess",  # LOESS works for numeric x as well
        **({"lowess_frac": args.frac} if args.frac is not None else {}),
        "show": False,
        "save": True,
        "out": f"outputs/plots/smoke_scatter_{preferred_y}_vs_{x_col}.png",
    }
    res2 = executor.execute(cmd_xy_scatter)
    print(res2.message)
    assert res2.ok, res2.message
    assert res2.artifact and Path(str(res2.artifact)).exists()
    print("Saved:", res2.artifact)
else:
    print("No suitable secondary numeric column for XY scatter; skipped.")
