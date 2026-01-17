"""Tests for the trigger registration and scheduling system."""

import json
import time

import pytest

from src.nodes import register_scheduled
from src.triggers import (
    find_trigger_nodes,
    get_enabled_workflows,
    init_trigger_system,
    set_workflow_enabled,
)
from src.worker import init_worker_system


# ##################################################################
# test init_trigger_system
# verifies directories are set up
def test_init_trigger_system(tmp_path):
    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)

    init_trigger_system(work_dir, workflows_dir)

    # Verify ENABLED_FILE path is set (file doesn't need to exist yet)
    from src.triggers import ENABLED_FILE

    assert ENABLED_FILE == work_dir / "enabled.json"


# ##################################################################
# test get_enabled_workflows
# verifies loading enabled state
def test_get_enabled_workflows_empty(tmp_path):
    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    init_trigger_system(work_dir, workflows_dir)

    # No enabled.json file exists
    enabled = get_enabled_workflows()
    assert enabled == {}


def test_get_enabled_workflows_with_data(tmp_path):
    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    init_trigger_system(work_dir, workflows_dir)

    # Create enabled.json
    enabled_file = work_dir / "enabled.json"
    enabled_file.write_text(json.dumps({"sample.json": True, "other.json": True}))

    enabled = get_enabled_workflows()
    assert enabled == {"sample.json": True, "other.json": True}


# ##################################################################
# test set_workflow_enabled
# verifies saving enabled state
def test_set_workflow_enabled(tmp_path):
    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    init_trigger_system(work_dir, workflows_dir)

    set_workflow_enabled("sample.json", True)

    enabled = get_enabled_workflows()
    assert enabled == {"sample.json": True}


def test_set_workflow_enabled_disable(tmp_path):
    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    init_trigger_system(work_dir, workflows_dir)

    # Enable first
    set_workflow_enabled("sample.json", True)
    assert get_enabled_workflows() == {"sample.json": True}

    # Disable
    set_workflow_enabled("sample.json", False)
    assert get_enabled_workflows() == {}


# ##################################################################
# test find_trigger_nodes
# verifies finding nodes with no inputs that have register functions
def test_find_trigger_nodes_scheduled():
    workflow = {
        "nodes": [
            {"id": "n1", "typeId": "scheduled", "name": "Schedule"},
            {"id": "n2", "typeId": "set", "name": "Set Data"},
        ],
        "connections": [{"sourceNodeId": "n1", "targetNodeId": "n2"}],
    }

    triggers = find_trigger_nodes(workflow)

    # Only scheduled has register function, and it has no inputs
    assert len(triggers) == 1
    assert triggers[0]["id"] == "n1"
    assert triggers[0]["typeId"] == "scheduled"


def test_find_trigger_nodes_no_triggers():
    workflow = {
        "nodes": [
            {"id": "n1", "typeId": "set", "name": "Set Data"},
        ],
        "connections": [],
    }

    triggers = find_trigger_nodes(workflow)

    # Set node has no register function
    assert len(triggers) == 0


def test_find_trigger_nodes_with_inputs():
    workflow = {
        "nodes": [
            {"id": "n1", "typeId": "start", "name": "Start"},
            {"id": "n2", "typeId": "scheduled", "name": "Schedule"},
        ],
        "connections": [{"sourceNodeId": "n1", "targetNodeId": "n2"}],
    }

    triggers = find_trigger_nodes(workflow)

    # scheduled has an input from start, so it's not a trigger
    # start has no register function
    assert len(triggers) == 0


def test_find_trigger_nodes_multiple():
    workflow = {
        "nodes": [
            {"id": "n1", "typeId": "scheduled", "name": "Schedule 1"},
            {"id": "n2", "typeId": "scheduled", "name": "Schedule 2"},
            {"id": "n3", "typeId": "set", "name": "Set Data"},
        ],
        "connections": [
            {"sourceNodeId": "n1", "targetNodeId": "n3"},
            {"sourceNodeId": "n2", "targetNodeId": "n3"},
        ],
    }

    triggers = find_trigger_nodes(workflow)

    # Both scheduled nodes are triggers
    assert len(triggers) == 2
    trigger_ids = [t["id"] for t in triggers]
    assert "n1" in trigger_ids
    assert "n2" in trigger_ids


# ##################################################################
# test register_scheduled
# verifies registration returns correct timing info
def test_register_scheduled_default():
    node_data = {}

    result = register_scheduled(node_data, lambda x: None)

    assert result["type"] == "timed"
    assert "trigger_at" in result
    assert result["interval_seconds"] == 300  # 5 minutes default


