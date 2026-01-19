"""Persistent cache API for node types.

Provides a simple key-value cache that persists to disk.
Each module/node_type combination gets its own cache directory.
"""

import json
import threading
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = PROJECT_ROOT / "local" / "cache"

# Lock for thread-safe file operations
_cache_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_lock(cache_path: str) -> threading.Lock:
    """Get or create a lock for a cache path."""
    with _locks_lock:
        if cache_path not in _cache_locks:
            _cache_locks[cache_path] = threading.Lock()
        return _cache_locks[cache_path]


class NodeCache:
    """Persistent cache for a specific module/node_type.

    Usage:
        cache = NodeCache("discord", "discord_trigger")
        cache.set("servers", [{"id": "123", "name": "My Server"}])
        servers = cache.get("servers")  # Returns (value, timestamp) or (None, 0)
    """

    DEFAULT_TTL = 300  # 5 minutes

    def __init__(self, module: str, node_type: str):
        self.module = module
        self.node_type = node_type
        self.cache_dir = CACHE_DIR / module / node_type
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, key: str) -> Path:
        """Get the cache file path for a key."""
        # Sanitize key for filesystem
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> tuple[Any | None, float]:
        """Get cached value and timestamp.

        Returns:
            Tuple of (value, timestamp) or (None, 0) if not found
        """
        cache_file = self._cache_file(key)
        lock = _get_lock(str(cache_file))

        with lock:
            if not cache_file.exists():
                return None, 0

            try:
                data = json.loads(cache_file.read_text())
                return data.get("value"), data.get("timestamp", 0)
            except (json.JSONDecodeError, IOError):
                return None, 0

    def set(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        cache_file = self._cache_file(key)
        lock = _get_lock(str(cache_file))

        with lock:
            data = {"value": value, "timestamp": time.time()}
            cache_file.write_text(json.dumps(data))

    def is_stale(self, key: str, ttl: int | None = None) -> bool:
        """Check if cache is stale (older than ttl seconds).

        Args:
            key: Cache key
            ttl: Time-to-live in seconds (default: 300)

        Returns:
            True if cache is missing or older than ttl
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL

        _, timestamp = self.get(key)
        if timestamp == 0:
            return True

        return (time.time() - timestamp) > ttl

    def get_or_default(self, key: str, default: Any = None) -> Any:
        """Get cached value or return default if not found."""
        value, _ = self.get(key)
        return value if value is not None else default


# Registry of caches by module/node_type
_caches: dict[tuple[str, str], NodeCache] = {}


def get_cache(module: str, node_type: str) -> NodeCache:
    """Get or create a cache instance for a module/node_type."""
    key = (module, node_type)
    if key not in _caches:
        _caches[key] = NodeCache(module, node_type)
    return _caches[key]
