import json
import tempfile

from fastapi.testclient import TestClient

from src.api import (
    app,
    get_workflow_stats,
    init_work_directories,
    save_workflow_stats,
)
from src.config import ServerConfig, set_config


# ##################################################################
# test health endpoint
# verifies the health endpoint returns expected structure
def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "start_time" in data
    assert isinstance(data["start_time"], float)


# ##################################################################
# test index page
# verifies the root endpoint serves html
def test_index_serves_html():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "dazflow2" in response.text


# ##################################################################
# test heartbeat generator
# verifies the heartbeat generator produces correct sse format
def test_heartbeat_generator():
    import asyncio
    from src.api import heartbeat_generator, SERVER_START_TIME

    async def get_first_heartbeat():
        gen = heartbeat_generator()
        return await gen.__anext__()

    result = asyncio.run(get_first_heartbeat())
    assert result.startswith("data:")
    assert result.endswith("\n\n")
    # verify the data contains the server start time
    timestamp = float(result.replace("data:", "").strip())
    assert timestamp == SERVER_START_TIME


# ##################################################################
# test init_work_directories
# verifies directories are created
def test_init_work_directories(tmp_path, monkeypatch):
    # Set config to use temp path
    from src.config import ServerConfig, set_config

    set_config(ServerConfig(data_dir=str(tmp_path)))

    import src.api as api_module

    monkeypatch.setattr(api_module, "SAMPLE_WORKFLOW", tmp_path / "nonexistent.json")

    init_work_directories()

    workflows = tmp_path / "local" / "work" / "workflows"
    stats = tmp_path / "local" / "work" / "stats"
    output = tmp_path / "local" / "work" / "output"

    assert workflows.exists()
    assert stats.exists()
    assert output.exists()


# ##################################################################
# test get_workflow_stats
# verifies stats retrieval and defaults
def test_get_workflow_stats_returns_default(tmp_path):
    from src.config import ServerConfig, set_config

    stats_dir = tmp_path / "local" / "work" / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    stats = get_workflow_stats("test")
    assert stats["execution_count"] == 0
    assert stats["total_execution_time_ms"] == 0
    assert stats["last_execution"] is None


def test_get_workflow_stats_reads_existing(tmp_path):
    from src.config import ServerConfig, set_config

    stats_dir = tmp_path / "local" / "work" / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    # Create a stats file
    stats_file = stats_dir / "test.stats.json"
    stats_file.write_text(
        json.dumps({"execution_count": 5, "total_execution_time_ms": 1000, "last_execution": "2024-01-01T00:00:00Z"})
    )

    stats = get_workflow_stats("test")
    assert stats["execution_count"] == 5
    assert stats["total_execution_time_ms"] == 1000


# ##################################################################
# test save_workflow_stats
# verifies stats are persisted
def test_save_workflow_stats(tmp_path):
    from src.config import ServerConfig, set_config

    stats_dir = tmp_path / "local" / "work" / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    stats = {"execution_count": 3, "total_execution_time_ms": 500, "last_execution": "2024-01-01T12:00:00Z"}
    save_workflow_stats("myworkflow", stats)

    saved_file = stats_dir / "myworkflow.stats.json"
    assert saved_file.exists()
    assert json.loads(saved_file.read_text()) == stats


# ##################################################################
# test list_workflows endpoint
# verifies workflow listing returns correct structure
def test_list_workflows(tmp_path):
    from src.config import ServerConfig, set_config

    workflows_dir = tmp_path / "local" / "work" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    stats_dir = tmp_path / "local" / "work" / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    # Create test files
    (workflows_dir / "test.json").write_text("{}")
    (workflows_dir / "subfolder").mkdir()

    client = TestClient(app)
    response = client.get("/api/workflows")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 2

    # Check folder
    folder = next(i for i in data["items"] if i["type"] == "folder")
    assert folder["name"] == "subfolder"

    # Check workflow
    wf = next(i for i in data["items"] if i["type"] == "workflow")
    assert wf["name"] == "test.json"
    assert "stats" in wf


def test_list_workflows_nonexistent_path():
    client = TestClient(app)
    response = client.get("/api/workflows?path=nonexistent")
    assert response.status_code == 404


# ##################################################################
# test get_workflow endpoint
# verifies workflow retrieval
def test_get_workflow(tmp_path):
    from src.config import ServerConfig, set_config

    workflows_dir = tmp_path / "local" / "work" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    workflow = {"nodes": [{"id": "n1"}], "connections": []}
    (workflows_dir / "test.json").write_text(json.dumps(workflow))

    client = TestClient(app)
    response = client.get("/api/workflow/test.json")
    assert response.status_code == 200
    assert response.json() == workflow


