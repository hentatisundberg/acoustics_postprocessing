from pathlib import Path
import os, sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from interface.task_executor import TaskExecutor

# Use the provided sample files
params = {
    "dir": "./data",
    "pattern": "SLUAquaSailor2020V2-Phase0-*.csv",
    "positions": "./data/positions.txt",
}

executor = TaskExecutor(Path("config/settings.yaml"))
result = executor._load_data(params)
print(result.message)
merged = executor.merged
print("Missing after interpolation:", merged[["latitude", "longitude"]].isna().sum().to_dict())
print(merged.head(10)[["timestamp", "latitude", "longitude"]].to_string(index=False))
