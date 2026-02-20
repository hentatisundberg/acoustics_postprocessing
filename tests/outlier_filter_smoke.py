import os
import sys
from pathlib import Path

# Ensure project root is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from interface.task_executor import TaskExecutor
from interface.nlp_interpreter import CommandInterpreter

if __name__ == "__main__":
    executor = TaskExecutor(Path("config/settings.yaml"))
    interpreter = CommandInterpreter()
    
    # Load data
    load_cmd = interpreter.parse_command(
        "load dir=data/data pattern=*.csv positions=data/positions/positions.txt"
    )
    res = executor.execute(load_cmd)
    print(res.message)
    if not res.ok:
        raise SystemExit(1)
    
    # Pick a typical column
    df = executor.merged.copy()
    ignore = {"timestamp", "latitude", "longitude", "position_matched"}
    numeric_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in ignore]
    ycol = "backscatter" if "backscatter" in numeric_cols else ("depth" if "depth" in numeric_cols else numeric_cols[0])
    
    # Test 1: Plot with outlier filtering (zscore, threshold=2.5)
    print("\n=== Test 1: Time series with outlier filtering ===")
    cmd1 = interpreter.parse_command(
        f"plot y:{ycol} 5min outliers=zscore z_thresh=2.5 save=true show=false out=outputs/plots/smoke_outlier_timeseries.png"
    )
    res1 = executor.execute(cmd1)
    print(res1.message)
    if not res1.ok:
        raise SystemExit(1)
    
    # Test 2: Scatter with outlier filtering
    print("\n=== Test 2: Scatter plot with outlier filtering ===")
    cmd2 = interpreter.parse_command(
        f"scatter y:{ycol} outliers:zscore z_thresh:3.0 save=true show=false out=outputs/plots/smoke_outlier_scatter.png"
    )
    res2 = executor.execute(cmd2)
    print(res2.message)
    if not res2.ok:
        raise SystemExit(1)
    
    # Test 3: Boxplot with outlier filtering
    print("\n=== Test 3: Boxplot with outlier filtering ===")
    cmd3 = interpreter.parse_command(
        f"boxplot y:{ycol} outliers=zscore save=true show=false out=outputs/plots/smoke_outlier_boxplot.png"
    )
    res3 = executor.execute(cmd3)
    print(res3.message)
    if not res3.ok:
        raise SystemExit(1)
    
    print("\n✓ All outlier filtering tests passed!")
