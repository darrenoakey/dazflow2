"""Tests for node cache module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from node_cache import NodeCache, get_cache


def test_get_cache_returns_same_instance():
    cache1 = get_cache("test_module", "test_node")
    cache2 = get_cache("test_module", "test_node")
    assert cache1 is cache2


def test_get_cache_different_for_different_keys():
    cache1 = get_cache("module1", "node1")
    cache2 = get_cache("module2", "node2")
    assert cache1 is not cache2


def test_cache_set_and_get():
    cache = NodeCache("test", "set_get")
    cache.set("key1", {"foo": "bar"})
    value, timestamp = cache.get("key1")
    assert value == {"foo": "bar"}
    assert timestamp > 0


def test_cache_get_missing_key():
    cache = NodeCache("test", "missing")
    value, timestamp = cache.get("nonexistent")
    assert value is None
    assert timestamp == 0


def test_cache_get_or_default():
    cache = NodeCache("test", "default")
    cache.set("exists", "value")
    assert cache.get_or_default("exists", "default") == "value"
    assert cache.get_or_default("missing", "default") == "default"


def test_cache_is_stale_missing_key():
    cache = NodeCache("test", "stale_missing")
    assert cache.is_stale("missing") is True


def test_cache_is_stale_fresh():
    cache = NodeCache("test", "stale_fresh")
    cache.set("key", "value")
    assert cache.is_stale("key", ttl=300) is False


def test_cache_is_stale_old():
    cache = NodeCache("test", "stale_old")
    cache.set("key", "value")
    # Use negative TTL to guarantee staleness (any positive elapsed time > negative number)
    assert cache.is_stale("key", ttl=-1) is True


def test_cache_handles_special_characters_in_key():
    cache = NodeCache("test", "special")
    cache.set("key/with:special*chars", "value")
    value, _ = cache.get("key/with:special*chars")
    assert value == "value"


def test_cache_stores_complex_data():
    cache = NodeCache("test", "complex")
    data = {
        "servers": [
            {"id": "123", "name": "Server 1"},
            {"id": "456", "name": "Server 2"},
        ],
        "count": 42,
        "active": True,
    }
    cache.set("complex_data", data)
    value, _ = cache.get("complex_data")
    assert value == data
