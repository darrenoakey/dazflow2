"""Tests for pipeline node types."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.config import ServerConfig, set_config

from .nodes import (
    NODE_TYPES,
    execute_state_check,
    execute_state_list,
    execute_state_read,
    execute_state_trigger,
    execute_state_write,
    execute_state_clear_failure,
    register_state_trigger,
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory and configure it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set the config to use temp dir
        set_config(ServerConfig(port=5000, data_dir=tmpdir))
        yield tmpdir


class TestNodeTypeRegistration:
    """Test that node types are properly registered."""

    def test_all_node_types_registered(self):
        assert "state_trigger" in NODE_TYPES
        assert "state_read" in NODE_TYPES
        assert "state_write" in NODE_TYPES
        assert "state_check" in NODE_TYPES
        assert "state_list" in NODE_TYPES
        assert "state_clear_failure" in NODE_TYPES

    def test_state_trigger_has_register(self):
        assert "register" in NODE_TYPES["state_trigger"]
        assert callable(NODE_TYPES["state_trigger"]["register"])

    def test_all_have_execute(self):
        for node_id, node_def in NODE_TYPES.items():
            assert "execute" in node_def, f"{node_id} missing execute"
            assert callable(node_def["execute"]), f"{node_id} execute not callable"


class TestStateTrigger:
    """Tests for state_trigger node."""

    def test_execute_with_no_entities(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "input/{id}/",
        }
        result = execute_state_trigger(node_data, [], None)
        assert len(result) == 1
        assert "error" in result[0]

    def test_execute_with_entity(self, temp_data_dir):
        # Create source directory
        (Path(temp_data_dir) / "output" / "input" / "test-1").mkdir(parents=True)
        (Path(temp_data_dir) / "output" / "input" / "test-1" / "data.txt").write_text("content")

        node_data = {
            "state_root": "output/",
            "pattern": "input/{id}/",
        }
        result = execute_state_trigger(node_data, [], None)

        assert len(result) == 1
        assert result[0]["entity_id"] == "test-1"
        assert result[0]["pattern"] == "input/{id}/"
        assert "triggered_at" in result[0]

    def test_register_with_no_pattern(self, temp_data_dir):
        node_data = {"state_root": "output/"}
        result = register_state_trigger(node_data, None, None)

        assert result["type"] == "timed"
        assert "error" in result

    def test_register_with_entities(self, temp_data_dir):
        # Create source directory
        (Path(temp_data_dir) / "output" / "input" / "test-1").mkdir(parents=True)

        node_data = {
            "state_root": "output/",
            "pattern": "input/{id}/",
            "scan_interval": 30,
        }
        result = register_state_trigger(node_data, None, None)

        assert result["type"] == "timed"
        assert result["pending_count"] == 1
        assert result["entity_id"] == "test-1"


class TestStateRead:
    """Tests for state_read node."""

    def test_read_missing_state(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
            "entity_id": "test-1",
        }
        result = execute_state_read(node_data, [], None)

        assert len(result) == 1
        assert result[0]["exists"] is False

    def test_read_existing_state(self, temp_data_dir):
        # Create state file
        (Path(temp_data_dir) / "output" / "data").mkdir(parents=True)
        (Path(temp_data_dir) / "output" / "data" / "test-1.txt").write_text("Hello World")

        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
            "entity_id": "test-1",
        }
        result = execute_state_read(node_data, [], None)

        assert len(result) == 1
        assert result[0]["exists"] is True
        assert result[0]["content"] == "Hello World"

    def test_read_json_content(self, temp_data_dir):
        # Create JSON state file
        (Path(temp_data_dir) / "output" / "data").mkdir(parents=True)
        (Path(temp_data_dir) / "output" / "data" / "test-1.json").write_text('{"name": "test"}')

        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.json",
            "entity_id": "test-1",
        }
        result = execute_state_read(node_data, [], None)

        assert len(result) == 1
        assert result[0]["content"] == {"name": "test"}

    def test_read_entity_from_input(self, temp_data_dir):
        # Create state file
        (Path(temp_data_dir) / "output" / "data").mkdir(parents=True)
        (Path(temp_data_dir) / "output" / "data" / "from-input.txt").write_text("content")

        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
        }
        input_data = [{"entity_id": "from-input"}]
        result = execute_state_read(node_data, input_data, None)

        assert result[0]["exists"] is True
        assert result[0]["entity_id"] == "from-input"


class TestStateWrite:
    """Tests for state_write node."""

    def test_write_creates_file(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "results/{id}.txt",
            "entity_id": "test-1",
            "content": "Test output",
        }
        result = execute_state_write(node_data, [], None)

        assert len(result) == 1
        assert result[0]["success"] is True
        assert result[0]["path"] == "results/test-1.txt"

        # Verify file exists
        path = Path(temp_data_dir) / "output" / "results" / "test-1.txt"
        assert path.exists()
        assert path.read_text() == "Test output"

    def test_write_creates_manifest(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "results/{id}.txt",
            "entity_id": "test-1",
            "content": "Test output",
            "_code_hash": "abc12345",
        }
        execute_state_write(node_data, [], None)

        # Check manifest exists
        manifest_path = Path(temp_data_dir) / "output" / ".dazflow" / "manifests" / "test-1.json"
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text())
        assert "results/{id}.txt" in manifest["states"]
        assert manifest["states"]["results/{id}.txt"]["code_hash"] == "abc12345"

    def test_write_validates_min_size(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "results/{id}.txt",
            "entity_id": "test-1",
            "content": "tiny",
            "min_size": 100,
        }
        result = execute_state_write(node_data, [], None)

        assert len(result) == 1
        assert "error" in result[0]
        assert "too small" in result[0]["error"]

    def test_write_uses_input_content(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "results/{id}.json",
            "entity_id": "test-1",
        }
        input_data = [{"entity_id": "test-1", "content": {"result": 42}}]
        result = execute_state_write(node_data, input_data, None)

        assert result[0]["success"] is True

        path = Path(temp_data_dir) / "output" / "results" / "test-1.json"
        content = json.loads(path.read_text())
        assert content == {"result": 42}


class TestStateCheck:
    """Tests for state_check node."""

    def test_check_missing_state(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
            "entity_id": "test-1",
        }
        result = execute_state_check(node_data, [], None)

        assert len(result) == 1
        assert result[0]["exists"] is False

    def test_check_existing_state(self, temp_data_dir):
        # Create state file
        (Path(temp_data_dir) / "output" / "data").mkdir(parents=True)
        (Path(temp_data_dir) / "output" / "data" / "test-1.txt").write_text("content")

        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
            "entity_id": "test-1",
        }
        result = execute_state_check(node_data, [], None)

        assert len(result) == 1
        assert result[0]["exists"] is True


class TestStateList:
    """Tests for state_list node."""

    def test_list_empty(self, temp_data_dir):
        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
        }
        result = execute_state_list(node_data, [], None)

        assert len(result) == 1
        assert result[0]["count"] == 0

    def test_list_multiple_entities(self, temp_data_dir):
        # Create multiple state files
        (Path(temp_data_dir) / "output" / "data").mkdir(parents=True)
        (Path(temp_data_dir) / "output" / "data" / "item-1.txt").write_text("a")
        (Path(temp_data_dir) / "output" / "data" / "item-2.txt").write_text("b")
        (Path(temp_data_dir) / "output" / "data" / "item-3.txt").write_text("c")

        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
        }
        result = execute_state_list(node_data, [], None)

        assert len(result) == 3
        entity_ids = [r["entity_id"] for r in result]
        assert "item-1" in entity_ids
        assert "item-2" in entity_ids
        assert "item-3" in entity_ids


class TestStateClearFailure:
    """Tests for state_clear_failure node."""

    def test_clear_failure(self, temp_data_dir):
        from src.pipeline.state_store import StateStore

        # First record a failure
        store = StateStore(Path(temp_data_dir) / "output")
        store.init()
        store.record_failure("test-1", "data/{id}.txt", "Test error")

        # Verify failure exists
        failure = store.get_failure("test-1", "data/{id}.txt")
        assert failure is not None

        # Clear it
        node_data = {
            "state_root": "output/",
            "pattern": "data/{id}.txt",
            "entity_id": "test-1",
        }
        result = execute_state_clear_failure(node_data, [], None)

        assert result[0]["success"] is True

        # Verify failure cleared
        failure = store.get_failure("test-1", "data/{id}.txt")
        assert failure is None


class TestIntegration:
    """Integration tests for pipeline node workflows."""

    def test_trigger_read_write_flow(self, temp_data_dir):
        """Test a complete pipeline: trigger -> read -> process -> write."""
        # Setup: create source data
        (Path(temp_data_dir) / "output" / "input" / "doc-1").mkdir(parents=True)
        (Path(temp_data_dir) / "output" / "input" / "doc-1" / "content.txt").write_text("hello world")

        # Step 1: Trigger
        trigger_data = {"state_root": "output/", "pattern": "input/{id}/"}
        trigger_result = execute_state_trigger(trigger_data, [], None)
        entity_id = trigger_result[0]["entity_id"]
        assert entity_id == "doc-1"

        # Step 2: Read input
        read_data = {"state_root": "output/", "pattern": "input/{id}/content.txt"}
        read_result = execute_state_read(read_data, [{"entity_id": entity_id}], None)
        content = read_result[0]["content"]
        assert content == "hello world"

        # Step 3: Process (simulate with uppercase)
        processed = content.upper()

        # Step 4: Write output
        write_data = {
            "state_root": "output/",
            "pattern": "output/{id}.txt",
            "entity_id": entity_id,
            "content": processed,
            "_code_hash": "process1",
        }
        write_result = execute_state_write(write_data, [], None)
        assert write_result[0]["success"] is True

        # Verify output exists
        output_path = Path(temp_data_dir) / "output" / "output" / "doc-1.txt"
        assert output_path.read_text() == "HELLO WORLD"

        # Step 5: Check that output exists
        check_data = {
            "state_root": "output/",
            "pattern": "output/{id}.txt",
            "entity_id": entity_id,
        }
        check_result = execute_state_check(check_data, [], None)
        assert check_result[0]["exists"] is True
