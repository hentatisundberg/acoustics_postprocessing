import os
import sys

# Ensure project root is on sys.path when running via `python tests/...`
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from interface.task_executor import TaskExecutor
from interface.nlp_interpreter import CommandInterpreter

if __name__ == "__main__":
    executor = TaskExecutor()
    interpreter = CommandInterpreter()
    # Load default data paths from config
    load_cmd = interpreter.parse_command(
        "load dir=data/data pattern=*.csv positions=data/positions/positions.txt"
    )
    res = executor.execute(load_cmd)
    print(res.message)
    if not res.ok:
        raise SystemExit(1)
    # Choose a sensible numeric column to plot
    df = executor.merged.copy()
    ignore = {"timestamp", "latitude", "longitude", "position_matched"}
    numeric_cols = [c for c in df.select_dtypes(include=["number"]).columns if c not in ignore]
    assert numeric_cols, "No numeric columns available for boxplot"
    preferred = None
    for candidate in ("backscatter", "depth", "nasc0", "wave_depth"):
        if candidate in numeric_cols:
            preferred = candidate
            break
    preferred = preferred or numeric_cols[0]
    print("Boxplot column:", preferred)
    # Boxplot basic
    cmd = interpreter.parse_command(
        f"boxplot y:{preferred} show=false save=true out=outputs/plots/smoke_boxplot.png"
    )
    res2 = executor.execute(cmd)
    print(res2.message)
    if not res2.ok:
        raise SystemExit(1)
    if res2.artifact:
        print(f"Saved: {res2.artifact}")
