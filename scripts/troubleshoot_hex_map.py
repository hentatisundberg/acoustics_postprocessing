"""Quick regression harness for the hex map pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from interface.task_executor import TaskExecutor


def _sample_data() -> pd.DataFrame:
    timestamps = pd.date_range("2025-03-18T00:00", periods=6, freq="1h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "latitude": [60.5, 60.52, 60.48, 60.55, 60.51, 60.49],
            "longitude": [15.0, 15.05, 15.1, 15.15, 15.08, 15.02],
            "nasc0": [0.25, 0.3, 0.4, 0.35, 0.28, 0.31],
        }
    )


def main() -> None:
    executor = TaskExecutor()
    executor.merged = _sample_data()
    print("--- Hex map troubleshooting ---")
    for backend in ("matplotlib", "folium"):
        result = executor._hex_map(
            "nasc0",
            resolution=7,
            backend=backend,
            show=False,
            coastline_path=None,
            opts={"min": 0.25, "max": 0.4},
        )
        print(f"[{backend}] {result.message}")
        if result.artifact:
            print(f"map artifact: {result.artifact}")


if __name__ == "__main__":
    main()
