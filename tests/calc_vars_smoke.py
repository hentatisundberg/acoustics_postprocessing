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
    
    # Test 1: Create hour variable from timestamp
    print("\n=== Test 1: Create hour from timestamp ===")
    cmd1 = interpreter.parse_command("create hour from timestamp")
    res1 = executor.execute(cmd1)
    print(res1.message)
    if not res1.ok:
        raise SystemExit(1)
    
    # Verify hour column exists
    if "hour" not in executor.merged.columns:
        print("ERROR: hour column was not created")
        raise SystemExit(1)
    print(f"Hour values sample: {executor.merged['hour'].head().tolist()}")
    
    # Test 2: Create calculated variable using expression
    print("\n=== Test 2: Create calculated variable with expression ===")
    # Pick a typical column
    df = executor.merged.copy()
    ignore = {"timestamp", "latitude", "longitude", "position_matched", "hour"}
    numeric_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in ignore]
    ycol = "backscatter" if "backscatter" in numeric_cols else ("depth" if "depth" in numeric_cols else numeric_cols[0])
    
    cmd2 = interpreter.parse_command(f"calc {ycol}_doubled={ycol}*2")
    res2 = executor.execute(cmd2)
    print(res2.message)
    if not res2.ok:
        raise SystemExit(1)
    
    # Verify new column exists
    new_col = f"{ycol}_doubled"
    if new_col not in executor.merged.columns:
        print(f"ERROR: {new_col} column was not created")
        raise SystemExit(1)
    print(f"{new_col} values sample: {executor.merged[new_col].head().tolist()}")
    
    # Test 3: Create day of week variable
    print("\n=== Test 3: Create day of week from timestamp ===")
    cmd3 = interpreter.parse_command("create var dayofweek=timestamp.dt.dayofweek")
    res3 = executor.execute(cmd3)
    print(res3.message)
    if not res3.ok:
        raise SystemExit(1)
    
    # Verify dayofweek column exists
    if "dayofweek" not in executor.merged.columns:
        print("ERROR: dayofweek column was not created")
        raise SystemExit(1)
    print(f"Day of week values sample: {executor.merged['dayofweek'].head().tolist()}")
    
    # Test 4: Plot using calculated variable
    print("\n=== Test 4: Plot using calculated variable ===")
    cmd4 = interpreter.parse_command(
        f"plot y:{new_col} 5min save=true show=false out=outputs/plots/smoke_calc_var_plot.png"
    )
    res4 = executor.execute(cmd4)
    print(res4.message)
    if not res4.ok:
        raise SystemExit(1)
    
    # Test 5: List columns to see new variables
    print("\n=== Test 5: List columns (should include new variables) ===")
    cmd5 = interpreter.parse_command("columns")
    res5 = executor.execute(cmd5)
    print(res5.message)
    
    print("\n✓ All calculated variable tests passed!")
