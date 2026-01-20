import asyncio
import json
import shutil
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

import setproctitle
from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from .agent_ws import handle_agent_connection
from .agents import get_registry
from .concurrency import get_registry as get_concurrency_registry
from .concurrency import get_tracker
from .config import get_config
from .credentials import (
    delete_credential,
    get_credential,
    list_credentials,
    save_credential,
    test_credential_data,
    verify_credential,
)
from .executor import execute_node
from .module_loader import (
    get_credential_types_for_api,
    get_dynamic_enum_values,
    get_modules_ui_paths,
    get_node_types_for_api,
    load_all_modules,
)
from .tags import create_tag, delete_tag, list_tags
from .triggers import (
    get_enabled_workflows,
    init_trigger_system,
    register_workflow_triggers,
    set_workflow_enabled,
    start_trigger_system,
    stop_trigger_system,
    unregister_workflow_triggers,
)
from .worker import (
    get_inprogress_items,
    get_queued_items,
    init_worker_system,
    queue_workflow,
    start_workers,
    stop_workers,
    wake_workers,
)

# Add agent directory to path for importing DazflowAgent
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

SERVER_START_TIME = time.time()
STATIC_DIR = Path(__file__).parent / "static"

# Executions cache (refreshed periodically by background task)
_executions_cache: dict = {"items": [], "has_more": False, "last_updated": 0}
_executions_cache_task: asyncio.Task | None = None
EXECUTIONS_CACHE_INTERVAL = 10  # seconds
PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_WORKFLOW = PROJECT_ROOT / "sample.json"

# Built-in agent state
_builtin_agent = None
_builtin_agent_task: asyncio.Task | None = None


# ##################################################################
# get work directory paths based on config
# returns paths relative to the configured data directory
def _get_work_dir() -> Path:
    return Path(get_config().data_dir) / "local" / "work"


def _get_workflows_dir() -> Path:
    return _get_work_dir() / "workflows"


def _get_stats_dir() -> Path:
    return _get_work_dir() / "stats"


def _get_output_dir() -> Path:
    return _get_work_dir() / "output"


def _get_queue_dir() -> Path:
    return _get_work_dir() / "queue"


def _get_executions_dir() -> Path:
    return _get_work_dir() / "executions"


def _get_indexes_dir() -> Path:
    return _get_work_dir() / "indexes"


# ##################################################################
# store built-in agent secret to file
# persists secret for built-in agent so it survives restarts
def _store_builtin_secret(secret: str) -> None:
    config = get_config()
    secret_file = Path(config.data_dir) / "builtin_agent_secret"
    secret_file.write_text(secret)


# ##################################################################
# get built-in agent secret from file
# returns secret if file exists, otherwise None
def _get_builtin_secret() -> str | None:
    config = get_config()
    secret_file = Path(config.data_dir) / "builtin_agent_secret"
    if secret_file.exists():
        return secret_file.read_text().strip()
    return None


# ##################################################################
# initialize work directories on startup
# creates workflows, stats, output, and queue directories
# copies sample.json if workflows dir is empty
def init_work_directories():
    workflows_dir = _get_workflows_dir()
    stats_dir = _get_stats_dir()
    output_dir = _get_output_dir()
    queue_dir = _get_queue_dir()
    work_dir = _get_work_dir()

    workflows_dir.mkdir(parents=True, exist_ok=True)
    stats_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_dir.mkdir(parents=True, exist_ok=True)

    # Copy sample.json if workflows dir is empty
    if SAMPLE_WORKFLOW.exists() and not any(workflows_dir.iterdir()):
        shutil.copy(SAMPLE_WORKFLOW, workflows_dir / "sample.json")

    # Initialize worker system
    init_worker_system(queue_dir, stats_dir)

    # Initialize trigger system
    init_trigger_system(work_dir, workflows_dir)

    # Load all modules
    load_all_modules()


def _load_executions_from_disk(limit: int = 100) -> dict:
    """Load executions from disk. Used by cache refresh."""
    executions = []
    indexes_dir = _get_indexes_dir()

    if indexes_dir.exists():
        for index_file in indexes_dir.glob("*.jsonl"):
            try:
                for line in index_file.read_text().strip().split("\n"):
                    if line:
                        entry = json.loads(line)
                        executions.append(entry)
            except (json.JSONDecodeError, OSError):
                pass

    # Sort by completed_at descending (newest first)
    executions.sort(key=lambda x: x.get("completed_at", 0), reverse=True)

    # Apply limit
    has_more = len(executions) > limit
    executions = executions[:limit]

    return {"items": executions, "has_more": has_more, "last_updated": time.time()}


