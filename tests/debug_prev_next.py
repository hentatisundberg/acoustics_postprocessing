import os, sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from data_loader.position_merger import PositionMerger

acoustic = pd.read_csv("data/SLUAquaSailor2020V2-Phase0-D20251023-T002114-0.csv", parse_dates=["time"]).rename(columns={"time": "timestamp"})
positions = pd.read_csv("data/positions.txt", sep="\t", parse_dates=["Time"]).rename(columns={"Time": "timestamp", "Lat": "latitude", "Long": "longitude"})

merger = PositionMerger(acoustic_time_col="timestamp", position_time_col="timestamp", lat_col="latitude", lon_col="longitude")

a = acoustic.copy(); p = positions.copy()
a[a.columns[0]]
prev = pd.merge_asof(
    a[[merger.acoustic_time_col]],
    p[[merger.position_time_col, merger.lat_col, merger.lon_col]],
    left_on=merger.acoustic_time_col,
    right_on=merger.position_time_col,
    direction="backward",
).rename(columns={
    merger.position_time_col: f"{merger.position_time_col}_prev",
    merger.lat_col: f"{merger.lat_col}_prev",
    merger.lon_col: f"{merger.lon_col}_prev",
}).reset_index()

next_ = pd.merge_asof(
    a[[merger.acoustic_time_col]],
    p[[merger.position_time_col, merger.lat_col, merger.lon_col]],
    left_on=merger.acoustic_time_col,
    right_on=merger.position_time_col,
    direction="forward",
).rename(columns={
    merger.position_time_col: f"{merger.position_time_col}_next",
    merger.lat_col: f"{merger.lat_col}_next",
    merger.lon_col: f"{merger.lon_col}_next",
}).reset_index()

print("prev columns:", list(prev.columns))
print("next_ columns:", list(next_.columns))
print(prev.head(3).to_string(index=False))
print(next_.head(3).to_string(index=False))
