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
    
    # Test 1: Stats by time with single column
    print("\n=== Test 1: Stats by time (10min) for single column ===")
    cmd1 = interpreter.parse_command(f"stats by time 10min columns={ycol}")
    res1 = executor.execute(cmd1)
    print(res1.message)
    if not res1.ok:
        raise SystemExit(1)
    
    # Verify output file exists
    output_file = Path("outputs/reports/stats_by_time_10min.txt")
    csv_file = Path("outputs/reports/stats_by_time_10min.csv")
    if not output_file.exists():
        print(f"ERROR: Output file {output_file} does not exist")
        raise SystemExit(1)
    if not csv_file.exists():
        print(f"ERROR: CSV file {csv_file} does not exist")
        raise SystemExit(1)
    
    print(f"✓ Created {output_file}")
    print(f"✓ Created {csv_file}")
    
    # Show a few lines from the text file
    with open(output_file, 'r') as f:
        lines = f.readlines()[:15]  # First 15 lines
        print("\nFirst few lines of output:")
        print("".join(lines))
    
    # Test 2: Stats by time with multiple columns
    print("\n=== Test 2: Stats by time (5min) for multiple columns ===")
    # Get another column if available
    cols_to_test = [ycol]
    if len(numeric_cols) > 1:
        other_col = [c for c in numeric_cols if c != ycol][0]
        cols_to_test.append(other_col)
    
    cmd2 = interpreter.parse_command(f"stats by time 5min columns={','.join(cols_to_test)}")
    res2 = executor.execute(cmd2)
    print(res2.message)
    if not res2.ok:
        raise SystemExit(1)
    
    # Test 3: Stats by time with outlier filtering
    print("\n=== Test 3: Stats by time with outlier filtering ===")
    cmd3 = interpreter.parse_command(
        f"stats by time 10min columns={ycol} outliers=zscore z_thresh=2.5"
    )
    res3 = executor.execute(cmd3)
    print(res3.message)
    if not res3.ok:
        raise SystemExit(1)
    
    # Test 4: Stats by time with date filtering
    print("\n=== Test 4: Stats by time with date filtering ===")
    # Get date range from data
    first_date = df['timestamp'].min().strftime('%Y-%m-%d')
    cmd4 = interpreter.parse_command(
        f"stats by time 15min columns={ycol} start_date={first_date}"
    )
    res4 = executor.execute(cmd4)
    print(res4.message)
    if not res4.ok:
        raise SystemExit(1)
    
    print("\n✓ All stats by time tests passed!")
