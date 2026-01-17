import json

from fastapi.testclient import TestClient

from src.api import (
    app,
    get_workflow_stats,
    init_work_directories,
    save_workflow_stats,
)


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
    # Use temp paths
    workflows = tmp_path / "workflows"
    stats = tmp_path / "stats"
    output = tmp_path / "output"

    import src.api as api_module

    monkeypatch.setattr(api_module, "WORKFLOWS_DIR", workflows)
    monkeypatch.setattr(api_module, "STATS_DIR", stats)
    monkeypatch.setattr(api_module, "OUTPUT_DIR", output)
    monkeypatch.setattr(api_module, "SAMPLE_WORKFLOW", tmp_path / "nonexistent.json")

    init_work_directories()

    assert workflows.exists()
    assert stats.exists()
    assert output.exists()


# ##################################################################
# test get_workflow_stats
# verifies stats retrieval and defaults
def test_get_workflow_stats_returns_default(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "STATS_DIR", tmp_path)

    stats = get_workflow_stats("test")
    assert stats["execution_count"] == 0
    assert stats["total_execution_time_ms"] == 0
    assert stats["last_execution"] is None


def test_get_workflow_stats_reads_existing(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "STATS_DIR", tmp_path)

    # Create a stats file
    stats_file = tmp_path / "test.stats.json"
    stats_file.write_text(
        json.dumps({"execution_count": 5, "total_execution_time_ms": 1000, "last_execution": "2024-01-01T00:00:00Z"})
    )

    stats = get_workflow_stats("test")
    assert stats["execution_count"] == 5
    assert stats["total_execution_time_ms"] == 1000


# ##################################################################
# test save_workflow_stats
# verifies stats are persisted
def test_save_workflow_stats(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "STATS_DIR", tmp_path)

    stats = {"execution_count": 3, "total_execution_time_ms": 500, "last_execution": "2024-01-01T12:00:00Z"}
    save_workflow_stats("myworkflow", stats)

    saved_file = tmp_path / "myworkflow.stats.json"
    assert saved_file.exists()
    assert json.loads(saved_file.read_text()) == stats


# ##################################################################
# test list_workflows endpoint
# verifies workflow listing returns correct structure
def test_list_workflows(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "WORKFLOWS_DIR", tmp_path)
    monkeypatch.setattr(api_module, "STATS_DIR", tmp_path / "stats")

    # Create test files
    (tmp_path / "test.json").write_text("{}")
    (tmp_path / "subfolder").mkdir()

    client = TestClient(app)
    response = client.get("/workflows")
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
    response = client.get("/workflows?path=nonexistent")
    assert response.status_code == 404


# ##################################################################
# test get_workflow endpoint
# verifies workflow retrieval
def test_get_workflow(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "WORKFLOWS_DIR", tmp_path)

    workflow = {"nodes": [{"id": "n1"}], "connections": []}
    (tmp_path / "test.json").write_text(json.dumps(workflow))

    client = TestClient(app)
    response = client.get("/workflow/test.json")
    assert response.status_code == 200
    assert response.json() == workflow


def test_get_workflow_not_found(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "WORKFLOWS_DIR", tmp_path)

    client = TestClient(app)
    response = client.get("/workflow/nonexistent.json")
    assert response.status_code == 404


# ##################################################################
# test save_workflow endpoint
# verifies workflow saving
def test_save_workflow(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "WORKFLOWS_DIR", tmp_path)

    workflow = {"nodes": [{"id": "n1", "typeId": "start"}], "connections": []}

    client = TestClient(app)
    response = client.put("/workflow/new.json", json={"workflow": workflow})
    assert response.status_code == 200
    assert response.json()["saved"] is True

    # Verify file was created
    saved = json.loads((tmp_path / "new.json").read_text())
    assert saved == workflow


# ##################################################################
# test execute_workflow endpoint
# verifies workflow execution and stats update
def test_execute_workflow(tmp_path, monkeypatch):
    import src.api as api_module

    monkeypatch.setattr(api_module, "WORKFLOWS_DIR", tmp_path)
    monkeypatch.setattr(api_module, "STATS_DIR", tmp_path / "stats")

    workflow = {"nodes": [{"id": "n1", "typeId": "scheduled", "name": "sched1", "data": {}}], "connections": []}

    client = TestClient(app)
    response = client.post("/workflow/test.json/execute", json={"workflow": workflow})
    assert response.status_code == 200
    data = response.json()

    assert "execution" in data
    assert "n1" in data["execution"]
    assert "stats" in data
    assert data["stats"]["execution_count"] == 1