async def _executions_cache_refresh_loop():
    """Background task that refreshes the executions cache periodically."""
    global _executions_cache
    never_set = asyncio.Event()

    while True:
        try:
            _executions_cache = _load_executions_from_disk()
        except Exception:
            pass  # Keep old cache on error

        try:
            await asyncio.wait_for(never_set.wait(), timeout=EXECUTIONS_CACHE_INTERVAL)
        except asyncio.TimeoutError:
            pass


async def start_executions_cache():
    """Start the executions cache refresh background task."""
    global _executions_cache_task, _executions_cache
    # Load initial cache synchronously
    _executions_cache = _load_executions_from_disk()
    # Start background refresh task
    _executions_cache_task = asyncio.create_task(_executions_cache_refresh_loop())


async def stop_executions_cache():
    """Stop the executions cache refresh background task."""
    global _executions_cache_task
    if _executions_cache_task:
        _executions_cache_task.cancel()
        try:
            await _executions_cache_task
        except asyncio.CancelledError:
            pass
        _executions_cache_task = None


async def start_builtin_agent():
    """Start the built-in agent."""
    global _builtin_agent, _builtin_agent_task

    # Lazy import to avoid circular dependencies
    from agent import DazflowAgent

    # Create built-in agent if it doesn't exist
    registry = get_registry()
    builtin = registry.get_agent("built-in")
    if not builtin:
        builtin, secret = registry.create_agent("built-in")
        _store_builtin_secret(secret)

    # Get the secret
    secret = _get_builtin_secret()
    if not secret:
        print("[WARNING] Built-in agent secret not found, skipping agent start")
        return

    # Start built-in agent
    config = get_config()
    server_url = f"ws://127.0.0.1:{config.port}"

    _builtin_agent = DazflowAgent(server_url, "built-in", secret)

    # Give the server a moment to finish starting up before agent connects
    async def start_agent_delayed():
        await asyncio.sleep(1)
        await _builtin_agent.run()

    _builtin_agent_task = asyncio.create_task(start_agent_delayed())


async def stop_builtin_agent():
    """Stop the built-in agent."""
    global _builtin_agent, _builtin_agent_task

    if _builtin_agent:
        _builtin_agent.stop()

    if _builtin_agent_task:
        _builtin_agent_task.cancel()
        try:
            await _builtin_agent_task
        except asyncio.CancelledError:
            pass
        _builtin_agent_task = None

    _builtin_agent = None


# ##################################################################
# lifespan context manager
# handles startup and shutdown events
@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_work_directories()
    await start_workers()
    await start_trigger_system()
    await start_executions_cache()
    await start_builtin_agent()
    yield
    await stop_builtin_agent()
    await stop_executions_cache()
    await stop_trigger_system()
    await stop_workers()


app = FastAPI(title="dazflow2", lifespan=lifespan)

# Create API router with /api prefix
api_router = APIRouter(prefix="/api")

# Mount static files for nodes directory (must be before routes)
app.mount("/nodes", StaticFiles(directory=STATIC_DIR / "nodes"), name="nodes")

# Mount modules directory for JS files
MODULES_DIR = PROJECT_ROOT / "modules"
if MODULES_DIR.exists():
    app.mount("/modules", StaticFiles(directory=MODULES_DIR), name="modules")


# ##################################################################
# get modules endpoint
# returns all node types and credential types from loaded modules
@api_router.get("/modules")
async def get_modules():
    """Get all node types and credential types from loaded modules."""
    return {
        "nodeTypes": get_node_types_for_api(),
        "credentialTypes": get_credential_types_for_api(),
        "moduleUIPaths": [f"/modules/{p.parent.name}/{p.name}" for p in get_modules_ui_paths()],
    }


# ##################################################################
# credentials endpoints
# manage secure credential storage


@api_router.get("/credentials")
async def list_credentials_endpoint():
    """List all stored credentials."""
    return {"credentials": list_credentials()}


@api_router.get("/credential/{name}")
async def get_credential_endpoint(name: str):
    """Get a credential by name (private fields masked)."""
    cred = get_credential(name)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"name": name, **cred}


