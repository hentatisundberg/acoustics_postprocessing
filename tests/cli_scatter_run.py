from pathlib import Path
import os, sys

# Make repo importable
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from interface.task_executor import TaskExecutor
from interface.nlp_interpreter import CommandInterpreter

interpreter = CommandInterpreter()
executor = TaskExecutor(Path("config/settings.yaml"))

# Load sample data (try repo paths first)
params = {
    "dir": "./data/data",
    "pattern": "SLUAquaSailor*",
    "positions": "./data/data/positions.txt",
}
res = executor.execute({"task": "load", "params": params})
if not res.ok:
    params = {
        "dir": "./data",
        "pattern": "SLUAquaSailor*",
        "positions": "./data/positions.txt",
    }
    res = executor.execute({"task": "load", "params": params})
print(res.message)
assert res.ok, res.message

# Case 1: 'scatter depth' shorthand
cmd1 = interpreter.parse_command("scatter depth save=true show=false out=outputs/plots/cli_scatter_depth.png")
ok1, err1 = interpreter.validate_command(cmd1)
assert ok1, err1
res1 = executor.execute(cmd1)
print(res1.message)
assert res1.ok
assert res1.artifact and Path(str(res1.artifact)).exists()

# Case 2: 'scatter depth vs temperature' form
cmd2 = interpreter.parse_command("scatter depth vs temperature save=true show=false out=outputs/plots/cli_scatter_depth_vs_temperature.png")
ok2, err2 = interpreter.validate_command(cmd2)
assert ok2, err2
res2 = executor.execute(cmd2)
print(res2.message)
assert res2.ok
assert res2.artifact and Path(str(res2.artifact)).exists()

print("CLI scatter integration OK.")
