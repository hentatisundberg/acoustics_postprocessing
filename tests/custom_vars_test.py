from pathlib import Path

from interface.nlp_interpreter import CommandInterpreter
from interface.task_executor import TaskExecutor


def run_test():
    print("Running custom variable alias test...")
    interpreter = CommandInterpreter()
    executor = TaskExecutor(Path("config/settings.yaml"))

    # Define aliases
    cmd = interpreter.parse_command("alias bs=backscatter temp_w=temp_water")
    ok, err = interpreter.validate_command(cmd)
    assert ok, f"Alias command should be valid: {err}"
    res = executor.execute(cmd)
    assert res.ok, f"Executor failed to add aliases: {res.message}"

    # Verify resolution
    assert executor._resolve_column("bs") == "backscatter", "Alias 'bs' -> 'backscatter' failed"
    assert executor._resolve_column("temp_w") == "temp_water", "Alias 'temp_w' -> 'temp_water' failed"
    assert executor._resolve_column("unchanged") == "unchanged", "Unaliased names should pass-through"

    # Aggregate with explicit var name (no data loaded; just check command parsing)
    cmd2 = interpreter.parse_command("aggregate time 5min y=bs")
    ok2, err2 = interpreter.validate_command(cmd2)
    assert ok2, f"Aggregate command should be valid: {err2}"
    assert cmd2.get("y") == "bs", "Interpreter should keep user var name in command"

    print("All alias tests passed.")


if __name__ == "__main__":
    run_test()