def test_get_workflow_not_found(tmp_path):
    from src.config import ServerConfig, set_config

    workflows_dir = tmp_path / "local" / "work" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    client = TestClient(app)
    response = client.get("/api/workflow/nonexistent.json")
    assert response.status_code == 404


# ##################################################################
# test save_workflow endpoint
# verifies workflow saving
def test_save_workflow(tmp_path):
    from src.config import ServerConfig, set_config

    workflows_dir = tmp_path / "local" / "work" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    workflow = {"nodes": [{"id": "n1", "typeId": "start"}], "connections": []}

    client = TestClient(app)
    response = client.put("/api/workflow/new.json", json={"workflow": workflow})
    assert response.status_code == 200
    assert response.json()["saved"] is True

    # Verify file was created
    saved = json.loads((workflows_dir / "new.json").read_text())
    assert saved == workflow


# ##################################################################
# test execute_workflow endpoint
# verifies workflow execution and stats update
def test_execute_workflow(tmp_path):
    from src.config import ServerConfig, set_config

    workflows_dir = tmp_path / "local" / "work" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    stats_dir = tmp_path / "local" / "work" / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)
    set_config(ServerConfig(data_dir=str(tmp_path)))

    workflow = {"nodes": [{"id": "n1", "typeId": "scheduled", "name": "sched1", "data": {}}], "connections": []}

    client = TestClient(app)
    response = client.post("/api/workflow/test.json/execute", json={"workflow": workflow})
    assert response.status_code == 200
    data = response.json()

    assert "execution" in data
    assert "n1" in data["execution"]
    assert "stats" in data
    assert data["stats"]["execution_count"] == 1


# ##################################################################
# test modules endpoint
# verifies modules endpoint returns node and credential types
def test_get_modules():
    client = TestClient(app)
    response = client.get("/api/modules")
    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "nodeTypes" in data
    assert "credentialTypes" in data
    assert "moduleUIPaths" in data

    # Check that core node types are loaded
    node_type_ids = [nt["id"] for nt in data["nodeTypes"]]
    assert "start" in node_type_ids
    assert "scheduled" in node_type_ids
    assert "set" in node_type_ids

    # Core module has no credential types
    assert isinstance(data["credentialTypes"], list)


# ##################################################################
# test credentials endpoint
# verifies credential listing
def test_list_credentials(monkeypatch):
    def stub_list_credentials():
        return [{"name": "test_cred", "type": "postgres", "data": {"host": "localhost"}}]

    import src.api as api_module

    monkeypatch.setattr(api_module, "list_credentials", stub_list_credentials)

    client = TestClient(app)
    response = client.get("/api/credentials")
    assert response.status_code == 200
    data = response.json()
    assert "credentials" in data
    assert len(data["credentials"]) == 1
    assert data["credentials"][0]["name"] == "test_cred"


def test_get_credential_not_found(monkeypatch):
    def stub_get_credential(name):
        return None

    import src.api as api_module

    monkeypatch.setattr(api_module, "get_credential", stub_get_credential)

    client = TestClient(app)
    response = client.get("/api/credential/nonexistent")
    assert response.status_code == 404


def test_get_credential_found(monkeypatch):
    def stub_get_credential(name):
        if name == "my_cred":
            return {"type": "postgres", "data": {"host": "localhost"}}
        return None

    import src.api as api_module

    monkeypatch.setattr(api_module, "get_credential", stub_get_credential)

    client = TestClient(app)
    response = client.get("/api/credential/my_cred")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "my_cred"
    assert data["type"] == "postgres"


