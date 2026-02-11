"""
Background workflow execution worker system.
Manages a pool of workers that process queued workflows step-by-step.
Uses atomic file operations for concurrency safety.

All node execution goes through the TaskQueue - agents (including the built-in
agent) pick up tasks they can handle and execute them.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .nodes import get_node_type
from .task_queue import Task, get_queue

# Configuration
MAX_WORKERS = 10
POLL_INTERVAL_SECONDS = 1800  # 30 minutes

# Directory paths (set by init_worker_system)
QUEUE_DIR: Path | None = None
INPROGRESS_DIR: Path | None = None
EXECUTIONS_DIR: Path | None = None
INDEXES_DIR: Path | None = None
STATS_DIR: Path | None = None
WORK_DIR: Path | None = None

# Worker state
_workers: list[asyncio.Task] = []
_wake_event: asyncio.Event | None = None
_shutdown = False


def init_worker_system(queue_dir: Path, stats_dir: Path):
    """Initialize the worker system with directory paths."""
    global QUEUE_DIR, INPROGRESS_DIR, EXECUTIONS_DIR, INDEXES_DIR, STATS_DIR, WORK_DIR

    WORK_DIR = queue_dir.parent
    QUEUE_DIR = queue_dir
    INPROGRESS_DIR = WORK_DIR / "inprogress"
    EXECUTIONS_DIR = WORK_DIR / "executions"
    INDEXES_DIR = WORK_DIR / "indexes"
    STATS_DIR = stats_dir

    # Create all directories
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    INPROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    EXECUTIONS_DIR.mkdir(parents=True, exist_ok=True)
    INDEXES_DIR.mkdir(parents=True, exist_ok=True)

    # Recover any orphaned inprogress items (from crash/restart)
    recover_inprogress_items()


def recover_inprogress_items():
    """Move all inprogress items back to queue for re-processing.

    Called on startup to recover from crashes. Any item in inprogress
    means a worker was processing it when the server died.
    """
    if not INPROGRESS_DIR or not QUEUE_DIR:
        return

    recovered = 0
    for inprogress_file in INPROGRESS_DIR.glob("*.json"):
        queue_file = QUEUE_DIR / inprogress_file.name
        try:
            # Reset item state for re-processing
            item = json.loads(inprogress_file.read_text())
            item["status"] = "queued"
            item["started_at"] = None
            item["current_step"] = 0
            item["execution"] = {}  # Reset execution to start fresh
            item["error"] = None
            item["error_node_id"] = None

            # Write to queue first, then delete from inprogress
            queue_file.write_text(json.dumps(item, indent=2))
            inprogress_file.unlink()
            recovered += 1
        except (json.JSONDecodeError, OSError) as e:
            print(f"Failed to recover {inprogress_file}: {e}")

    if recovered:
        print(f"Recovered {recovered} orphaned workflow(s) from inprogress to queue")


def get_queued_items() -> list[dict]:
    """Get all items from queue directory."""
    if not QUEUE_DIR:
        return []
    items = []
    for f in QUEUE_DIR.glob("*.json"):
        try:
            item = json.loads(f.read_text())
            item["queue_file"] = str(f)
            items.append(item)
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(items, key=lambda x: x.get("queued_at", 0))


def get_inprogress_items() -> list[dict]:
    """Get all items from inprogress directory."""
    if not INPROGRESS_DIR:
        return []
    items = []
    for f in INPROGRESS_DIR.glob("*.json"):
        try:
            item = json.loads(f.read_text())
            item["queue_file"] = str(f)
            items.append(item)
        except (json.JSONDecodeError, OSError):
            pass
    return sorted(items, key=lambda x: x.get("queued_at", 0))


def queue_workflow(
    workflow_path: str,
    workflow: dict,
    trigger_node_id: str | None = None,
    trigger_output: list | None = None,
) -> str:
    """Add a workflow to the execution queue. Returns queue item ID.

    Args:
        workflow_path: Path to workflow file
        workflow: Workflow definition
        trigger_node_id: If provided, node ID that triggered this execution
        trigger_output: If provided, pre-computed output for trigger node
    """
    if not QUEUE_DIR:
        raise RuntimeError("Worker system not initialized")

    # Generate timestamp-based ID
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    workflow_slug = workflow_path.replace("/", "-").replace(".json", "")
    queue_id = f"{timestamp}-{workflow_slug}"
    queue_file = QUEUE_DIR / f"{queue_id}.json"

    # Pre-populate execution with trigger output if provided
    initial_execution = {}
    if trigger_node_id and trigger_output:
        initial_execution[trigger_node_id] = {
            "input": [],
            "nodeOutput": trigger_output,
            "output": trigger_output,
            "executedAt": now.isoformat(),
        }

    queue_item = {
        "id": queue_id,
        "workflow_path": workflow_path,
        "workflow": workflow,  # Snapshot of workflow at queue time
        "execution": initial_execution,
        "queued_at": time.time(),
        "started_at": None,
        "completed_at": None,
        "status": "queued",  # queued, running, completed, error
        "current_step": 0,
        "error": None,
        "error_node_id": None,
        "error_details": None,
        "logs": [],  # Log entries from agent execution
    }

    queue_file.write_text(json.dumps(queue_item, indent=2))
    return queue_id


def claim_queue_item() -> dict | None:
    """Atomically claim a queue item by moving it to inprogress.

    Uses filesystem rename (atomic on POSIX) for test-and-set semantics.
    Returns the claimed item or None if no items available.
    """
    if not QUEUE_DIR or not INPROGRESS_DIR:
        return None

    for queue_file in sorted(QUEUE_DIR.glob("*.json")):
        inprogress_file = INPROGRESS_DIR / queue_file.name
        try:
            # Atomic rename - fails if destination exists or source was already moved
            queue_file.rename(inprogress_file)

            # Successfully claimed - update status
            item = json.loads(inprogress_file.read_text())
            item["queue_file"] = str(inprogress_file)
            item["status"] = "running"
            item["started_at"] = time.time()
            inprogress_file.write_text(json.dumps(item, indent=2))
            return item
        except (FileNotFoundError, FileExistsError, OSError):
            # Another worker claimed it first, or file was removed - try next
            continue

    return None


def update_inprogress_item(item: dict):
    """Update an in-progress item on disk."""
    path = Path(item["queue_file"])
    if path.exists():
        path.write_text(json.dumps(item, indent=2))


def release_to_queue(item: dict):
    """Move item back to queue (e.g., for crash recovery)."""
    if not QUEUE_DIR:
        return

    inprogress_file = Path(item["queue_file"])
    queue_file = QUEUE_DIR / inprogress_file.name

    item["status"] = "queued"
    item["started_at"] = None
    inprogress_file.write_text(json.dumps(item, indent=2))

    try:
        inprogress_file.rename(queue_file)
        item["queue_file"] = str(queue_file)
    except OSError:
        pass  # Already moved or deleted


def append_to_index(workflow_path: str, entry: dict):
    """Append an execution entry to the workflow's JSONL index."""
    if not INDEXES_DIR:
        return

    # Create index file path from workflow path
    index_name = workflow_path.replace("/", "-").replace(".json", "") + ".jsonl"
    index_file = INDEXES_DIR / index_name

    # Append entry as JSONL
    with open(index_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def complete_execution(item: dict):
    """Move completed/errored item to executions archive."""
    if not EXECUTIONS_DIR or not WORK_DIR:
        # If not configured, just remove the file
        path = Path(item["queue_file"])
        if path.exists():
            path.unlink()
        return

    inprogress_file = Path(item["queue_file"])
    if not inprogress_file.exists():
        return

    # Generate chronological archive path
    now = datetime.now()
    date_dir = EXECUTIONS_DIR / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
    date_dir.mkdir(parents=True, exist_ok=True)

    timestamp = now.strftime("%Y%m%d-%H%M%S")
    workflow_slug = item["workflow_path"].replace("/", "-").replace(".json", "")
    archive_file = date_dir / f"{timestamp}-{workflow_slug}.json"

    # Handle potential collision by adding microseconds
    if archive_file.exists():
        timestamp = now.strftime("%Y%m%d-%H%M%S-%f")
        archive_file = date_dir / f"{timestamp}-{workflow_slug}.json"

    # Update item with final file location before archiving
    item["archive_file"] = str(archive_file.relative_to(WORK_DIR))
    del item["queue_file"]  # Remove transient field

    # Write to archive location
    archive_file.write_text(json.dumps(item, indent=2))

    # Remove from inprogress
    inprogress_file.unlink()

    # Calculate duration
    duration_ms = 0
    if item.get("started_at") and item.get("completed_at"):
        duration_ms = int((item["completed_at"] - item["started_at"]) * 1000)

    # Append to workflow index
    append_to_index(
        item["workflow_path"],
        {
            "id": item["id"],
            "file": str(archive_file.relative_to(WORK_DIR)),
            "workflow_path": item["workflow_path"],
            "status": item["status"],
            "queued_at": item["queued_at"],
            "started_at": item.get("started_at"),
            "completed_at": item["completed_at"],
            "duration_ms": duration_ms,
            "error": item.get("error"),
        },
    )

    # Update workflow stats
    if STATS_DIR and item["status"] == "completed":
        stats_key = item["workflow_path"].replace(".json", "")
        stats_path = STATS_DIR / f"{stats_key}.stats.json"
        if stats_path.exists():
            stats = json.loads(stats_path.read_text())
        else:
            stats = {"execution_count": 0, "total_execution_time_ms": 0, "last_execution": None}
        stats["execution_count"] += 1
        stats["total_execution_time_ms"] += duration_ms
        stats["last_execution"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats))


