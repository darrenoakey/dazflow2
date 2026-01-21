"""Tests for tags system."""

import tempfile
from datetime import datetime, timezone

from .agents import AgentRegistry, set_registry
from .config import ServerConfig, set_config
from .task_queue import Task, TaskQueue
from .tags import create_tag, delete_tag, list_tags


# ##################################################################
# test list tags when file does not exist
# returns empty list when tags file does not exist
def test_list_tags_empty():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        tags = list_tags()
        assert tags == []


# ##################################################################
# test create tag
# adds new tag to list
def test_create_tag():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        success = create_tag("gpu")
        assert success is True

        tags = list_tags()
        assert "gpu" in tags


# ##################################################################
# test create duplicate tag
# does not add duplicate tag
def test_create_duplicate_tag():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        create_tag("gpu")
        success = create_tag("gpu")
        assert success is False

        tags = list_tags()
        assert tags.count("gpu") == 1


# ##################################################################
# test create multiple tags
# can create multiple unique tags
def test_create_multiple_tags():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        create_tag("gpu")
        create_tag("cuda")
        create_tag("docker")

        tags = list_tags()
        assert len(tags) == 3
        assert "gpu" in tags
        assert "cuda" in tags
        assert "docker" in tags


# ##################################################################
# test delete tag
# removes tag from list
def test_delete_tag():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        create_tag("gpu")
        create_tag("cuda")

        success = delete_tag("gpu")
        assert success is True

        tags = list_tags()
        assert "gpu" not in tags
        assert "cuda" in tags


# ##################################################################
# test delete nonexistent tag
# returns false when deleting nonexistent tag
def test_delete_nonexistent_tag():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        success = delete_tag("nonexistent")
        assert success is False


# ##################################################################
# test task requires tag agent has
# agent with required tag can run task
def test_task_requires_tag_agent_has():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("gpu-agent")
        registry.update_agent("gpu-agent", enabled=True, status="online", tags=["gpu"])
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={
                "workflow": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "typeId": "core/log",
                            "data": {"agentConfig": {"agents": [], "requiredTags": ["gpu"]}},
                        }
                    ]
                }
            },
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("gpu-agent")
        assert available is not None
        assert available.id == "task-1"


# ##################################################################
# test task requires tag agent missing
# agent without required tag cannot run task
def test_task_requires_tag_agent_missing():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("cpu-agent")
        registry.update_agent("cpu-agent", enabled=True, status="online", tags=["cpu"])
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={
                "workflow": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "typeId": "core/log",
                            "data": {"agentConfig": {"agents": [], "requiredTags": ["gpu"]}},
                        }
                    ]
                }
            },
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("cpu-agent")
        assert available is None


# ##################################################################
# test task requires multiple tags all present
# agent with all required tags can run task
def test_task_requires_multiple_tags_all_present():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("ml-agent")
        registry.update_agent("ml-agent", enabled=True, status="online", tags=["gpu", "cuda", "docker"])
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={
                "workflow": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "typeId": "core/log",
                            "data": {"agentConfig": {"agents": [], "requiredTags": ["gpu", "cuda"]}},
                        }
                    ]
                }
            },
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("ml-agent")
        assert available is not None
        assert available.id == "task-1"


# ##################################################################
# test task requires multiple tags one missing
# agent missing one required tag cannot run task
def test_task_requires_multiple_tags_one_missing():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("gpu-agent")
        registry.update_agent("gpu-agent", enabled=True, status="online", tags=["gpu"])
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={
                "workflow": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "typeId": "core/log",
                            "data": {"agentConfig": {"agents": [], "requiredTags": ["gpu", "cuda"]}},
                        }
                    ]
                }
            },
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("gpu-agent")
        assert available is None


# ##################################################################
# test task with no required tags
# task with empty requiredTags runs on any agent
def test_task_with_no_required_tags():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("basic-agent")
        registry.update_agent("basic-agent", enabled=True, status="online", tags=[])
        set_registry(registry)

        queue = TaskQueue()
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={
                "workflow": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "typeId": "core/log",
                            "data": {"agentConfig": {"agents": [], "requiredTags": []}},
                        }
                    ]
                }
            },
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        available = queue.get_available_task("basic-agent")
        assert available is not None


# ##################################################################
# test task with specific agent and required tags
# both agent selection and tag requirements must be met
def test_task_with_specific_agent_and_required_tags():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent1, secret1 = registry.create_agent("agent-1")
        agent2, secret2 = registry.create_agent("agent-2")
        registry.update_agent("agent-1", enabled=True, status="online", tags=["gpu"])
        registry.update_agent("agent-2", enabled=True, status="online", tags=["gpu"])
        set_registry(registry)

        queue = TaskQueue()
        # Task that requires agent-1 AND gpu tag
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={
                "workflow": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "typeId": "core/log",
                            "data": {"agentConfig": {"agents": ["agent-1"], "requiredTags": ["gpu"]}},
                        }
                    ]
                }
            },
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        # agent-1 has gpu tag and is in agents list - should work
        available1 = queue.get_available_task("agent-1")
        assert available1 is not None

        # agent-2 has gpu tag but is not in agents list - should not work
        available2 = queue.get_available_task("agent-2")
        assert available2 is None


# ##################################################################
# test agent with extra tags can run task
# agent with more tags than required can still run task
def test_agent_with_extra_tags_can_run_task():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("multi-agent")
        registry.update_agent("multi-agent", enabled=True, status="online", tags=["gpu", "cuda", "docker", "linux"])
        set_registry(registry)

        queue = TaskQueue()
        # Task only requires gpu
        task = Task(
            id="task-1",
            execution_id="exec-1",
            workflow_name="test-workflow",
            node_id="node-1",
            execution_snapshot={
                "workflow": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "typeId": "core/log",
                            "data": {"agentConfig": {"agents": [], "requiredTags": ["gpu"]}},
                        }
                    ]
                }
            },
            queued_at=datetime.now(timezone.utc).isoformat(),
        )
        queue.enqueue(task)

        # Agent with extra tags should still be able to run it
        available = queue.get_available_task("multi-agent")
        assert available is not None