def test_save_credential(monkeypatch):
    def stub_save_credential(name, cred_type, data):
        return True

    import src.api as api_module

    monkeypatch.setattr(api_module, "save_credential", stub_save_credential)

    client = TestClient(app)
    response = client.put(
        "/api/credential/new_cred",
        json={"type": "postgres", "data": {"host": "localhost", "user": "admin"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["saved"] is True
    assert data["name"] == "new_cred"


def test_delete_credential(monkeypatch):
    def stub_delete_credential(name):
        return True

    import src.api as api_module

    monkeypatch.setattr(api_module, "delete_credential", stub_delete_credential)

    client = TestClient(app)
    response = client.delete("/api/credential/old_cred")
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True


def test_test_credential(monkeypatch):
    def stub_verify_credential(name):
        return {"status": True, "message": "Connection successful"}

    import src.api as api_module

    monkeypatch.setattr(api_module, "verify_credential", stub_verify_credential)

    client = TestClient(app)
    response = client.post("/api/credential/my_cred/test")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] is True


# ##################################################################
# test agent endpoints
# verifies agent CRUD operations


def test_list_agents_empty(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    set_registry(AgentRegistry(str(agents_file)))

    client = TestClient(app)
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_agents_with_agents(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create some agents
    registry.create_agent("agent1")
    registry.create_agent("agent2")

    client = TestClient(app)
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    names = {agent["name"] for agent in data}
    assert names == {"agent1", "agent2"}


def test_create_agent_success(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    set_registry(AgentRegistry(str(agents_file)))

    client = TestClient(app)
    response = client.post("/api/agents", json={"name": "test-agent"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-agent"
    assert data["enabled"] is True
    assert data["priority"] == 0
    assert data["tags"] == []
    assert data["status"] == "offline"
    assert "secret" in data
    assert "secret_hash" in data
    assert len(data["secret"]) > 0


def test_create_agent_no_name(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    set_registry(AgentRegistry(str(agents_file)))

    client = TestClient(app)
    response = client.post("/api/agents", json={})
    assert response.status_code == 400
    assert "name is required" in response.json()["detail"]


def test_create_agent_empty_name(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    set_registry(AgentRegistry(str(agents_file)))

    client = TestClient(app)
    response = client.post("/api/agents", json={"name": "  "})
    assert response.status_code == 400


def test_create_agent_duplicate(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create agent first time
    registry.create_agent("duplicate-agent")

    client = TestClient(app)
    response = client.post("/api/agents", json={"name": "duplicate-agent"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_agent_success(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create agent
    agent, secret = registry.create_agent("get-test-agent")

    client = TestClient(app)
    response = client.get("/api/agents/get-test-agent")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "get-test-agent"
    assert data["enabled"] is True
    assert "secret" not in data  # Secret should not be in GET response


def test_get_agent_not_found(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    set_registry(AgentRegistry(str(agents_file)))

    client = TestClient(app)
    response = client.get("/api/agents/nonexistent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_update_agent_success(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create agent
    registry.create_agent("update-test-agent")

    client = TestClient(app)
    response = client.put("/api/agents/update-test-agent", json={"enabled": False, "priority": 5})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "update-test-agent"
    assert data["enabled"] is False
    assert data["priority"] == 5


def test_update_agent_not_found(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    set_registry(AgentRegistry(str(agents_file)))

    client = TestClient(app)
    response = client.put("/api/agents/nonexistent", json={"enabled": False})
    assert response.status_code == 404


def test_update_agent_enabled(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create agent
    registry.create_agent("enable-test-agent")

    client = TestClient(app)
    response = client.put("/api/agents/enable-test-agent", json={"enabled": False})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False

    # Verify it persisted
    agent = registry.get_agent("enable-test-agent")
    assert agent.enabled is False


def test_update_agent_priority(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create agent
    registry.create_agent("priority-test-agent")

    client = TestClient(app)
    response = client.put("/api/agents/priority-test-agent", json={"priority": 10})
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == 10


def test_update_agent_tags(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create agent
    registry.create_agent("tags-test-agent")

    client = TestClient(app)
    response = client.put("/api/agents/tags-test-agent", json={"tags": ["gpu", "cuda"]})
    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["gpu", "cuda"]


def test_delete_agent_success(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create agent
    registry.create_agent("delete-test-agent")

    client = TestClient(app)
    response = client.delete("/api/agents/delete-test-agent")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"

    # Verify it was deleted
    assert registry.get_agent("delete-test-agent") is None


def test_delete_agent_not_found(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    set_registry(AgentRegistry(str(agents_file)))

    client = TestClient(app)
    response = client.delete("/api/agents/nonexistent")
    assert response.status_code == 404


# ##################################################################
# test built-in agent functionality
# verifies built-in agent is created and can be managed


def test_builtin_agent_secret_storage(tmp_path):
    from src.config import ServerConfig, set_config
    from src.api import _store_builtin_secret, _get_builtin_secret

    # Setup isolated environment
    set_config(ServerConfig(data_dir=str(tmp_path)))

    # Store secret
    test_secret = "test-secret-123"
    _store_builtin_secret(test_secret)

    # Verify it was stored
    secret_file = tmp_path / "builtin_agent_secret"
    assert secret_file.exists()

    # Retrieve secret
    retrieved = _get_builtin_secret()
    assert retrieved == test_secret


def test_builtin_agent_secret_not_found(tmp_path):
    from src.config import ServerConfig, set_config
    from src.api import _get_builtin_secret

    # Setup isolated environment
    set_config(ServerConfig(data_dir=str(tmp_path)))

    # No secret file exists
    retrieved = _get_builtin_secret()
    assert retrieved is None


def test_builtin_agent_created_on_startup(tmp_path, monkeypatch):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry
    from src.api import start_builtin_agent, stop_builtin_agent
    import asyncio

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Mock the DazflowAgent to prevent actual connection
    class MockAgent:
        def __init__(self, server_url, name, secret):
            self.server_url = server_url
            self.name = name
            self.secret = secret
            self.running = True

        async def run(self):
            # Simulate agent running without actually connecting
            while self.running:
                await asyncio.sleep(0.1)

        def stop(self):
            self.running = False

    # Patch the import

    original_import = __import__

    def custom_import(name, *args, **kwargs):
        if name == "agent":
            # Return a module-like object with DazflowAgent
            class MockAgentModule:
                DazflowAgent = MockAgent

            return MockAgentModule()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", custom_import)

    # Start built-in agent
    async def test_startup():
        await start_builtin_agent()

        # Verify agent was created
        builtin = registry.get_agent("built-in")
        assert builtin is not None
        assert builtin.name == "built-in"
        assert builtin.enabled is True

        # Verify secret was stored
        secret_file = tmp_path / "builtin_agent_secret"
        assert secret_file.exists()

        # Cleanup
        await stop_builtin_agent()

    asyncio.run(test_startup())


def test_builtin_agent_can_be_disabled(tmp_path):
    from src.config import ServerConfig, set_config
    from src.agents import AgentRegistry, set_registry

    # Setup isolated environment
    agents_file = tmp_path / "agents.json"
    set_config(ServerConfig(data_dir=str(tmp_path)))
    registry = AgentRegistry(str(agents_file))
    set_registry(registry)

    # Create built-in agent
    registry.create_agent("built-in")

    # Disable via API
    client = TestClient(app)
    response = client.put("/api/agents/built-in", json={"enabled": False})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "built-in"
    assert data["enabled"] is False

    # Verify it persisted
    builtin = registry.get_agent("built-in")
    assert builtin.enabled is False


# ##################################################################
# test list tags empty
# returns empty list when no tags exist
def test_list_tags_empty():
    with tempfile.TemporaryDirectory() as temp_dir:
        set_config(ServerConfig(data_dir=temp_dir))

        client = TestClient(app)
        response = client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == []


# ##################################################################
# test create tag
# creates new tag via API
def test_create_tag_api():
    with tempfile.TemporaryDirectory() as temp_dir:
        set_config(ServerConfig(data_dir=temp_dir))

        client = TestClient(app)
        response = client.post("/api/tags", json={"name": "gpu"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "gpu"
        assert data["created"] is True

        # Verify it was created
        response = client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert "gpu" in data["tags"]


# ##################################################################
# test create duplicate tag
# returns error when creating duplicate tag
def test_create_duplicate_tag_api():
    with tempfile.TemporaryDirectory() as temp_dir:
        set_config(ServerConfig(data_dir=temp_dir))

        client = TestClient(app)
        client.post("/api/tags", json={"name": "gpu"})
        response = client.post("/api/tags", json={"name": "gpu"})
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


# ##################################################################
# test create tag without name
# returns error when name is missing
def test_create_tag_without_name():
    with tempfile.TemporaryDirectory() as temp_dir:
        set_config(ServerConfig(data_dir=temp_dir))

        client = TestClient(app)
        response = client.post("/api/tags", json={})
        assert response.status_code == 400
        assert "required" in response.json()["detail"]


# ##################################################################
# test delete tag
# deletes tag via API
def test_delete_tag_api():
    with tempfile.TemporaryDirectory() as temp_dir:
        set_config(ServerConfig(data_dir=temp_dir))

        client = TestClient(app)
        client.post("/api/tags", json={"name": "gpu"})

        response = client.delete("/api/tags/gpu")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "gpu"
        assert data["deleted"] is True

        # Verify it was deleted
        response = client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert "gpu" not in data["tags"]


# ##################################################################
# test delete nonexistent tag
# returns error when deleting nonexistent tag
def test_delete_nonexistent_tag_api():
    with tempfile.TemporaryDirectory() as temp_dir:
        set_config(ServerConfig(data_dir=temp_dir))

        client = TestClient(app)
        response = client.delete("/api/tags/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# ##################################################################
# test list multiple tags
# returns all created tags
def test_list_multiple_tags():
    with tempfile.TemporaryDirectory() as temp_dir:
        set_config(ServerConfig(data_dir=temp_dir))

        client = TestClient(app)
        client.post("/api/tags", json={"name": "gpu"})
        client.post("/api/tags", json={"name": "cuda"})
        client.post("/api/tags", json={"name": "docker"})

        response = client.get("/api/tags")
        assert response.status_code == 200
        data = response.json()
        assert len(data["tags"]) == 3
        assert "gpu" in data["tags"]
        assert "cuda" in data["tags"]
        assert "docker" in data["tags"]