def get_upstream_subgraph(workflow: dict, target_node_id: str) -> set[str]:
    """Get all node IDs that are upstream of (or equal to) the target node.

    This includes the target node itself and all its transitive dependencies.
    """
    connections = workflow.get("connections", [])

    # Build reverse dependency map: node_id -> list of upstream node_ids
    upstream_map: dict[str, list[str]] = {}
    for conn in connections:
        target_id = conn.get("targetNodeId")
        source_id = conn.get("sourceNodeId")
        if target_id and source_id:
            if target_id not in upstream_map:
                upstream_map[target_id] = []
            upstream_map[target_id].append(source_id)

    # BFS/DFS to find all upstream nodes
    result = {target_node_id}
    to_visit = [target_node_id]
    while to_visit:
        node_id = to_visit.pop()
        for upstream_id in upstream_map.get(node_id, []):
            if upstream_id not in result:
                result.add(upstream_id)
                to_visit.append(upstream_id)

    return result


def find_ready_node(workflow: dict, execution: dict, target_node_id: str | None = None) -> str | None:
    """Find a node that hasn't run and has all inputs satisfied.

    Args:
        workflow: Workflow definition
        execution: Current execution state
        target_node_id: If provided, only consider nodes in the subgraph
                       leading to this target (for single-node execution)
    """
    nodes = workflow.get("nodes", [])
    connections = workflow.get("connections", [])

    # If target specified, only consider nodes in that subgraph
    allowed_nodes = None
    if target_node_id:
        allowed_nodes = get_upstream_subgraph(workflow, target_node_id)

    # Build dependency map: node_id -> list of upstream node_ids
    dependencies: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for conn in connections:
        target_id = conn.get("targetNodeId")
        source_id = conn.get("sourceNodeId")
        if target_id and source_id and target_id in dependencies:
            dependencies[target_id].append(source_id)

    # Find node that:
    # 1. Hasn't been executed yet
    # 2. Has all upstream nodes executed (or has no upstream nodes)
    # 3. Is in allowed_nodes (if target specified)
    for node in nodes:
        node_id = node["id"]
        if node_id in execution:
            continue  # Already executed

        if allowed_nodes is not None and node_id not in allowed_nodes:
            continue  # Not in path to target

        # Check if all dependencies are satisfied
        upstream = dependencies.get(node_id, [])
        if all(dep_id in execution for dep_id in upstream):
            return node_id

    return None


