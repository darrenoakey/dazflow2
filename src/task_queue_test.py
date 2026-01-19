"""Tests for task queue."""

import tempfile
from datetime import datetime, timezone

from .agents import AgentRegistry, set_registry
from .config import ServerConfig, set_config
from .task_queue import Task, TaskQueue, get_queue


# ##################################################################
# test task queue enqueue
# verifies task added to pending queue
def test_task_queue_enqueue():
    queue = TaskQueue()
    task = Task(
        id="task-1",
        execution_id="exec-1",
        workflow_name="test-workflow",
        node_id="node-1",
        execution_snapshot={"test": "data"},
        queued_at=datetime.now(timezone.utc).isoformat(),
    )

    queue.enqueue(task)
    assert queue.get_pending_count() == 1
    assert queue.get_in_progress_count() == 0


# ##################################################################
# test task queue get available task
# returns task for enabled online agent
def test_task_queue_get_available_task():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=True, status="online")
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("agent-1")
        assert available is not None
        assert available.id == "task-1"


# ##################################################################
# test task queue no available task for disabled agent
# returns none when agent is disabled
def test_task_queue_no_available_task_disabled_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=False, status="online")
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("agent-1")
        assert available is None


# ##################################################################
# test task queue no available task for offline agent
# returns none when agent is offline
def test_task_queue_no_available_task_offline_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=True, status="offline")
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("agent-1")
        assert available is None


# ##################################################################
# test task queue claim task
# moves task from pending to in progress
def test_task_queue_claim_task():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=True, status="online")
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        success = queue.claim_task("task-1", "agent-1")
        assert success is True
        assert queue.get_pending_count() == 0
        assert queue.get_in_progress_count() == 1

        # Verify agent current_task updated
        updated_agent = registry.get_agent("agent-1")
        assert updated_agent.current_task == "exec-1"


# ##################################################################
# test task queue claim nonexistent task
# returns false for task not in queue
def test_task_queue_claim_nonexistent_task():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        set_registry(registry)

        queue = TaskQueue()
        success = queue.claim_task("nonexistent", "agent-1")
        assert success is False


# ##################################################################
# test task queue complete task
# removes from in progress and calls callback
def test_task_queue_complete_task():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=True, status="online")
        set_registry(registry)

        callback_result = None

        def on_complete(result):
            nonlocal callback_result
            callback_result = result

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task, on_complete=on_complete)
        queue.claim_task("task-1", "agent-1")

        result = {"output": "success"}
        queue.complete_task("task-1", result)

        assert queue.get_in_progress_count() == 0
        assert callback_result == result

        # Verify agent current_task cleared and total_tasks incremented
        updated_agent = registry.get_agent("agent-1")
        assert updated_agent.current_task is None
        assert updated_agent.total_tasks == 1


# ##################################################################
# test task queue fail task
# removes from in progress and calls callback with error
def test_task_queue_fail_task():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=True, status="online")
        set_registry(registry)

        callback_result = None

        def on_complete(result):
            nonlocal callback_result
            callback_result = result

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task, on_complete=on_complete)
        queue.claim_task("task-1", "agent-1")

        queue.fail_task("task-1", "Something went wrong")

        assert queue.get_in_progress_count() == 0
        assert callback_result == {"error": "Something went wrong"}

        # Verify agent current_task cleared
        updated_agent = registry.get_agent("agent-1")
        assert updated_agent.current_task is None


# ##################################################################
# test task queue requeue agent tasks
# moves claimed tasks back to pending when agent disconnects
def test_task_queue_requeue_agent_tasks():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=True, status="online")
        set_registry(registry)

        queue = TaskQueue()
        task1 = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        task2 = Task(
            id="task-2",
            execution_id="exec-2",
            workflow_name="test-workflow",
            node_id="node-2",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task1)
        queue.enqueue(task2)
        queue.claim_task("task-1", "agent-1")
        queue.claim_task("task-2", "agent-1")

        assert queue.get_in_progress_count() == 2
        assert queue.get_pending_count() == 0

        queue.requeue_agent_tasks("agent-1")

        assert queue.get_in_progress_count() == 0
        assert queue.get_pending_count() == 2

        # Verify tasks are requeued with cleared claim info
        available = queue.get_available_task("agent-1")
        assert available is not None
        assert available.claimed_by is None
        assert available.claimed_at is None


# ##################################################################
# test task queue requeue only specific agent tasks
# only requeues tasks claimed by specific agent
def test_task_queue_requeue_only_specific_agent_tasks():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent1, secret1 = registry.create_agent("agent-1")
        agent2, secret2 = registry.create_agent("agent-2")
        registry.update_agent("agent-1", enabled=True, status="online")
        registry.update_agent("agent-2", enabled=True, status="online")
        set_registry(registry)

        queue = TaskQueue()
        task1 = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        task2 = Task(
            id="task-2",
            execution_id="exec-2",
            workflow_name="test-workflow",
            node_id="node-2",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task1)
        queue.enqueue(task2)
        queue.claim_task("task-1", "agent-1")
        queue.claim_task("task-2", "agent-2")

        queue.requeue_agent_tasks("agent-1")

        # agent-1's task requeued
        assert queue.get_in_progress_count() == 1
        assert queue.get_pending_count() == 1

        # agent-2's task still in progress
        in_progress = queue._in_progress
        assert "task-2" in in_progress
        assert in_progress["task-2"].claimed_by == "agent-2"


# ##################################################################
# test get global queue
# returns singleton instance
def test_get_global_queue():
    queue1 = get_queue()
    queue2 = get_queue()
    assert queue1 is queue2


# ##################################################################
# test task dataclass
# verifies task can be created and fields accessed
def test_task_dataclass():
    now = datetime.now(timezone.utc).isoformat()
    task = Task(
        id="task-1",
        execution_id="exec-1",
        workflow_name="test-workflow",
        node_id="node-1",
        execution_snapshot={"nodes": [], "connections": []},
        queued_at=now,
    )

    assert task.id == "task-1"
    assert task.execution_id == "exec-1"
    assert task.workflow_name == "test-workflow"
    assert task.node_id == "node-1"
    assert task.execution_snapshot == {"nodes": [], "connections": []}
    assert task.queued_at == now
    assert task.claimed_by is None
    assert task.claimed_at is None


# ##################################################################
# test task claim updates timestamps
# verifies claimed_at is set when task is claimed
def test_task_claim_updates_timestamps():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        registry.update_agent("agent-1", enabled=True, status="online")
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        queue.claim_task("task-1", "agent-1")

        # Get the task from in_progress
        claimed_task = queue._in_progress["task-1"]
        assert claimed_task.claimed_by == "agent-1"
        assert claimed_task.claimed_at is not None


# ##################################################################
# test enqueue with callback
# verifies callback stored and called on completion
def test_enqueue_with_callback():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("agent-1")
        set_registry(registry)

        called = False

        def callback(result):
            nonlocal called
            called = True

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={"test": "data"},
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task, on_complete=callback)
        queue.claim_task("task-1", "agent-1")
        queue.complete_task("task-1", {})

        assert called is True