def test_register_scheduled_custom_interval():
    node_data = {"interval": 10, "unit": "seconds"}
    # Pass a recent last execution time so trigger_at is in the future
    last_exec = time.time() - 2  # 2 seconds ago

    result = register_scheduled(node_data, lambda x: None, last_exec)

    assert result["type"] == "timed"
    assert result["interval_seconds"] == 10
    # trigger_at should be last_exec + 10 = ~8 seconds from now
    assert result["trigger_at"] > time.time()
    assert result["trigger_at"] < time.time() + 10


def test_register_scheduled_no_previous_execution():
    """When there's no previous execution, should trigger immediately."""
    node_data = {"interval": 60, "unit": "seconds"}

    result = register_scheduled(node_data, lambda x: None, None)

    assert result["type"] == "timed"
    assert result["interval_seconds"] == 60
    # trigger_at should be now (immediate)
    assert result["trigger_at"] <= time.time()


def test_register_scheduled_past_trigger():
    """When last execution + interval is in the past, should trigger immediately."""
    node_data = {"interval": 10, "unit": "seconds"}
    # Last execution was 30 seconds ago, interval is 10s, so it's overdue
    last_exec = time.time() - 30

    result = register_scheduled(node_data, lambda x: None, last_exec)

    assert result["type"] == "timed"
    # Should trigger immediately (now)
    assert result["trigger_at"] <= time.time()


def test_register_scheduled_hours():
    node_data = {"interval": 2, "unit": "hours"}

    result = register_scheduled(node_data, lambda x: None)

    assert result["type"] == "timed"
    assert result["interval_seconds"] == 7200  # 2 hours


def test_register_scheduled_days():
    node_data = {"interval": 1, "unit": "days"}

    result = register_scheduled(node_data, lambda x: None)

    assert result["type"] == "timed"
    assert result["interval_seconds"] == 86400  # 1 day


