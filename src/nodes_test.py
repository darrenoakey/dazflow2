"""Tests for node type definitions."""

from src.nodes import (
    NODE_TYPES,
    execute_append_to_file,
    execute_hardwired,
    execute_http,
    execute_if,
    execute_rss,
    execute_scheduled,
    execute_set,
    execute_start,
    execute_transform,
    get_node_type,
)


# ##################################################################
# test execute_start
# verifies start node returns empty item
def test_execute_start_returns_empty_item():
    result = execute_start({}, None)
    assert result == [{}]


# ##################################################################
# test execute_scheduled
# verifies scheduled node returns timestamp
def test_execute_scheduled_returns_timestamp():
    result = execute_scheduled({}, None)
    assert len(result) == 1
    assert "time" in result[0]
    # ISO format contains T separator
    assert "T" in result[0]["time"]


# ##################################################################
# test execute_hardwired
# verifies hardwired node parses json correctly
def test_execute_hardwired_valid_json():
    node_data = {"json": '[{"name": "test"}, {"name": "test2"}]'}
    result = execute_hardwired(node_data, None)
    assert result == [{"name": "test"}, {"name": "test2"}]


def test_execute_hardwired_invalid_json():
    node_data = {"json": "not valid json"}
    result = execute_hardwired(node_data, None)
    assert len(result) == 1
    assert result[0]["error"] == "Invalid JSON"


def test_execute_hardwired_empty_json():
    node_data = {"json": "[]"}
    result = execute_hardwired(node_data, None)
    assert result == []


# ##################################################################
# test execute_set
# verifies set node creates output with fields
def test_execute_set_with_fields():
    node_data = {
        "fields": [
            {"name": "greeting", "value": '"hello"'},
            {"name": "count", "value": "42"},
        ]
    }
    result = execute_set(node_data, {})
    assert result["greeting"] == "hello"
    assert result["count"] == 42


def test_execute_set_empty_fields():
    node_data = {"fields": []}
    result = execute_set(node_data, {})
    assert result == {}


def test_execute_set_field_without_name_ignored():
    node_data = {"fields": [{"name": "", "value": "test"}]}
    result = execute_set(node_data, {})
    assert result == {}


# ##################################################################
# test execute_transform
# verifies transform node returns expression result
def test_execute_transform():
    node_data = {"expression": "transformed_value"}
    result = execute_transform(node_data, {})
    assert result == {"result": "transformed_value"}


def test_execute_transform_empty_expression():
    node_data = {"expression": ""}
    result = execute_transform(node_data, {})
    assert result == {"result": ""}


# ##################################################################
# test execute_if
# verifies if node filters based on condition
def test_execute_if_true_condition():
    node_data = {"condition": "true"}
    input_data = [{"x": 1}]
    result = execute_if(node_data, input_data)
    assert result == [{"x": 1}]


def test_execute_if_false_condition():
    node_data = {"condition": "false"}
    input_data = [{"x": 1}]
    result = execute_if(node_data, input_data)
    assert result == []


def test_execute_if_empty_string_is_falsy():
    node_data = {"condition": ""}
    input_data = [{"x": 1}]
    result = execute_if(node_data, input_data)
    assert result == []


def test_execute_if_null_is_falsy():
    node_data = {"condition": "null"}
    input_data = [{"x": 1}]
    result = execute_if(node_data, input_data)
    assert result == []


def test_execute_if_zero_is_falsy():
    node_data = {"condition": "0"}
    input_data = [{"x": 1}]
    result = execute_if(node_data, input_data)
    assert result == []


def test_execute_if_single_item_input():
    node_data = {"condition": "true"}
    input_data = {"x": 1}
    result = execute_if(node_data, input_data)
    assert result == [{"x": 1}]


# ##################################################################
# test execute_http
# verifies http node returns placeholder
def test_execute_http():
    node_data = {"url": "https://example.com", "method": "POST"}
    result = execute_http(node_data, None)
    assert result == [{"url": "https://example.com", "method": "POST", "status": "not_implemented"}]


def test_execute_http_defaults():
    node_data = {}
    result = execute_http(node_data, None)
    assert result == [{"url": "", "method": "GET", "status": "not_implemented"}]


# ##################################################################
# test execute_rss
# verifies rss node returns placeholder
def test_execute_rss():
    node_data = {"url": "https://example.com/feed"}
    result = execute_rss(node_data, None)
    assert result == [{"feed_url": "https://example.com/feed", "status": "not_implemented"}]


# ##################################################################
# test execute_append_to_file
# verifies append_to_file node writes content to file
def test_execute_append_to_file(tmp_path):
    filepath = tmp_path / "output" / "test.txt"
    node_data = {"filepath": str(filepath), "content": "hello world"}
    result = execute_append_to_file(node_data, None)
    assert result == [{"written": True, "filepath": str(filepath)}]
    assert filepath.exists()
    assert filepath.read_text() == "hello world\n"


def test_execute_append_to_file_appends(tmp_path):
    filepath = tmp_path / "test.txt"
    filepath.write_text("existing\n")
    node_data = {"filepath": str(filepath), "content": "new line"}
    execute_append_to_file(node_data, None)
    assert filepath.read_text() == "existing\nnew line\n"


def test_execute_append_to_file_empty_filepath():
    node_data = {"filepath": "", "content": "test"}
    result = execute_append_to_file(node_data, None)
    assert result == [{"written": False, "filepath": ""}]


# ##################################################################
# test NODE_TYPES registry
# verifies registry has expected structure
def test_node_types_registry_contains_all_types():
    expected_types = ["start", "scheduled", "hardwired", "set", "transform", "if", "http", "rss", "append_to_file"]
    for type_id in expected_types:
        assert type_id in NODE_TYPES
        assert "execute" in NODE_TYPES[type_id]
        assert "kind" in NODE_TYPES[type_id]


def test_node_types_kinds_are_valid():
    for type_id, node_type in NODE_TYPES.items():
        assert node_type["kind"] in ["map", "array"], f"{type_id} has invalid kind"


# ##################################################################
# test get_node_type
# verifies get_node_type returns correct type or None
def test_get_node_type_returns_type():
    result = get_node_type("scheduled")
    assert result is not None
    assert result["kind"] == "array"


def test_get_node_type_returns_none_for_unknown():
    result = get_node_type("nonexistent")
    assert result is None
