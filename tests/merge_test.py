import os
import sys
import pandas as pd

# Ensure workspace root is on sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from data_loader.position_merger import PositionMerger

acoustic_path = "data/SLUAquaSailor2020V2-Phase0-D20251023-T002114-0.csv"
pos_path = "data/positions.txt"

# Load acoustic CSV with 'time' column and normalize
acoustic = pd.read_csv(acoustic_path, parse_dates=["time"]).rename(columns={"time": "timestamp"})

# Load positions TSV with 'Time', 'Lat', 'Long' and normalize
positions = pd.read_csv(pos_path, sep="\t", parse_dates=["Time"]).rename(columns={"Time": "timestamp", "Lat": "latitude", "Long": "longitude"})

merger = PositionMerger(acoustic_time_col="timestamp", position_time_col="timestamp", lat_col="latitude", lon_col="longitude")
merged_interp = merger.merge_positions_interpolated(acoustic, positions)

missing_counts = merged_interp[["latitude", "longitude"]].isna().sum().to_dict()
print("Rows:", len(merged_interp))
print("Missing after interpolation:", missing_counts)
print("Head:")
print(merged_interp.head(10)[["timestamp", "latitude", "longitude"]].to_string(index=False))
