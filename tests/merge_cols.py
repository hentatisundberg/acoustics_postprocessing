import os, sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

acoustic_path = "data/SLUAquaSailor2020V2-Phase0-D20251023-T002114-0.csv"
pos_path = "data/positions.txt"

acoustic = pd.read_csv(acoustic_path, parse_dates=["time"]).rename(columns={"time": "timestamp"})
positions = pd.read_csv(pos_path, sep="\t", parse_dates=["Time"]).rename(columns={"Time": "timestamp", "Lat": "latitude", "Long": "longitude"})

merged = pd.merge_asof(
    acoustic.sort_values("timestamp"),
    positions.sort_values("timestamp")[["timestamp", "latitude", "longitude"]],
    left_on="timestamp",
    right_on="timestamp",
    tolerance=pd.Timedelta("5s"),
    direction="nearest",
)
print("Columns:", list(merged.columns))
print(merged.head(3).to_string(index=False))
