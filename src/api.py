import asyncio
import json
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import setproctitle
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from .executor import execute_node
from .worker import (
    get_inprogress_items,
    get_queued_items,
    init_worker_system,
    queue_workflow,
    start_workers,
    stop_workers,
    wake_workers,
)

SERVER_START_TIME = time.time()
STATIC_DIR = Path(__file__).parent / "static"
PROJECT_ROOT = Path(__file__).parent.parent
WORK_DIR = PROJECT_ROOT / "local" / "work"
WORKFLOWS_DIR = WORK_DIR / "workflows"
STATS_DIR = WORK_DIR / "stats"
OUTPUT_DIR = WORK_DIR / "output"
QUEUE_DIR = WORK_DIR / "queue"
EXECUTIONS_DIR = WORK_DIR / "executions"
INDEXES_DIR = WORK_DIR / "indexes"
SAMPLE_WORKFLOW = PROJECT_ROOT / "sample.json"


# ##################################################################
# initialize work directories on startup
# creates workflows, stats, output, and queue directories
# copies sample.json if workflows dir is empty
def init_work_directories():
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)

    # Copy sample.json if workflows dir is empty
    if SAMPLE_WORKFLOW.exists() and not any(WORKFLOWS_DIR.iterdir()):
        shutil.copy(SAMPLE_WORKFLOW, WORKFLOWS_DIR / "sample.json")

    # Initialize worker system
    init_worker_system(QUEUE_DIR, STATS_DIR)


# ##################################################################
# lifespan context manager
# handles startup and shutdown events
@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_work_directories()
    await start_workers()
    yield
    await stop_workers()


app = FastAPI(title="dazflow2", lifespan=lifespan)

# Mount static files for nodes directory (must be before routes)
app.mount("/nodes", StaticFiles(directory=STATIC_DIR / "nodes"), name="nodes")


# ##################################################################
# get stats for a workflow
# returns stats dict or creates default stats
def get_workflow_stats(workflow_path: str) -> dict:
    stats_path = STATS_DIR / (workflow_path + ".stats.json")
    if stats_path.exists():
        return json.loads(stats_path.read_text())
    return {"execution_count": 0, "total_execution_time_ms": 0, "last_execution": None}


# ##################################################################
# save stats for a workflow
# persists stats to the stats directory
def save_workflow_stats(workflow_path: str, stats: dict):
    stats_path = STATS_DIR / (workflow_path + ".stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats))


# ##################################################################
# list workflows endpoint
# returns list of workflows and folders with stats
@app.get("/workflows")
async def list_workflows(path: str = ""):
    base_path = WORKFLOWS_DIR / path if path else WORKFLOWS_DIR
    if not base_path.exists() or not base_path.is_dir():
        raise HTTPException(status_code=404, detail="Path not found")

    items = []
    for item in sorted(base_path.iterdir()):
        rel_path = str(item.relative_to(WORKFLOWS_DIR))
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
                }
            )
    return {"items": items, "path": path}


# ##################################################################
# get workflow endpoint
# returns workflow json
@app.get("/workflow/{path:path}")
async def get_workflow(path: str):
    workflow_path = WORKFLOWS_DIR / path
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")
    return json.loads(workflow_path.read_text())


# ##################################################################
# save workflow endpoint
# saves workflow json
class SaveWorkflowRequest(BaseModel):
    workflow: dict


@app.put("/workflow/{path:path}")
async def save_workflow(path: str, request: SaveWorkflowRequest):
    workflow_path = WORKFLOWS_DIR / path
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(json.dumps(request.workflow, indent=2))
    return {"saved": True, "path": path}


# ##################################################################
# execute workflow endpoint
# executes all nodes in a workflow and updates stats
class ExecuteWorkflowRequest(BaseModel):
    workflow: dict


class ExecuteWorkflowResponse(BaseModel):
    execution: dict
    stats: dict


@app.post("/workflow/{path:path}/execute")
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


@app.post("/workflow/{path:path}/queue")
async def queue_workflow_endpoint(path: str):
    workflow_path = WORKFLOWS_DIR / path
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = json.loads(workflow_path.read_text())
    queue_id = queue_workflow(path, workflow)
    wake_workers()

    return QueueWorkflowResponse(queue_id=queue_id, status="queued")


# ##################################################################
# get queue status endpoint
# returns list of queued and running workflows
@app.get("/queue")
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
@app.get("/executions")
async def list_executions(limit: int = 100, before: float | None = None):
    """List executions, newest first, with pagination."""
    executions = []

    # Read all index files and collect entries
    if INDEXES_DIR.exists():
        for index_file in INDEXES_DIR.glob("*.jsonl"):
            try:
                for line in index_file.read_text().strip().split("\n"):
                    if line:
                        entry = json.loads(line)
                        executions.append(entry)
            except (json.JSONDecodeError, OSError):
                pass

    # Sort by completed_at descending (newest first)
    executions.sort(key=lambda x: x.get("completed_at", 0), reverse=True)

    # Filter by before cursor if provided
    if before is not None:
        executions = [e for e in executions if e.get("completed_at", 0) < before]

    # Apply limit
    has_more = len(executions) > limit
    executions = executions[:limit]

    return {"items": executions, "has_more": has_more}


# ##################################################################
# get single execution endpoint
# returns full execution instance by ID
@app.get("/execution/{execution_id}")
async def get_execution(execution_id: str):
    """Get full execution instance by ID."""
    # Search for the execution in index files
    if not INDEXES_DIR.exists():
        raise HTTPException(status_code=404, detail="Execution not found")

    for index_file in INDEXES_DIR.glob("*.jsonl"):
        try:
            for line in index_file.read_text().strip().split("\n"):
                if line:
                    entry = json.loads(line)
                    if entry.get("id") == execution_id:
                        # Found the entry - load the full file
                        file_path = WORK_DIR / entry["file"]
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


@app.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """Execute a node and return updated execution state."""
    updated_execution = execute_node(
        node_id=request.node_id,
        workflow=request.workflow,
        execution=request.execution,
    )
    return ExecuteResponse(execution=updated_execution)


# ##################################################################
# main entry
# starts the uvicorn server with the configured number of workers
def main():
    import uvicorn

    setproctitle.setproctitle("dazflow2-api")
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=31415,
        workers=10,
        reload=False,
    )


# ##################################################################
# standard dispatch
if __name__ == "__main__":
    main()
