# File: bot/cache.py
"""
File-based deduplication cache for cross-run article tracking.

Stores URL hashes of previously published articles in a JSON file.
Entries expire after a configurable TTL to prevent unbounded growth.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Lambda only allows writes to /tmp. CACHE_DIR env var overrides default.
_CACHE_DIR = Path(os.environ.get(
    "CACHE_DIR",
    str(Path(__file__).resolve().parent.parent / "data"),
))
_CACHE_FILE = _CACHE_DIR / "seen_articles.json"
_TTL_HOURS = 72  # purge entries older than 3 days


def _load_cache() -> dict[str, str]:
    """Load the cache dict {url_hash: iso_timestamp}."""
    if not _CACHE_FILE.exists():
        return {}
    try:
        with open(_CACHE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"Cache read failed, starting fresh: {exc}")
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    """Persist the cache dict atomically (write → rename)."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=_CACHE_DIR, suffix=".tmp")
    try:
        with open(tmp_fd, "w") as f:
            json.dump(cache, f, indent=2)
        Path(tmp_path).replace(_CACHE_FILE)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _purge_expired(cache: dict[str, str]) -> dict[str, str]:
    """Remove entries older than _TTL_HOURS."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_TTL_HOURS)
    return {
        h: ts for h, ts in cache.items()
        if datetime.fromisoformat(ts) > cutoff
    }


def filter_unseen(url_hashes: list[str]) -> set[str]:
    """Return the subset of url_hashes that have NOT been seen before."""
    cache = _load_cache()
    cache = _purge_expired(cache)
    _save_cache(cache)
    return {h for h in url_hashes if h not in cache}


def mark_seen(url_hashes: list[str]) -> None:
    """Record url_hashes as published. Call after successful Teams post."""
    cache = _load_cache()
    now_iso = datetime.now(timezone.utc).isoformat()
    for h in url_hashes:
        cache[h] = now_iso
    cache = _purge_expired(cache)
    _save_cache(cache)
    logger.info(f"Cache updated: {len(url_hashes)} new, {len(cache)} total entries.")
