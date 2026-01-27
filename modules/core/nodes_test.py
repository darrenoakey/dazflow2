"""Tests for core node type definitions.

Note: Main tests are in src/nodes_test.py. This file provides additional coverage.
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.core.nodes import (
    NODE_TYPES,
    execute_start,
    execute_scheduled,
    execute_hardwired,
    execute_set,
    execute_transform,
    execute_if,
    execute_http,
    execute_rss,
    execute_append_to_file,
    register_scheduled,
)


# ##################################################################
# test NODE_TYPES registry structure
def test_node_types_registry_exists():
    assert NODE_TYPES is not None
    assert isinstance(NODE_TYPES, dict)


def test_node_types_registry_has_execute_functions():
    for type_id, node_type in NODE_TYPES.items():
        assert "execute" in node_type, f"{type_id} missing execute function"
        assert callable(node_type["execute"]), f"{type_id} execute is not callable"


def test_node_types_registry_has_kind():
    for type_id, node_type in NODE_TYPES.items():
        assert "kind" in node_type, f"{type_id} missing kind"
        assert node_type["kind"] in ["map", "array"], f"{type_id} has invalid kind"


# ##################################################################
# test execute functions accept credential_data parameter
def test_execute_start_accepts_credential_data():
    # Third param is _credential_data (internal underscore convention)
    result = execute_start({}, None, None)
    assert result == [{}]


def test_execute_scheduled_accepts_credential_data():
    result = execute_scheduled({}, None, None)
    assert len(result) == 1
    assert "time" in result[0]


def test_execute_hardwired_accepts_credential_data():
    result = execute_hardwired({"json": "[{}]"}, None, None)
    assert result == [{}]


def test_execute_set_accepts_credential_data():
    result = execute_set({"fields": []}, {}, None)
    assert result == {}


def test_execute_transform_accepts_credential_data():
    result = execute_transform({"expression": "test"}, {}, None)
    assert result == {"result": "test"}


def test_execute_if_accepts_credential_data():
    result = execute_if({"condition": "true"}, [{}], None)
    assert result == [{}]


def test_execute_http_accepts_credential_data():
    result = execute_http({}, None, None)
    assert "status" in result[0]


def test_execute_rss_accepts_credential_data():
    result = execute_rss({"url": "http://test"}, None, None)
    assert "feed_url" in result[0]


def test_execute_append_to_file_accepts_credential_data(tmp_path):
    filepath = tmp_path / "test.txt"
    result = execute_append_to_file(
        {"filepath": str(filepath), "content": "test"},
        None,
        None,
    )
    assert result[0]["written"] is True


# ##################################################################
# test register_scheduled
def test_register_scheduled_returns_timing_info():
    node_data = {"interval": 5, "unit": "minutes"}
    result = register_scheduled(node_data, lambda: None)
    assert result["type"] == "timed"
    assert "trigger_at" in result
    assert result["interval_seconds"] == 300


def test_register_scheduled_calculates_next_trigger():
    import time

    node_data = {"interval": 1, "unit": "hours"}
    last_time = time.time() - 3600  # 1 hour ago
    result = register_scheduled(node_data, lambda: None, last_execution_time=last_time)
    # Should trigger now since interval has passed
    assert result["trigger_at"] <= time.time()


def test_register_scheduled_uses_defaults():
    node_data = {}
    result = register_scheduled(node_data, lambda: None)
    # Default is 5 minutes = 300 seconds
    assert result["interval_seconds"] == 300


# ##################################################################
# test register_scheduled with cron mode
def test_register_scheduled_cron_mode_returns_timing_info():
    node_data = {"mode": "cron", "cron": "*/5 * * * *"}
    result = register_scheduled(node_data, lambda: None)
    assert result["type"] == "timed"
    assert "trigger_at" in result
    assert result["cron"] == "*/5 * * * *"


def test_register_scheduled_cron_mode_calculates_future_trigger():
    import time

    node_data = {"mode": "cron", "cron": "0 * * * *"}  # Every hour at minute 0
    result = register_scheduled(node_data, lambda: None)
    # Trigger should be in the future
    assert result["trigger_at"] > time.time()


def test_register_scheduled_cron_mode_with_last_execution():
    import time

    node_data = {"mode": "cron", "cron": "*/5 * * * *"}
    last_time = time.time() - 60  # 1 minute ago
    result = register_scheduled(node_data, lambda: None, last_execution_time=last_time)
    assert result["type"] == "timed"
    assert "trigger_at" in result


def test_register_scheduled_cron_mode_invalid_expression():
    node_data = {"mode": "cron", "cron": "invalid cron"}
    result = register_scheduled(node_data, lambda: None)
    # Should fall back gracefully with an error
    assert result["type"] == "timed"
    assert "error" in result
    assert result["interval_seconds"] == 300  # Falls back to 5-minute interval


def test_register_scheduled_interval_mode_explicit():
    # Verify interval mode still works when mode is explicitly set
    node_data = {"mode": "interval", "interval": 10, "unit": "seconds"}
    result = register_scheduled(node_data, lambda: None)
    assert result["type"] == "timed"
    assert result["interval_seconds"] == 10
    assert "cron" not in result


def test_register_scheduled_cron_weekday_expression():
    # Test a more complex cron expression: 9am on weekdays
    node_data = {"mode": "cron", "cron": "0 9 * * 1-5"}
    result = register_scheduled(node_data, lambda: None)
    assert result["type"] == "timed"
    assert result["cron"] == "0 9 * * 1-5"
    assert "trigger_at" in result