def is_workflow_complete(workflow: dict, execution: dict) -> bool:
    """Check if all nodes in the workflow have been executed."""
    nodes = workflow.get("nodes", [])
    return all(n["id"] in execution for n in nodes)


def is_trigger_node(workflow: dict, node_id: str) -> bool:
    """Check if a node is a trigger node (has no upstream connections AND has a register function).

    Trigger nodes (like scheduled, webhook) have a register function that sets up
    their triggering mechanism. When found as "ready", they should be auto-completed
    with default output instead of being sent to an agent.

    Non-trigger nodes (like set, transform) that have no upstream connections should
    still be executed normally.
    """
    connections = workflow.get("connections", [])
    for conn in connections:
        if conn.get("targetNodeId") == node_id:
            return False  # Has incoming connection, not a trigger

    # Check if the node type has a register function
    node = get_node_by_id(workflow, node_id)
    if not node:
        return False

    node_type = get_node_type(node.get("typeId", ""))
    if not node_type or not node_type.get("register"):
        return False  # No register function, not a trigger node

    return True


def get_node_by_id(workflow: dict, node_id: str) -> dict | None:
    """Get a node by its ID from the workflow."""
    for node in workflow.get("nodes", []):
        if node.get("id") == node_id:
            return node
    return None


async def execute_one_step(item: dict) -> dict:
    """Execute one step of a workflow via TaskQueue. Returns updated item.

    Enqueues the next ready node to the TaskQueue and waits for an agent
    to claim and execute it.
    """
    workflow = item["workflow"]
    execution = item["execution"]

    # Find a ready node
    ready_node_id = find_ready_node(workflow, execution)

    if ready_node_id is None:
        # No node ready - either complete or blocked
        if is_workflow_complete(workflow, execution):
            item["status"] = "completed"
            item["completed_at"] = time.time()
        else:
            # Might be blocked (circular dependency or missing node)
            item["status"] = "error"
            item["error"] = "No executable nodes found - possible circular dependency"
            item["completed_at"] = time.time()
        return item

    # Check if this is a trigger node (no upstream connections)
    # Trigger nodes don't execute code - auto-complete them with default output
    if is_trigger_node(workflow, ready_node_id):
        node = get_node_by_id(workflow, ready_node_id)
        node_name = node.get("name", ready_node_id) if node else ready_node_id
        now = datetime.now(timezone.utc)

        # Generate default trigger output (similar to how trigger system does it)
        trigger_output = [{node_name: {"time": now.isoformat()}}]

        execution[ready_node_id] = {
            "input": [],
            "nodeOutput": trigger_output,
            "output": trigger_output,
            "executedAt": now.isoformat(),
        }
        item["execution"] = execution
        item["current_step"] += 1

        # Check if workflow is now complete
        if is_workflow_complete(workflow, execution):
            item["status"] = "completed"
            item["completed_at"] = time.time()

        return item

    # Create task for the node
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        execution_id=item["id"],
        workflow_name=item.get("workflow_path", "unknown"),
        node_id=ready_node_id,
        execution_snapshot={
            "workflow": workflow,
            "execution": execution,
            "node_id": ready_node_id,
        },
        queued_at=datetime.now(timezone.utc).isoformat(),
    )

    # Create an event to wait for task completion
    completion_event = asyncio.Event()
    task_result: dict = {}

    def on_complete(result: dict):
        nonlocal task_result
        task_result = result
        completion_event.set()

    # Enqueue the task
    queue = get_queue()
    queue.enqueue(task, on_complete=on_complete)

    # Use node's configured timeout if available, otherwise default to 5 minutes
    node = get_node_by_id(workflow, ready_node_id)
    node_data = node.get("data", {}) if node else {}
    try:
        worker_timeout = int(node_data.get("timeout", 300))
    except (ValueError, TypeError):
        worker_timeout = 300
    # Add a small buffer so the node's own timeout fires first with a clean error
    worker_timeout = max(worker_timeout + 30, 300)

    # Wait for task completion (with timeout)
    try:
        await asyncio.wait_for(completion_event.wait(), timeout=worker_timeout)

        # Task completed - update execution with result
        if task_result.get("success"):
            new_execution = task_result.get("execution", execution)
            item["execution"] = new_execution
            item["current_step"] += 1

            # Check if now complete
            if is_workflow_complete(workflow, new_execution):
                item["status"] = "completed"
                item["completed_at"] = time.time()
        else:
            # Task failed - include agent name if available
            error_msg = task_result.get("error", "Task execution failed")
            agent_name = task_result.get("agent")
            if agent_name:
                error_msg = f"[agent: {agent_name}] {error_msg}"
            item["status"] = "error"
            item["error"] = error_msg
            item["error_node_id"] = ready_node_id
            item["error_agent"] = agent_name
            item["error_details"] = task_result.get("error_details")
            item["completed_at"] = time.time()
            # Preserve execution state so node error info is visible
            if task_result.get("execution"):
                item["execution"] = task_result["execution"]

    except asyncio.TimeoutError:
        item["status"] = "error"
        item["error"] = f"Task timeout: node {ready_node_id} took too long"
        item["error_node_id"] = ready_node_id
        item["completed_at"] = time.time()

    return item