class SaveCredentialRequest(BaseModel):
    type: str
    data: dict


@api_router.put("/credential/{name}")
async def save_credential_endpoint(name: str, request: SaveCredentialRequest):
    """Save or update a credential."""
    success = save_credential(name, request.type, request.data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save credential")
    return {"saved": True, "name": name}


@api_router.delete("/credential/{name}")
async def delete_credential_endpoint(name: str):
    """Delete a credential."""
    success = delete_credential(name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete credential")
    return {"deleted": True, "name": name}


@api_router.post("/credential/{name}/test")
async def test_credential_endpoint(name: str):
    """Test a credential connection."""
    result = verify_credential(name)
    return result


@api_router.post("/credential-test")
async def test_credential_data_endpoint(request: Request):
    """Test credential data without saving.

    Request body: { type: string, data: object }
    """
    body = await request.json()
    cred_type = body.get("type")
    cred_data = body.get("data", {})

    if not cred_type:
        return {"status": False, "message": "Missing credential type"}

    result = test_credential_data(cred_type, cred_data)
    return result


# ##################################################################
# agent endpoints
# manage distributed agents


@api_router.get("/agents")
def list_agents():
    """List all agents."""
    registry = get_registry()
    agents = registry.list_agents()
    return [asdict(a) for a in agents]


@api_router.post("/agents")
def create_agent(request: dict):
    """Create a new agent."""
    name = request.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Agent name is required")

    registry = get_registry()
    if registry.get_agent(name):
        raise HTTPException(status_code=400, detail=f"Agent '{name}' already exists")

    agent, secret = registry.create_agent(name)

    # Return agent data plus the secret (only available at creation time)
    result = asdict(agent)
    result["secret"] = secret
    return result


@api_router.get("/agents/{name}")
def get_agent(name: str):
    """Get single agent."""
    registry = get_registry()
    agent = registry.get_agent(name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return asdict(agent)


@api_router.put("/agents/{name}")
def update_agent(name: str, request: dict):
    """Update agent."""
    registry = get_registry()
    agent = registry.get_agent(name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # Extract allowed fields from request
    updates = {}
    if "enabled" in request:
        updates["enabled"] = bool(request["enabled"])
    if "priority" in request:
        updates["priority"] = int(request["priority"])
    if "tags" in request:
        updates["tags"] = list(request["tags"])

    updated = registry.update_agent(name, **updates)
    return asdict(updated)


@api_router.delete("/agents/{name}")
def delete_agent(name: str):
    """Delete agent."""
    registry = get_registry()
    agent = registry.get_agent(name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    registry.delete_agent(name)
    return {"status": "deleted"}


@api_router.get("/agents/{name}/install-script")
def get_agent_install_script(name: str, secret: str):
    """Generate install script for an agent."""
    registry = get_registry()

    # Verify agent exists and secret is valid
    if not registry.verify_secret(name, secret):
        raise HTTPException(status_code=401, detail="Invalid agent name or secret")

    # Get server URL from config
    config = get_config()
    server_url = f"http://localhost:{config.port}"

    # Generate install script
    script = f'''#!/bin/bash
# Dazflow2 Agent Installer for {name}

AGENT_DIR="$HOME/.dazflow-agent"
SERVER_URL="{server_url}"
AGENT_NAME="{name}"
AGENT_SECRET="{secret}"

echo "Installing Dazflow2 agent '{name}'..."

# Create directory
mkdir -p "$AGENT_DIR"
cd "$AGENT_DIR"

# Download agent files
echo "Downloading agent files..."
curl -f -o agent.py "$SERVER_URL/api/agent-files/agent.py" || {{ echo "Failed to download agent.py"; exit 1; }}
curl -f -o agent_updater.py "$SERVER_URL/api/agent-files/agent_updater.py" || {{ echo "Failed to download agent_updater.py"; exit 1; }}

# Create config
cat > config.json << 'EOF'
{{"server": "{server_url}", "name": "{name}", "secret": "{secret}"}}
EOF

# Make executable
chmod +x agent.py agent_updater.py

echo ""
echo "Agent installed successfully!"
echo "Directory: $AGENT_DIR"
echo ""
echo "To start the agent, run:"
echo "  cd $AGENT_DIR"
echo "  python3 agent_updater.py"
echo ""
echo "Or use the config file:"
echo "  python3 agent_updater.py --config $AGENT_DIR/config.json"
'''

    return {"script": script}


@api_router.get("/agent-files/agent.py")
def get_agent_file():
    """Serve agent.py file."""
    agent_file = PROJECT_ROOT / "agent" / "agent.py"
    if not agent_file.exists():
        raise HTTPException(status_code=404, detail="Agent file not found")
    return FileResponse(agent_file, media_type="text/x-python", filename="agent.py")


@api_router.get("/agent-files/agent_updater.py")
def get_agent_updater_file():
    """Serve agent_updater.py file."""
    updater_file = PROJECT_ROOT / "agent" / "agent_updater.py"
    if not updater_file.exists():
        raise HTTPException(status_code=404, detail="Agent updater file not found")
    return FileResponse(updater_file, media_type="text/x-python", filename="agent_updater.py")


@api_router.get("/agent-files/version")
def get_agent_version():
    """Get current agent version."""
    config = get_config()
    return {"version": config.agent_version}


# ##################################################################
# tags endpoints
# manage capability tags for agents


@api_router.get("/tags")
def list_tags_endpoint():
    """List all tags."""
    return {"tags": list_tags()}


@api_router.post("/tags")
def create_tag_endpoint(request: dict):
    """Create a new tag."""
    name = request.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name is required")

    success = create_tag(name)
    if not success:
        raise HTTPException(status_code=400, detail=f"Tag '{name}' already exists")

    return {"name": name, "created": True}


@api_router.delete("/tags/{name}")
def delete_tag_endpoint(name: str):
    """Delete a tag."""
    success = delete_tag(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Tag '{name}' not found")

    return {"name": name, "deleted": True}


# ##################################################################
# agent websocket endpoint
# websocket connection for agents to connect to server
@app.websocket("/ws/agent/{name}/{secret}")
async def agent_websocket(websocket: WebSocket, name: str, secret: str):
    """WebSocket endpoint for agent connections."""
    await handle_agent_connection(websocket, name, secret)


# ##################################################################
# dynamic enum endpoint
# gets dynamic enum values for a node property
@api_router.post("/dynamic-enum")
async def get_dynamic_enum_endpoint(request: Request):
    """Get dynamic enum values for a node property.

    Request body: {
        nodeTypeId: string,
        enumKey: string,
        nodeData: object,
        credentialName: string (optional)
    }
    """
    body = await request.json()
    node_type_id = body.get("nodeTypeId", "")
    enum_key = body.get("enumKey", "")
    node_data = body.get("nodeData", {})
    credential_name = body.get("credentialName", "")

    if not node_type_id or not enum_key:
        return {"options": []}

    # Get credential data if credential name is provided
    credential_data = None
    if credential_name:
        cred = get_credential(credential_name, mask_private=False)
        if cred:
            credential_data = cred.get("data", {})

    options = get_dynamic_enum_values(node_type_id, enum_key, node_data, credential_data)
    return {"options": options}


# ##################################################################
# get stats for a workflow
# returns stats dict or creates default stats
def get_workflow_stats(workflow_path: str) -> dict:
    stats_dir = _get_stats_dir()
    stats_path = stats_dir / (workflow_path + ".stats.json")
    if stats_path.exists():
        return json.loads(stats_path.read_text())
    return {"execution_count": 0, "total_execution_time_ms": 0, "last_execution": None}


# ##################################################################
# save stats for a workflow
# persists stats to the stats directory
def save_workflow_stats(workflow_path: str, stats: dict):
    stats_dir = _get_stats_dir()
    stats_path = stats_dir / (workflow_path + ".stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats))


# ##################################################################
# list workflows endpoint
# returns list of workflows and folders with stats
@api_router.get("/workflows")
async def list_workflows(path: str = ""):
    workflows_dir = _get_workflows_dir()
    base_path = workflows_dir / path if path else workflows_dir
    if not base_path.exists() or not base_path.is_dir():
        raise HTTPException(status_code=404, detail="Path not found")

    enabled_state = get_enabled_workflows()
    items = []
    for item in sorted(base_path.iterdir()):
        rel_path = str(item.relative_to(workflows_dir))
        if item.is_dir():
            items.append({"name": item.name, "path": rel_path, "type": "folder"})
        elif item.suffix == ".json":
            stats = get_workflow_stats(rel_path.replace(".json", ""))
            items.append(
                {
                    "name": item.name,
                    "path": rel_path,
                    "type": "workflow",
                    "stats": stats,
                    "enabled": enabled_state.get(rel_path, False),
                }
            )
    return {"items": items, "path": path}


# ##################################################################
# get enabled workflows endpoint
# returns enabled state for all workflows
@api_router.get("/workflows/enabled")
async def get_workflows_enabled():
    return {"enabled": get_enabled_workflows()}


# ##################################################################
# set workflow enabled endpoint
# enables or disables workflow triggers
class SetEnabledRequest(BaseModel):
    enabled: bool


@api_router.put("/workflow/{path:path}/enabled")
async def set_workflow_enabled_endpoint(path: str, request: SetEnabledRequest):
    workflows_dir = _get_workflows_dir()
    workflow_path = workflows_dir / path
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    set_workflow_enabled(path, request.enabled)

    if request.enabled:
        workflow = json.loads(workflow_path.read_text())
        await register_workflow_triggers(path, workflow)
    else:
        await unregister_workflow_triggers(path)

    return {"path": path, "enabled": request.enabled}


# ##################################################################
# get workflow endpoint
# returns workflow json
@api_router.get("/workflow/{path:path}")
async def get_workflow(path: str):
    workflows_dir = _get_workflows_dir()
    workflow_path = workflows_dir / path
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")
    return json.loads(workflow_path.read_text())


# ##################################################################
# save workflow endpoint
# saves workflow json
class SaveWorkflowRequest(BaseModel):
    workflow: dict


@api_router.put("/workflow/{path:path}")
async def save_workflow(path: str, request: SaveWorkflowRequest):
    workflows_dir = _get_workflows_dir()
    workflow_path = workflows_dir / path
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(json.dumps(request.workflow, indent=2))
    return {"saved": True, "path": path}


# ##################################################################
# create new workflow endpoint
# creates a new empty workflow with given name
class CreateWorkflowRequest(BaseModel):
    name: str
    folder: str = ""


@api_router.post("/workflows/new")
async def create_workflow(request: CreateWorkflowRequest):
    workflows_dir = _get_workflows_dir()
    # Ensure name ends with .json
    name = request.name if request.name.endswith(".json") else f"{request.name}.json"
    folder_path = workflows_dir / request.folder if request.folder else workflows_dir

    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Folder not found")

    workflow_path = folder_path / name
    if workflow_path.exists():
        raise HTTPException(status_code=409, detail="Workflow already exists")

    # Create empty workflow
    empty_workflow = {"nodes": [], "connections": []}
    workflow_path.write_text(json.dumps(empty_workflow, indent=2))

    rel_path = str(workflow_path.relative_to(workflows_dir))
    return {"created": True, "path": rel_path}


# ##################################################################
# create new folder endpoint
class CreateFolderRequest(BaseModel):
    name: str
    parent: str = ""


@api_router.post("/folders/new")
async def create_folder(request: CreateFolderRequest):
    workflows_dir = _get_workflows_dir()
    parent_path = workflows_dir / request.parent if request.parent else workflows_dir

    if not parent_path.exists():
        raise HTTPException(status_code=404, detail="Parent folder not found")

    folder_path = parent_path / request.name
    if folder_path.exists():
        raise HTTPException(status_code=409, detail="Folder already exists")

    folder_path.mkdir(parents=True)
    rel_path = str(folder_path.relative_to(workflows_dir))
    return {"created": True, "path": rel_path}


# ##################################################################
# move workflow endpoint
class MoveWorkflowRequest(BaseModel):
    destination: str


@api_router.post("/workflow/{path:path}/move")
async def move_workflow(path: str, request: MoveWorkflowRequest):
    workflows_dir = _get_workflows_dir()
    source_path = workflows_dir / path
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Destination can be a folder or a full path
    dest = request.destination
    if not dest.endswith(".json"):
        # Moving to a folder - keep the original filename
        dest = f"{dest}/{source_path.name}" if dest else source_path.name

    dest_path = workflows_dir / dest

    if dest_path.exists():
        raise HTTPException(status_code=409, detail="Destination already exists")

    # Ensure destination directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Move the file
    source_path.rename(dest_path)

    # Update enabled state if workflow was enabled
    enabled = get_enabled_workflows()
    if path in enabled:
        set_workflow_enabled(path, False)
        set_workflow_enabled(dest, True)

    return {"moved": True, "from": path, "to": dest}


# ##################################################################
# execute workflow endpoint
# executes all nodes in a workflow and updates stats
class ExecuteWorkflowRequest(BaseModel):
    workflow: dict


class ExecuteWorkflowResponse(BaseModel):
    execution: dict
    stats: dict


@api_router.post("/workflow/{path:path}/execute")
async def execute_workflow(path: str, request: ExecuteWorkflowRequest):
    start_time = time.time()
    workflow = request.workflow
    execution: dict[str, Any] = {}

    # Execute all nodes in topological order (simple: just execute each)
    for node in workflow.get("nodes", []):
        node_id = node.get("id")
        if node_id and node_id not in execution:
            execution = execute_node(node_id, workflow, execution)

    end_time = time.time()
    duration_ms = int((end_time - start_time) * 1000)

    # Update stats
    stats_key = path.replace(".json", "")
    stats = get_workflow_stats(stats_key)
    stats["execution_count"] += 1
    stats["total_execution_time_ms"] += duration_ms
    stats["last_execution"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_workflow_stats(stats_key, stats)

    return ExecuteWorkflowResponse(execution=execution, stats=stats)


# ##################################################################
# queue workflow endpoint
# adds workflow to background execution queue
class QueueWorkflowResponse(BaseModel):
    queue_id: str
    status: str


@api_router.post("/workflow/{path:path}/queue")
async def queue_workflow_endpoint(path: str):
    workflows_dir = _get_workflows_dir()
    workflow_path = workflows_dir / path
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = json.loads(workflow_path.read_text())
    queue_id = queue_workflow(path, workflow)
    wake_workers()

    return QueueWorkflowResponse(queue_id=queue_id, status="queued")


# ##################################################################
# get queue status endpoint
# returns list of queued and running workflows
@api_router.get("/queue")
async def get_queue():
    queued = get_queued_items()
    inprogress = get_inprogress_items()
    all_items = queued + inprogress

    # Sort by queued_at
    all_items.sort(key=lambda x: x.get("queued_at", 0))

    # Remove internal fields and workflow data for response
    return {
        "items": [
            {
                "id": item["id"],
                "workflow_path": item["workflow_path"],
                "status": item["status"],
                "queued_at": item["queued_at"],
                "started_at": item["started_at"],
                "completed_at": item["completed_at"],
                "current_step": item["current_step"],
                "error": item.get("error"),
            }
            for item in all_items
        ]
    }


# ##################################################################
# list executions endpoint
# returns paginated list of completed/errored executions
@api_router.get("/executions")
async def list_executions(limit: int = 100, before: float | None = None):
    """List executions, newest first, with pagination.

    Returns cached data that refreshes every 10 seconds server-side.
    Multiple clients hitting this endpoint share the same cached result.
    """
    # Use cached data
    executions = list(_executions_cache.get("items", []))

    # Filter by before cursor if provided (for pagination)
    if before is not None:
        executions = [e for e in executions if e.get("completed_at", 0) < before]

    # Apply limit
    has_more = len(executions) > limit
    executions = executions[:limit]

    return {
        "items": executions,
        "has_more": has_more,
        "last_updated": _executions_cache.get("last_updated", 0),
    }


# ##################################################################
# get single execution endpoint
# returns full execution instance by ID
@api_router.get("/execution/{execution_id}")
async def get_execution(execution_id: str):
    """Get full execution instance by ID."""
    indexes_dir = _get_indexes_dir()
    work_dir = _get_work_dir()
    # Search for the execution in index files
    if not indexes_dir.exists():
        raise HTTPException(status_code=404, detail="Execution not found")

    for index_file in indexes_dir.glob("*.jsonl"):
        try:
            for line in index_file.read_text().strip().split("\n"):
                if line:
                    entry = json.loads(line)
                    if entry.get("id") == execution_id:
                        # Found the entry - load the full file
                        file_path = work_dir / entry["file"]
                        if file_path.exists():
                            return json.loads(file_path.read_text())
                        raise HTTPException(status_code=404, detail="Execution file not found")
        except (json.JSONDecodeError, OSError):
            pass

    raise HTTPException(status_code=404, detail="Execution not found")


# ##################################################################
# heartbeat generator
# yields server-sent events with the server start time so clients
# can detect when the server has restarted and reload the page
async def heartbeat_generator():
    never_set = asyncio.Event()
    while True:
        yield f"data: {SERVER_START_TIME}\n\n"
        try:
            await asyncio.wait_for(never_set.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass


# ##################################################################
# health check
# simple endpoint to verify the server is running
@app.get("/health")
async def health():
    return {"status": "ok", "start_time": SERVER_START_TIME}


# ##################################################################
# heartbeat stream
# server-sent events endpoint that clients use to detect server restarts
@app.get("/heartbeat")
async def heartbeat():
    return StreamingResponse(
        heartbeat_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ##################################################################
# serve index
# serves the main frontend shell html page
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path, media_type="text/html")


# ##################################################################
# execute node endpoint
# executes a node (and its upstream dependencies if needed)
class ExecuteRequest(BaseModel):
    node_id: str
    workflow: dict
    execution: dict


class ExecuteResponse(BaseModel):
    execution: dict


@api_router.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """Execute a node and return updated execution state."""
    try:
        updated_execution = execute_node(
            node_id=request.node_id,
            workflow=request.workflow,
            execution=request.execution,
        )
        return ExecuteResponse(execution=updated_execution)
    except Exception as e:
        # Return the error in execution result so frontend can display it
        import traceback

        error_msg = f"{type(e).__name__}: {e}"
        tb = traceback.format_exc()
        print(f"Execute error: {error_msg}\n{tb}")  # Log to server
        error_execution = dict(request.execution)
        error_execution[request.node_id] = {
            "input": None,
            "nodeOutput": [{"error": error_msg}],
            "output": [{"error": error_msg}],
            "executedAt": None,
        }
        return ExecuteResponse(execution=error_execution)


# ##################################################################
# concurrency groups endpoints
# manage concurrency groups for limiting concurrent task execution


@api_router.get("/concurrency-groups")
def list_concurrency_groups():
    """List all concurrency groups with active counts."""
    registry = get_concurrency_registry()
    tracker = get_tracker()

    groups = registry.list_groups()
    return [{"name": g.name, "limit": g.limit, "active": tracker.get_count(g.name)} for g in groups]


@api_router.post("/concurrency-groups")
def create_concurrency_group(request: dict):
    """Create a new concurrency group."""
    name = request.get("name", "").strip()
    limit = request.get("limit")

    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")

    if limit is None or not isinstance(limit, int) or limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be a positive integer")

    registry = get_concurrency_registry()
    try:
        group = registry.create_group(name, limit)
        tracker = get_tracker()
        return {"name": group.name, "limit": group.limit, "active": tracker.get_count(group.name)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/concurrency-groups/{name}")
def get_concurrency_group(name: str):
    """Get a concurrency group by name."""
    registry = get_concurrency_registry()
    group = registry.get_group(name)

    if not group:
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")

    tracker = get_tracker()
    return {"name": group.name, "limit": group.limit, "active": tracker.get_count(group.name)}


@api_router.put("/concurrency-groups/{name}")
def update_concurrency_group(name: str, request: dict):
    """Update a concurrency group's limit."""
    limit = request.get("limit")

    if limit is None or not isinstance(limit, int) or limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be a positive integer")

    registry = get_concurrency_registry()
    try:
        group = registry.update_group(name, limit)
        tracker = get_tracker()
        return {"name": group.name, "limit": group.limit, "active": tracker.get_count(group.name)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@api_router.delete("/concurrency-groups/{name}")
def delete_concurrency_group(name: str):
    """Delete a concurrency group."""
    registry = get_concurrency_registry()
    try:
        registry.delete_group(name)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Include the API router
app.include_router(api_router)


# ##################################################################
# SPA catch-all route
# serves index.html for any unmatched routes (for client-side routing)
@app.get("/{_path:path}", response_class=HTMLResponse)
async def spa_catch_all(_path: str):
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path, media_type="text/html")


# ##################################################################
# main entry
# starts the uvicorn server with the configured number of workers
def main():
    import uvicorn

    setproctitle.setproctitle("dazflow2-api")
    config = get_config()
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=config.port,
        workers=10,
        reload=False,
    )


# ##################################################################
# standard dispatch
if __name__ == "__main__":
    main()
