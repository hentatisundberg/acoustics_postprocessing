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
    # Scatter with date filtering (save to file)
    cmd = interpreter.parse_command(
        f"scatter y:{ycol} start_date=2024-10-06 end_date=2024-10-06 show=false save=true out=outputs/plots/smoke_scatter_date.png"
    )
    res2 = executor.execute(cmd)
    print(res2.message)
    if not res2.ok:
        raise SystemExit(1)
