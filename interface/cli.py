from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from interface.nlp_interpreter import CommandInterpreter
from interface.task_executor import TaskExecutor


def main() -> None:
    console = Console()
    console.print(
        "Acoustics Analysis CLI — type 'help' or 'exit'\n"
        "Scatter: scatter y:<col> [x:<col>] [smooth=loess|true|false] [frac=0.1] (default x=timestamp)",
        style="bold green",
    )

    interpreter = CommandInterpreter()
    executor = TaskExecutor(Path("config/settings.yaml"))

    while True:
        try:
            user_input = Prompt.ask("»")
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!", style="bold yellow")
            break

        # Ignore empty input lines to avoid unintended defaults
        if not user_input.strip():
            continue

        # Add support for 'coords' command
        if user_input.strip().lower() == "coords":
            result = executor.execute({"task": "coords_info"})
            style = "green" if result.ok else "red"
            console.print(result.message, style=style)
            continue

        cmd = interpreter.parse_command(user_input)
        ok, err = interpreter.validate_command(cmd)
        if not ok:
            console.print(f"Invalid command: {err}", style="bold red")
            continue
        result = executor.execute(cmd)
        if result.message == "exit":
            console.print("Bye!", style="bold yellow")
            break
        style = "green" if result.ok else "red"
        console.print(result.message, style=style)
        if result.artifact:
            console.print(f"Artifact: {result.artifact}")


if __name__ == "__main__":
    main()
