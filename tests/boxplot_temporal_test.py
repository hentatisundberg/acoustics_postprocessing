#!/usr/bin/env python3
"""
Smoke test for boxplot with temporal aggregation.
Tests that boxplot commands can work with time intervals (e.g., 10min, 30min).
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from interface.task_executor import TaskExecutor

def main():
    executor = TaskExecutor()
    
    # Load data
    print("=" * 60)
    print("Loading data...")
    load_cmd = {
        "task": "load",
        "params": {
            "dir": "./data/data",
            "pattern": "SLUAquaSailor*",
            "positions": "./data/positions/positions.txt"
        }
    }
    result = executor.execute(load_cmd)
    print(f"Load result: {result.ok} - {result.message}")
    if not result.ok:
        print("Failed to load data. Exiting.")
        return
    
    # List available columns
    print("\n" + "=" * 60)
    print("Available columns:")
    if executor.merged is not None:
        print(executor.merged.columns.tolist())
    
    # Create the "hour" calculated variable for tests that group by hour
    print("\n" + "=" * 60)
    print("Creating 'hour' calculated variable from timestamp...")
    create_hour_cmd = {
        "task": "create_variable",
        "name": "hour",
        "expression": "timestamp.dt.hour"
    }
    result_hour = executor.execute(create_hour_cmd)
    print(f"Result: {result_hour.ok} - {result_hour.message}")
    
    # Test 1: Boxplot without temporal aggregation (baseline)
    print("\n" + "=" * 60)
    print("Test 1: Boxplot without temporal aggregation")
    cmd1 = {
        "task": "plot_boxplot",
        "y": "nasc0",
        "x": "hour",
        "show": False,
        "save": True,
        "out": "outputs/plots/test_boxplot_no_agg.png"
    }
    result1 = executor.execute(cmd1)
    print(f"Result: {result1.ok} - {result1.message}")
    if result1.artifact:
        print(f"Output: {result1.artifact}")
    
    # Reload data for next test (and recreate hour variable)
    executor.execute(load_cmd)
    executor.execute(create_hour_cmd)
    
    # Test 2: Boxplot WITH 30min temporal aggregation
    print("\n" + "=" * 60)
    print("Test 2: Boxplot WITH 30min temporal aggregation")
    cmd2 = {
        "task": "plot_boxplot",
        "y": "nasc0",
        "x": "hour",
        "interval": "30min",  # Key addition
        "logy": True,
        "outlier_method": "modified_zscore",
        "z_thresh": 100.0,
        "show": False,
        "save": True,
        "out": "outputs/plots/test_boxplot_30min_agg.png"
    }
    result2 = executor.execute(cmd2)
    print(f"Result: {result2.ok} - {result2.message}")
    if result2.artifact:
        print(f"Output: {result2.artifact}")
    
    # Reload data for next test
    executor.execute(load_cmd)
    
    # Test 3: Boxplot with 10min aggregation (simpler)
    print("\n" + "=" * 60)
    print("Test 3: Boxplot with 10min aggregation")
    cmd3 = {
        "task": "plot_boxplot",
        "y": "depth",
        "interval": "10min",
        "show": False,
        "save": True,
        "out": "outputs/plots/test_boxplot_10min_agg.png"
    }
    result3 = executor.execute(cmd3)
    print(f"Result: {result3.ok} - {result3.message}")
    if result3.artifact:
        print(f"Output: {result3.artifact}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
