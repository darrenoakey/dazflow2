"""Tests for background workflow execution worker system."""

import json
import time

from src.worker import (
    append_to_index,
    claim_queue_item,
    complete_execution,
    execute_one_step,
    find_ready_node,
    get_inprogress_items,
    get_queued_items,
    init_worker_system,
    is_workflow_complete,
    queue_workflow,
    release_to_queue,
    update_inprogress_item,
)


# ##################################################################
# test init_worker_system
# verifies directories are created
def test_init_worker_system(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"

    init_worker_system(queue_dir, stats_dir)

    assert queue_dir.exists()
    assert (tmp_path / "inprogress").exists()
    assert (tmp_path / "executions").exists()
    assert (tmp_path / "indexes").exists()


# ##################################################################
# test queue_workflow
# verifies workflow is added to queue
def test_queue_workflow(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    workflow = {"nodes": [{"id": "n1", "typeId": "scheduled"}], "connections": []}
    queue_id = queue_workflow("test.json", workflow)

    assert queue_id is not None
    queue_files = list(queue_dir.glob("*.json"))
    assert len(queue_files) == 1

    item = json.loads(queue_files[0].read_text())
    assert item["workflow_path"] == "test.json"
    assert item["status"] == "queued"
    assert item["workflow"] == workflow
    assert item["error_node_id"] is None
    assert item["error_details"] is None


# ##################################################################
# test get_queued_items
# verifies queued items are retrieved
def test_get_queued_items(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_workflow("a.json", {"nodes": [], "connections": []})
    queue_workflow("b.json", {"nodes": [], "connections": []})

    items = get_queued_items()
    assert len(items) == 2


# ##################################################################
# test claim_queue_item
# verifies atomic claim moves item to inprogress
def test_claim_queue_item(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_workflow("test.json", {"nodes": [], "connections": []})
    assert len(get_queued_items()) == 1

    item = claim_queue_item()

    assert item is not None
    assert item["status"] == "running"
    assert item["started_at"] is not None
    assert len(get_queued_items()) == 0
    assert len(get_inprogress_items()) == 1


def test_claim_queue_item_empty_queue(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    item = claim_queue_item()
    assert item is None


# ##################################################################
# test update_inprogress_item
# verifies inprogress item is updated
def test_update_inprogress_item(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_workflow("test.json", {"nodes": [], "connections": []})
    item = claim_queue_item()

    item["current_step"] = 5
    update_inprogress_item(item)

    items = get_inprogress_items()
    assert items[0]["current_step"] == 5


# ##################################################################
# test release_to_queue
# verifies item is moved back to queue
def test_release_to_queue(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_workflow("test.json", {"nodes": [], "connections": []})
    item = claim_queue_item()
    assert len(get_queued_items()) == 0
    assert len(get_inprogress_items()) == 1

    release_to_queue(item)

    assert len(get_queued_items()) == 1
    assert len(get_inprogress_items()) == 0
    assert item["status"] == "queued"
    assert item["started_at"] is None


# ##################################################################
# test complete_execution
# verifies item is archived and indexed
def test_complete_execution(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_workflow("test.json", {"nodes": [], "connections": []})
    item = claim_queue_item()
    item["status"] = "completed"
    item["completed_at"] = time.time()
    update_inprogress_item(item)

    complete_execution(item)

    # Should be removed from inprogress
    assert len(get_inprogress_items()) == 0

    # Should be in executions directory
    executions_dir = tmp_path / "executions"
    archived_files = list(executions_dir.glob("**/*.json"))
    assert len(archived_files) == 1

    # Should have index entry
    index_file = tmp_path / "indexes" / "test.jsonl"
    assert index_file.exists()
    index_lines = index_file.read_text().strip().split("\n")
    assert len(index_lines) == 1
    entry = json.loads(index_lines[0])
    assert entry["status"] == "completed"
    assert entry["workflow_path"] == "test.json"


def test_complete_execution_with_error(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_workflow("test.json", {"nodes": [], "connections": []})
    item = claim_queue_item()
    item["status"] = "error"
    item["error"] = "Something went wrong"
    item["error_node_id"] = "n1"
    item["completed_at"] = time.time()
    update_inprogress_item(item)

    complete_execution(item)

    # Should be archived with error status
    executions_dir = tmp_path / "executions"
    archived_files = list(executions_dir.glob("**/*.json"))
    assert len(archived_files) == 1

    archived = json.loads(archived_files[0].read_text())
    assert archived["status"] == "error"
    assert archived["error"] == "Something went wrong"
    assert archived["error_node_id"] == "n1"


# ##################################################################
# test append_to_index
# verifies JSONL index is appended
def test_append_to_index(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    append_to_index("workflow.json", {"id": "1", "status": "completed"})
    append_to_index("workflow.json", {"id": "2", "status": "error"})

    index_file = tmp_path / "indexes" / "workflow.jsonl"
    lines = index_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["id"] == "1"
    assert json.loads(lines[1])["id"] == "2"


# ##################################################################
# test find_ready_node
# verifies node with satisfied inputs is found
def test_find_ready_node_no_dependencies():
    workflow = {
        "nodes": [{"id": "n1", "typeId": "scheduled"}],
        "connections": [],
    }
    execution = {}

    ready = find_ready_node(workflow, execution)
    assert ready == "n1"


def test_find_ready_node_with_dependencies():
    workflow = {
        "nodes": [
            {"id": "n1", "typeId": "scheduled"},
            {"id": "n2", "typeId": "set"},
        ],
        "connections": [
            {"sourceNodeId": "n1", "targetNodeId": "n2"},
        ],
    }
    execution = {}

    # n1 should be ready (no dependencies)
    ready = find_ready_node(workflow, execution)
    assert ready == "n1"

    # After n1 executes, n2 should be ready
    execution = {"n1": {"output": []}}
    ready = find_ready_node(workflow, execution)
    assert ready == "n2"


def test_find_ready_node_all_executed():
    workflow = {
        "nodes": [{"id": "n1", "typeId": "scheduled"}],
        "connections": [],
    }
    execution = {"n1": {"output": []}}

    ready = find_ready_node(workflow, execution)
    assert ready is None


# ##################################################################
# test is_workflow_complete
# verifies workflow completion detection
def test_is_workflow_complete_empty():
    workflow = {"nodes": [], "connections": []}
    assert is_workflow_complete(workflow, {}) is True


def test_is_workflow_complete_incomplete():
    workflow = {"nodes": [{"id": "n1"}], "connections": []}
    assert is_workflow_complete(workflow, {}) is False


def test_is_workflow_complete_done():
    workflow = {"nodes": [{"id": "n1"}, {"id": "n2"}], "connections": []}
    execution = {"n1": {}, "n2": {}}
    assert is_workflow_complete(workflow, execution) is True


# ##################################################################
# test execute_one_step
# verifies single step execution
def test_execute_one_step(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_item = {
        "workflow": {
            "nodes": [{"id": "n1", "typeId": "scheduled", "name": "sched1", "data": {}}],
            "connections": [],
        },
        "execution": {},
        "status": "running",
        "current_step": 0,
    }

    updated = execute_one_step(queue_item)

    assert "n1" in updated["execution"]
    assert updated["status"] == "completed"
    assert updated["current_step"] == 1


def test_execute_one_step_multi_node(tmp_path):
    queue_dir = tmp_path / "queue"
    stats_dir = tmp_path / "stats"
    init_worker_system(queue_dir, stats_dir)

    queue_item = {
        "workflow": {
            "nodes": [
                {"id": "n1", "typeId": "scheduled", "name": "sched1", "data": {}},
                {"id": "n2", "typeId": "set", "name": "set1", "data": {"fields": []}},
            ],
            "connections": [{"sourceNodeId": "n1", "targetNodeId": "n2"}],
        },
        "execution": {},
        "status": "running",
        "current_step": 0,
    }

    # First step
    updated = execute_one_step(queue_item)
    assert "n1" in updated["execution"]
    assert "n2" not in updated["execution"]
    assert updated["status"] == "running"

    # Second step
    updated = execute_one_step(updated)
    assert "n1" in updated["execution"]
    assert "n2" in updated["execution"]
    assert updated["status"] == "completed"
