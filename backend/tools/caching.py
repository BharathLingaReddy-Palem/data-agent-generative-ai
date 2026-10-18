"""
caching.py — High-Performance Analysis & Query Caching Layer (Phase 4)
======================================================================
Optional cache helpers using SHA-256 dataset fingerprints and query signatures.
These helpers are not wired into the application pipeline or SQL endpoint.

Features:
  - Full dataset content hashing (all rows, index, schema)
  - In-memory dictionary + persistent disk-backed storage (no LRU bound)
  - TTL (time-to-live) expiration support
"""
import os
import json
import time
import pickle
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import pandas as pd
from backend.services.dataset_fingerprint import dataset_fingerprint

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "analysis"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory fast lookup cache
_MEMORY_CACHE: Dict[str, Tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 86400 * 7  # 7 days


def compute_dataset_fingerprint(df: pd.DataFrame, extra_key: str = "") -> str:
    """
    Computes a deterministic SHA-256 hash representing the DataFrame content and any extra query key.
    """
    content = dataset_fingerprint(df)
    if not isinstance(extra_key, str):
        raise TypeError('Cache query key must be a string.')
    if not extra_key:
        return content
    # Preserve SQL/string literal case and whitespace; they can change results.
    payload = json.dumps([content, extra_key], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(b'ds-agent:query:v2\0' + payload.encode('utf-8')).hexdigest()


def get_cached_result(cache_key: str) -> Optional[Any]:
    """
    Retrieves cached item if present and not expired. Checks in-memory first, then disk.
    """
    now = time.time()

    # 1. Check in-memory
    if cache_key in _MEMORY_CACHE:
        timestamp, data = _MEMORY_CACHE[cache_key]
        if now - timestamp < CACHE_TTL_SECONDS:
            logger.info(f"Memory cache hit for key: {cache_key[:12]}")
            return data

    # 2. Check disk cache
    cache_file = CACHE_DIR / f"{cache_key}.pkl"
    if cache_file.exists():
        try:
            with open(cache_file, "rb") as f:
                timestamp, data = pickle.load(f)
            if now - timestamp < CACHE_TTL_SECONDS:
                # Promote to memory cache
                _MEMORY_CACHE[cache_key] = (timestamp, data)
                logger.info(f"Disk cache hit for key: {cache_key[:12]}")
                return data
            else:
                cache_file.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to read cache file: {e}")

    return None


def set_cached_result(cache_key: str, data: Any) -> None:
    """
    Stores an item in both in-memory and disk cache.
    """
    now = time.time()
    _MEMORY_CACHE[cache_key] = (now, data)

    cache_file = CACHE_DIR / f"{cache_key}.pkl"
    try:
        with open(cache_file, "wb") as f:
            pickle.dump((now, data), f)
        logger.info(f"Cached result saved for key: {cache_key[:12]}")
    except Exception as e:
        logger.warning(f"Failed to write disk cache: {e}")


def clear_cache() -> int:
    """
    Clears all in-memory and disk cache files. Returns count of files deleted.
    """
    _MEMORY_CACHE.clear()
    count = 0
    for f in CACHE_DIR.glob("*.pkl"):
        try:
            f.unlink()
            count += 1
        except Exception:
            pass
    return count
