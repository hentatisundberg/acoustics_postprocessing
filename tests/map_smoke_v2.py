from pathlib import Path
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from interface.task_executor import TaskExecutor

params = {
    "dir": "./data/data",
    "pattern": "SLUAquaSailor2020V2-Phase0-*.csv",
    "positions": "positions.txt",
}

executor = TaskExecutor(Path("config/settings.yaml"))
res = executor.execute({"task": "load", "params": params})
print(res.message)
assert res.ok, res.message

merged = executor.merged.copy()
ignore = {"timestamp", "latitude", "longitude", "position_matched"}
num_cols = [c for c in merged.select_dtypes(include=["number"]).columns if c not in ignore]
col = "depth" if "depth" in num_cols else ("backscatter" if "backscatter" in num_cols else (num_cols[0] if num_cols else None))
print("Using column:", col)
assert col is not None, "No numeric column available for map"

# Apply negative transform example (useful for depth)
res2 = executor.execute({"task": "hex_map", "y": col, "resolution": 8, "negative": True, "min": None, "max": None})
print(res2.message)
assert res2.ok, res2.message
assert res2.artifact is not None

out_path = Path(str(res2.artifact))
assert out_path.exists(), f"Missing map file: {out_path}"
size = out_path.stat().st_size
print("Map size bytes:", size)
assert size > 5_000, "Map file seems too small; may be blank"
