from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.io_helpers import ensure_directory

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, cache_dir: Path = Path("./cache")):
        self.cache_dir = Path(cache_dir)
        ensure_directory(self.cache_dir)

    def _cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.parquet"

    def _meta_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def save_to_cache(self, data: pd.DataFrame, cache_key: str) -> None:
        path = self._cache_path(cache_key)
        meta = self._meta_path(cache_key)
        data.to_parquet(path, index=False)
        meta.write_text(json.dumps({"saved_at": datetime.utcnow().isoformat()}), encoding="utf-8")
        logger.info("Saved cache: %s", path)

    def load_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(cache_key)
        if path.exists():
            logger.info("Loading from cache: %s", path)
            return pd.read_parquet(path)
        return None

    def clear_cache(self, older_than: Optional[timedelta] = None) -> None:
        for p in self.cache_dir.glob("*.parquet"):
            if older_than is None:
                p.unlink(missing_ok=True)
                meta = p.with_suffix(".json")
                meta.unlink(missing_ok=True)
            else:
                meta = p.with_suffix(".json")
                if meta.exists():
                    try:
                        info = json.loads(meta.read_text(encoding="utf-8"))
                        saved_at = datetime.fromisoformat(info.get("saved_at"))
                        if datetime.utcnow() - saved_at > older_than:
                            p.unlink(missing_ok=True)
                            meta.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        continue