# ##################################################################
# test queue_workflow with trigger data
# verifies pre-populated execution state
def test_queue_workflow_with_trigger(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    from src.worker import queue_workflow

    workflow = {
        "nodes": [{"id": "n1", "typeId": "scheduled", "name": "Schedule"}],
        "connections": [],
    }
    trigger_output = [{"Schedule": {"time": "2026-01-17T12:00:00"}}]

    queue_id = queue_workflow(
        "sample.json",
        workflow,
        trigger_node_id="n1",
        trigger_output=trigger_output,
    )

    # Read the queued item
    queue_files = list(queue_dir.glob("*.json"))
    assert len(queue_files) == 1

    item = json.loads(queue_files[0].read_text())
    assert item["id"] == queue_id

    # Verify trigger node is pre-populated in execution
    assert "n1" in item["execution"]
    assert item["execution"]["n1"]["nodeOutput"] == trigger_output
    assert item["execution"]["n1"]["output"] == trigger_output
    assert item["execution"]["n1"]["input"] == []


def test_queue_workflow_without_trigger(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    from src.worker import queue_workflow

    workflow = {
        "nodes": [{"id": "n1", "typeId": "scheduled", "name": "Schedule"}],
        "connections": [],
    }

    queue_id = queue_workflow("sample.json", workflow)

    # Read the queued item
    queue_files = list(queue_dir.glob("*.json"))
    assert len(queue_files) == 1

    item = json.loads(queue_files[0].read_text())
    assert item["id"] == queue_id

    # Verify execution is empty (no trigger pre-population)
    assert item["execution"] == {}


# ##################################################################
# test _make_trigger_callback
# verifies callback creates and queues workflow
def test_make_trigger_callback(tmp_path):
    from src.triggers import _make_trigger_callback

    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    queue_dir = work_dir / "queue"
    stats_dir = work_dir / "stats"

    init_trigger_system(work_dir, workflows_dir)
    init_worker_system(queue_dir, stats_dir)

    # Create a workflow file
    workflow = {
        "nodes": [{"id": "n1", "typeId": "scheduled", "name": "Schedule"}],
        "connections": [],
    }
    workflow_file = workflows_dir / "sample.json"
    workflow_file.write_text(json.dumps(workflow))

    # Create callback
    callback = _make_trigger_callback("sample.json", "n1", "Schedule")

    # Call the callback with trigger data
    callback({"time": "2026-01-17T12:00:00"})

    # Verify workflow was queued
    queue_files = list(queue_dir.glob("*.json"))
    assert len(queue_files) == 1

    item = json.loads(queue_files[0].read_text())
    assert item["workflow_path"] == "sample.json"
    assert "n1" in item["execution"]


def test_make_trigger_callback_missing_workflow(tmp_path):
    from src.triggers import _make_trigger_callback

    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    queue_dir = work_dir / "queue"
    stats_dir = work_dir / "stats"

    init_trigger_system(work_dir, workflows_dir)
    init_worker_system(queue_dir, stats_dir)

    # Create callback for non-existent workflow
    callback = _make_trigger_callback("nonexistent.json", "n1", "Schedule")

    # Call should not error, just return
    callback({"time": "2026-01-17T12:00:00"})

    # Nothing should be queued
    queue_files = list(queue_dir.glob("*.json"))
    assert len(queue_files) == 0


# ##################################################################
# test register_workflow_triggers
# verifies triggers are registered for a workflow


@pytest.mark.asyncio
async def test_register_workflow_triggers(tmp_path):
    from src.triggers import (
        _timed_tasks,
        register_workflow_triggers,
        unregister_workflow_triggers,
    )

    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    queue_dir = work_dir / "queue"
    stats_dir = work_dir / "stats"

    init_trigger_system(work_dir, workflows_dir)
    init_worker_system(queue_dir, stats_dir)

    workflow = {
        "nodes": [
            {"id": "n1", "typeId": "scheduled", "name": "Schedule", "data": {"interval": 60, "unit": "seconds"}},
            {"id": "n2", "typeId": "set", "name": "Set Data"},
        ],
        "connections": [{"sourceNodeId": "n1", "targetNodeId": "n2"}],
    }

    await register_workflow_triggers("sample.json", workflow)

    # Verify a timed task was created
    assert "sample.json:n1" in _timed_tasks

    # Clean up
    await unregister_workflow_triggers("sample.json")
    assert "sample.json:n1" not in _timed_tasks


@pytest.mark.asyncio
async def test_register_workflow_triggers_no_triggers(tmp_path):
    from src.triggers import _timed_tasks, register_workflow_triggers

    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    queue_dir = work_dir / "queue"
    stats_dir = work_dir / "stats"

    init_trigger_system(work_dir, workflows_dir)
    init_worker_system(queue_dir, stats_dir)

    workflow = {
        "nodes": [
            {"id": "n1", "typeId": "set", "name": "Set Data"},
        ],
        "connections": [],
    }

    await register_workflow_triggers("sample.json", workflow)

    # No tasks should be created (set node has no register)
    assert "sample.json:n1" not in _timed_tasks


# ##################################################################
# test start_trigger_system and stop_trigger_system
@pytest.mark.asyncio
async def test_start_stop_trigger_system(tmp_path):
    from src.triggers import (
        _timed_tasks,
        start_trigger_system,
        stop_trigger_system,
    )

    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    queue_dir = work_dir / "queue"
    stats_dir = work_dir / "stats"

    init_trigger_system(work_dir, workflows_dir)
    init_worker_system(queue_dir, stats_dir)

    # Create a workflow file
    workflow = {
        "nodes": [{"id": "n1", "typeId": "scheduled", "name": "Schedule", "data": {}}],
        "connections": [],
    }
    workflow_file = workflows_dir / "sample.json"
    workflow_file.write_text(json.dumps(workflow))

    # Enable the workflow
    set_workflow_enabled("sample.json", True)

    # Start trigger system
    await start_trigger_system()

    # Verify trigger was registered
    assert "sample.json:n1" in _timed_tasks

    # Stop trigger system
    await stop_trigger_system()

    # Verify all tasks cleaned up
    assert len(_timed_tasks) == 0


@pytest.mark.asyncio
async def test_start_trigger_system_no_enabled(tmp_path):
    from src.triggers import _timed_tasks, start_trigger_system, stop_trigger_system

    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)
    queue_dir = work_dir / "queue"
    stats_dir = work_dir / "stats"

    init_trigger_system(work_dir, workflows_dir)
    init_worker_system(queue_dir, stats_dir)

    # Create a workflow file but don't enable it
    workflow = {
        "nodes": [{"id": "n1", "typeId": "scheduled", "name": "Schedule", "data": {}}],
        "connections": [],
    }
    workflow_file = workflows_dir / "sample.json"
    workflow_file.write_text(json.dumps(workflow))

    # Start trigger system (nothing enabled)
    await start_trigger_system()

    # No tasks should be created
    assert len(_timed_tasks) == 0

    await stop_trigger_system()


@pytest.mark.asyncio
async def test_unregister_workflow_triggers_not_registered(tmp_path):
    from src.triggers import _timed_tasks, unregister_workflow_triggers

    work_dir = tmp_path / "work"
    workflows_dir = work_dir / "workflows"
    workflows_dir.mkdir(parents=True)

    init_trigger_system(work_dir, workflows_dir)

    # Should not error even if nothing registered
    await unregister_workflow_triggers("nonexistent.json")
    assert len(_timed_tasks) == 0