async def worker_loop(_worker_id: int):
    """Worker loop that processes queue items."""
    global _shutdown, _wake_event

    while not _shutdown:
        # Try to claim work from queue (atomic operation)
        work_item = claim_queue_item()

        if work_item:
            # Process the item step by step until complete or error
            while work_item["status"] == "running" and not _shutdown:
                work_item = await execute_one_step(work_item)

                if work_item["status"] == "running":
                    # Save progress after each step
                    update_inprogress_item(work_item)

                    # Small delay before next step
                    try:
                        await asyncio.wait_for(asyncio.Event().wait(), timeout=0.01)
                    except asyncio.TimeoutError:
                        pass

            # Execution finished (completed or error) - archive it
            if work_item["status"] in ("completed", "error"):
                complete_execution(work_item)
        else:
            # No work available - wait for wake event or poll interval
            if _wake_event:
                try:
                    await asyncio.wait_for(_wake_event.wait(), timeout=POLL_INTERVAL_SECONDS)
                    _wake_event.clear()
                except asyncio.TimeoutError:
                    pass
            else:
                try:
                    await asyncio.wait_for(asyncio.Event().wait(), timeout=POLL_INTERVAL_SECONDS)
                except asyncio.TimeoutError:
                    pass


async def start_workers():
    """Start the worker pool."""
    global _workers, _wake_event, _shutdown
    _shutdown = False
    _wake_event = asyncio.Event()

    for i in range(MAX_WORKERS):
        task = asyncio.create_task(worker_loop(i))
        _workers.append(task)


async def stop_workers():
    """Stop all workers."""
    global _shutdown, _workers
    _shutdown = True

    if _wake_event:
        _wake_event.set()

    for task in _workers:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    _workers = []


def wake_workers():
    """Wake up all workers to check for new work."""
    if _wake_event:
        _wake_event.set()
