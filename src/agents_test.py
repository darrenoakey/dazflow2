"""Tests for agent registry."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents import Agent, AgentRegistry, get_registry, set_registry
from config import ServerConfig, set_config


# ##################################################################
# test Agent dataclass with defaults
def test_agent_dataclass_defaults():
    agent = Agent(name="test-agent")
    assert agent.name == "test-agent"
    assert agent.enabled is True
    assert agent.priority == 0
    assert agent.tags == []
    assert agent.status == "offline"
    assert agent.last_seen is None
    assert agent.ip_address is None
    assert agent.version is None
    assert agent.total_tasks == 0
    assert agent.current_task is None
    assert agent.secret_hash == ""


# ##################################################################
# test Agent dataclass with custom values
def test_agent_dataclass_custom_values():
    agent = Agent(
        name="custom-agent",
        enabled=False,
        priority=10,
        tags=["gpu", "cuda"],
        status="online",
        last_seen="2024-01-20T10:30:00Z",
        ip_address="10.0.0.50",
        version="1.0.0",
        total_tasks=47,
        current_task="exec-123",
        secret_hash="abc123def456",
    )
    assert agent.name == "custom-agent"
    assert agent.enabled is False
    assert agent.priority == 10
    assert agent.tags == ["gpu", "cuda"]
    assert agent.status == "online"
    assert agent.last_seen == "2024-01-20T10:30:00Z"
    assert agent.ip_address == "10.0.0.50"
    assert agent.version == "1.0.0"
    assert agent.total_tasks == 47
    assert agent.current_task == "exec-123"
    assert agent.secret_hash == "abc123def456"


# ##################################################################
# test AgentRegistry load from non-existent file
def test_agent_registry_load_empty():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agents = registry.list_agents()
        assert agents == []


# ##################################################################
# test AgentRegistry load from existing file
def test_agent_registry_load_existing_file():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        # Create agents.json file
        agents_file = Path(temp_dir) / "agents.json"
        data = {
            "agent-1": {
                "name": "agent-1",
                "enabled": True,
                "priority": 0,
                "tags": [],
                "status": "offline",
                "last_seen": None,
                "ip_address": None,
                "version": None,
                "total_tasks": 0,
                "current_task": None,
                "secret_hash": "hash1",
            },
            "agent-2": {
                "name": "agent-2",
                "enabled": False,
                "priority": 5,
                "tags": ["gpu"],
                "status": "online",
                "last_seen": "2024-01-20T10:00:00Z",
                "ip_address": "10.0.0.1",
                "version": "1.0.0",
                "total_tasks": 10,
                "current_task": "exec-456",
                "secret_hash": "hash2",
            },
        }
        with open(agents_file, "w") as f:
            json.dump(data, f)

        # Load registry
        registry = AgentRegistry()
        agents = registry.list_agents()
        assert len(agents) == 2

        agent1 = registry.get_agent("agent-1")
        assert agent1 is not None
        assert agent1.name == "agent-1"
        assert agent1.enabled is True
        assert agent1.priority == 0
        assert agent1.tags == []
        assert agent1.status == "offline"
        assert agent1.secret_hash == "hash1"

        agent2 = registry.get_agent("agent-2")
        assert agent2 is not None
        assert agent2.name == "agent-2"
        assert agent2.enabled is False
        assert agent2.priority == 5
        assert agent2.tags == ["gpu"]
        assert agent2.status == "online"
        assert agent2.last_seen == "2024-01-20T10:00:00Z"
        assert agent2.ip_address == "10.0.0.1"
        assert agent2.version == "1.0.0"
        assert agent2.total_tasks == 10
        assert agent2.current_task == "exec-456"
        assert agent2.secret_hash == "hash2"


# ##################################################################
# test create_agent generates unique secret
def test_create_agent_generates_unique_secret():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()

        # Create first agent
        agent1, secret1 = registry.create_agent("agent-1")
        assert agent1.name == "agent-1"
        assert agent1.enabled is True
        assert agent1.priority == 0
        assert agent1.tags == []
        assert agent1.status == "offline"
        assert secret1  # Secret should not be empty
        assert len(secret1) > 0

        # Verify secret hash is stored
        assert agent1.secret_hash
        expected_hash = hashlib.sha256(secret1.encode()).hexdigest()
        assert agent1.secret_hash == expected_hash

        # Create second agent
        agent2, secret2 = registry.create_agent("agent-2")
        assert agent2.name == "agent-2"
        assert secret2
        assert secret1 != secret2  # Secrets should be different
        assert agent1.secret_hash != agent2.secret_hash  # Hashes should be different

        # Verify agents were persisted
        agents_file = Path(temp_dir) / "agents.json"
        assert agents_file.exists()

        with open(agents_file) as f:
            data = json.load(f)
            assert "agent-1" in data
            assert "agent-2" in data
            assert data["agent-1"]["secret_hash"] == agent1.secret_hash
            assert data["agent-2"]["secret_hash"] == agent2.secret_hash


# ##################################################################
# test create_agent fails for duplicate name
def test_create_agent_duplicate_name():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent1, secret1 = registry.create_agent("agent-1")

        # Try to create agent with same name
        try:
            agent2, secret2 = registry.create_agent("agent-1")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "already exists" in str(e)


# ##################################################################
# test update_agent updates fields
def test_update_agent_updates_fields():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("test-agent")

        # Update various fields
        updated = registry.update_agent(
            "test-agent",
            enabled=False,
            priority=10,
            tags=["gpu", "cuda"],
            status="online",
            last_seen="2024-01-20T10:30:00Z",
            ip_address="10.0.0.50",
            version="1.0.0",
            total_tasks=5,
            current_task="exec-789",
        )

        assert updated.name == "test-agent"
        assert updated.enabled is False
        assert updated.priority == 10
        assert updated.tags == ["gpu", "cuda"]
        assert updated.status == "online"
        assert updated.last_seen == "2024-01-20T10:30:00Z"
        assert updated.ip_address == "10.0.0.50"
        assert updated.version == "1.0.0"
        assert updated.total_tasks == 5
        assert updated.current_task == "exec-789"

        # Verify changes were persisted
        agents_file = Path(temp_dir) / "agents.json"
        with open(agents_file) as f:
            data = json.load(f)
            assert data["test-agent"]["enabled"] is False
            assert data["test-agent"]["priority"] == 10
            assert data["test-agent"]["tags"] == ["gpu", "cuda"]


# ##################################################################
# test update_agent fails for non-existent agent
def test_update_agent_nonexistent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()

        try:
            registry.update_agent("nonexistent", enabled=False)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "not found" in str(e)


# ##################################################################
# test delete_agent removes agent
def test_delete_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent1, secret1 = registry.create_agent("agent-1")
        agent2, secret2 = registry.create_agent("agent-2")

        # Delete agent-1
        registry.delete_agent("agent-1")

        # Verify agent-1 is gone but agent-2 remains
        agents = registry.list_agents()
        assert len(agents) == 1
        assert agents[0].name == "agent-2"

        assert registry.get_agent("agent-1") is None
        assert registry.get_agent("agent-2") is not None

        # Verify deletion was persisted
        agents_file = Path(temp_dir) / "agents.json"
        with open(agents_file) as f:
            data = json.load(f)
            assert "agent-1" not in data
            assert "agent-2" in data


# ##################################################################
# test delete_agent fails for non-existent agent
def test_delete_agent_nonexistent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()

        try:
            registry.delete_agent("nonexistent")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "not found" in str(e)


# ##################################################################
# test verify_secret with correct secret
def test_verify_secret_correct():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("test-agent")

        # Verify correct secret
        assert registry.verify_secret("test-agent", secret) is True


# ##################################################################
# test verify_secret with wrong secret
def test_verify_secret_wrong():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("test-agent")

        # Verify wrong secret
        assert registry.verify_secret("test-agent", "wrong-secret") is False


# ##################################################################
# test verify_secret with non-existent agent
def test_verify_secret_nonexistent_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()

        # Verify secret for non-existent agent
        assert registry.verify_secret("nonexistent", "any-secret") is False


# ##################################################################
# test list_agents returns all agents
def test_list_agents():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()

        # Empty registry
        assert registry.list_agents() == []

        # Add agents
        agent1, _ = registry.create_agent("agent-1")
        agent2, _ = registry.create_agent("agent-2")
        agent3, _ = registry.create_agent("agent-3")

        agents = registry.list_agents()
        assert len(agents) == 3
        names = {agent.name for agent in agents}
        assert names == {"agent-1", "agent-2", "agent-3"}


# ##################################################################
# test get_agent returns correct agent
def test_get_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent1, _ = registry.create_agent("agent-1")
        agent2, _ = registry.create_agent("agent-2")

        retrieved = registry.get_agent("agent-1")
        assert retrieved is not None
        assert retrieved.name == "agent-1"
        assert retrieved.secret_hash == agent1.secret_hash


# ##################################################################
# test get_agent returns None for non-existent
def test_get_agent_nonexistent():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()

        retrieved = registry.get_agent("nonexistent")
        assert retrieved is None


# ##################################################################
# test global registry functions
def test_get_registry_creates_instance():
    # Reset global registry
    import agents as agents_module

    agents_module._registry = None

    registry1 = get_registry()
    assert registry1 is not None

    registry2 = get_registry()
    assert registry1 is registry2  # Same instance


def test_set_registry_changes_global():
    # Reset global registry
    import agents as agents_module

    agents_module._registry = None

    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        custom_registry = AgentRegistry()
        set_registry(custom_registry)

        retrieved = get_registry()
        assert retrieved is custom_registry


# ##################################################################
# test update_agent ignores disallowed fields
def test_update_agent_ignores_disallowed_fields():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        registry = AgentRegistry()
        agent, secret = registry.create_agent("test-agent")

        original_secret_hash = agent.secret_hash

        # Try to update disallowed fields
        updated = registry.update_agent("test-agent", enabled=False, secret_hash="hacked")

        # Verify disallowed field was not changed
        assert updated.secret_hash == original_secret_hash

        # Verify allowed field was changed
        assert updated.enabled is False


# ##################################################################
# test persistence after reload
def test_persistence_after_reload():
    with tempfile.TemporaryDirectory() as temp_dir:
        config = ServerConfig(data_dir=temp_dir)
        set_config(config)

        # Create registry and add agents
        registry1 = AgentRegistry()
        agent1, secret1 = registry1.create_agent("agent-1")
        registry1.update_agent("agent-1", priority=10, tags=["gpu"])

        # Create new registry instance (reload from disk)
        registry2 = AgentRegistry()

        # Verify data persisted
        agent = registry2.get_agent("agent-1")
        assert agent is not None
        assert agent.name == "agent-1"
        assert agent.priority == 10
        assert agent.tags == ["gpu"]
        assert agent.secret_hash == agent1.secret_hash

        # Verify secret still works
        assert registry2.verify_secret("agent-1", secret1) is True
