from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from rich.logging import RichHandler


def read_config(config_path: Path) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_directory(path: Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    handlers = [RichHandler(rich_tracebacks=True)]
    if log_file:
        ensure_directory(Path(log_file).parent)
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=handlers,
    )


def file_hash(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_network_read(path: Path, retry: int = 3):
    last_err = None
    for _ in range(retry):
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise last_err  # type: ignore[misc]
