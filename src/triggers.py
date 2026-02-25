"""
Trigger registration and scheduling system.
Manages automatic workflow execution via trigger nodes.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from .nodes import get_node_type
from .worker import queue_workflow, wake_workers

logger = logging.getLogger(__name__)

# Directory paths (set by init_trigger_system)
WORK_DIR: Path | None = None
WORKFLOWS_DIR: Path | None = None
ENABLED_FILE: Path | None = None
INDEXES_DIR: Path | None = None

# Trigger state
_timed_tasks: dict[str, asyncio.Task] = {}  # trigger_id -> timer task
_push_listeners: dict[str, asyncio.Task] = {}  # trigger_id -> listener task
_shutdown = False


def init_trigger_system(work_dir: Path, workflows_dir: Path):
    """Initialize the trigger system with directory paths."""
    global WORK_DIR, WORKFLOWS_DIR, ENABLED_FILE, INDEXES_DIR
    WORK_DIR = work_dir
    WORKFLOWS_DIR = workflows_dir
    ENABLED_FILE = work_dir / "enabled.json"
    INDEXES_DIR = work_dir / "indexes"


def get_last_execution_time(workflow_path: str) -> float | None:
    """Get the timestamp of the last completed execution for a workflow.

    Returns None if no executions exist.
    """
    if not INDEXES_DIR:
        return None

    # Index file path from workflow path
    index_name = workflow_path.replace("/", "-").replace(".json", "") + ".jsonl"
    index_file = INDEXES_DIR / index_name

    if not index_file.exists():
        return None

    # Read last line efficiently
    try:
        content = index_file.read_text().strip()
        if not content:
            return None

        # Get the last line
        last_line = content.split("\n")[-1]
        if not last_line:
            return None

        entry = json.loads(last_line)
        return entry.get("completed_at")
    except (json.JSONDecodeError, OSError):
        return None


def get_enabled_workflows() -> dict[str, bool]:
    """Load enabled state for all workflows."""
    if not ENABLED_FILE or not ENABLED_FILE.exists():
        return {}
    try:
        return json.loads(ENABLED_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def set_workflow_enabled(workflow_path: str, enabled: bool) -> None:
    """Update enabled state for a workflow."""
    if not ENABLED_FILE:
        return
    current = get_enabled_workflows()
    if enabled:
        current[workflow_path] = True
    elif workflow_path in current:
        del current[workflow_path]
    ENABLED_FILE.write_text(json.dumps(current, indent=2))


def find_trigger_nodes(workflow: dict) -> list[dict]:
    """Find all nodes with no incoming connections (trigger nodes)."""
    nodes = workflow.get("nodes", [])
    connections = workflow.get("connections", [])

    # Build set of nodes that have incoming connections
    has_inputs = {c.get("targetNodeId") for c in connections}

    # Return nodes with no inputs that have a register function
    trigger_nodes = []
    for node in nodes:
        if node["id"] not in has_inputs:
            node_type = get_node_type(node.get("typeId"))
            if node_type and node_type.get("register"):
                trigger_nodes.append(node)

    return trigger_nodes


def _make_trigger_callback(
    workflow_path: str,
    node_id: str,
    node_name: str,
) -> Callable[[dict], None]:
    """Create a callback that queues workflow execution when trigger fires."""

    def callback(output_data: dict) -> None:
        if not WORKFLOWS_DIR:
            return

        # Load current workflow
        workflow_file = WORKFLOWS_DIR / workflow_path
        if not workflow_file.exists():
            return

        workflow = json.loads(workflow_file.read_text())

        # Format output like execute_node does - namespaced by node name
        trigger_output = [{node_name: output_data}]

        # Queue with pre-populated trigger output
        queue_workflow(
            workflow_path,
            workflow,
            trigger_node_id=node_id,
            trigger_output=trigger_output,
        )
        wake_workers()

    return callback


async def _schedule_timed_trigger(
    trigger_id: str,
    trigger_at: float,
    interval_seconds: float,
    node_data: dict,
    register_fn: Callable,
    callback: Callable,
) -> None:
    """Schedule a timed trigger with automatic re-registration."""
    global _shutdown

    async def timer_task():
        nonlocal trigger_at
        while not _shutdown:
            now = time.time()
            delay = max(0, trigger_at - now)

            try:
                # Wait until trigger time using Event pattern
                if delay > 0:
                    try:
                        await asyncio.wait_for(asyncio.Event().wait(), timeout=delay)
                    except asyncio.TimeoutError:
                        pass  # Expected - timeout is the normal path

                if _shutdown:
                    break

                # Fire trigger with current time
                fire_time = time.time()
                output = {"time": datetime.now().isoformat()}
                callback(output)

                # Re-register to get next trigger time, passing the fire time
                # as the last execution time so it calculates the next interval correctly
                result = register_fn(node_data, callback, fire_time)
                if result.get("type") == "timed":
                    trigger_at = result.get("trigger_at", time.time() + interval_seconds)
                else:
                    break  # Registration changed type, stop timed loop

            except asyncio.CancelledError:
                break
            except Exception:
                # On error, wait interval and retry
                try:
                    await asyncio.wait_for(asyncio.Event().wait(), timeout=interval_seconds)
                except asyncio.TimeoutError:
                    pass
                trigger_at = time.time()

    task = asyncio.create_task(timer_task())
    _timed_tasks[trigger_id] = task


async def _start_push_listener(
    trigger_id: str,
    listener_fn: Callable,
    node_data: dict,
    callback: Callable,
) -> None:
    """Start a push listener with automatic restart on crash."""
    global _shutdown

    async def listener_wrapper():
        restart_count = 0
        max_restarts = 10
        backoff = 1

        logger.info("Push listener starting: %s", trigger_id)
        while not _shutdown and restart_count < max_restarts:
            try:
                # Call the listener function (blocks until callback called or error)
                await listener_fn(node_data, callback)
                # If it returns normally, we're done
                logger.info("Push listener exited normally: %s", trigger_id)
                break
            except asyncio.CancelledError:
                logger.info("Push listener cancelled: %s", trigger_id)
                break
            except Exception as e:
                restart_count += 1
                logger.warning(
                    "Push listener error (%s, attempt %d/%d): %s", trigger_id, restart_count, max_restarts, e
                )
                # Exponential backoff using Event pattern
                try:
                    await asyncio.wait_for(asyncio.Event().wait(), timeout=min(backoff, 60))
                except asyncio.TimeoutError:
                    pass
                backoff *= 2

        if restart_count >= max_restarts:
            logger.error("Push listener gave up after %d restarts: %s", max_restarts, trigger_id)

    task = asyncio.create_task(listener_wrapper())
    _push_listeners[trigger_id] = task


async def register_workflow_triggers(workflow_path: str, workflow: dict) -> None:
    """Register all triggers for a workflow."""
    trigger_nodes = find_trigger_nodes(workflow)

    # Get the last execution time for this workflow
    last_execution_time = get_last_execution_time(workflow_path)

    for node in trigger_nodes:
        node_id = node["id"]
        node_name = node.get("name", node_id)
        node_type = get_node_type(node.get("typeId"))
        register_fn = node_type.get("register") if node_type else None

        if not register_fn:
            continue

        trigger_id = f"{workflow_path}:{node_id}"
        node_data = node.get("data", {})
        callback = _make_trigger_callback(workflow_path, node_id, node_name)

        # Call register function with last execution time
        result = register_fn(node_data, callback, last_execution_time)

        if result.get("type") == "timed":
            # Schedule timed trigger
            await _schedule_timed_trigger(
                trigger_id,
                result["trigger_at"],
                result.get("interval_seconds", 300),
                node_data,
                register_fn,
                callback,
            )
        elif result.get("type") == "push":
            # Start push listener
            listener_fn = result.get("listener")
            if listener_fn:
                await _start_push_listener(
                    trigger_id,
                    listener_fn,
                    node_data,
                    callback,
                )


async def unregister_workflow_triggers(workflow_path: str) -> None:
    """Unregister all triggers for a workflow."""
    # Cancel timed triggers
    to_remove = [tid for tid in _timed_tasks if tid.startswith(f"{workflow_path}:")]
    for trigger_id in to_remove:
        task = _timed_tasks.pop(trigger_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    # Cancel push listeners
    to_remove = [tid for tid in _push_listeners if tid.startswith(f"{workflow_path}:")]
    for trigger_id in to_remove:
        task = _push_listeners.pop(trigger_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def start_trigger_system() -> None:
    """Start the trigger system - register triggers for all enabled workflows."""
    global _shutdown
    _shutdown = False

    if not WORKFLOWS_DIR:
        return

    enabled = get_enabled_workflows()

    for workflow_path, is_enabled in enabled.items():
        if not is_enabled:
            continue

        workflow_file = WORKFLOWS_DIR / workflow_path
        if not workflow_file.exists():
            continue

        try:
            workflow = json.loads(workflow_file.read_text())
            await register_workflow_triggers(workflow_path, workflow)
        except (json.JSONDecodeError, OSError):
            pass


async def stop_trigger_system() -> None:
    """Stop all triggers."""
    global _shutdown
    _shutdown = True

    # Cancel all timed tasks
    for task in _timed_tasks.values():
        task.cancel()
    for task in _timed_tasks.values():
        try:
            await task
        except asyncio.CancelledError:
            pass
    _timed_tasks.clear()

    # Cancel all push listeners
    for task in _push_listeners.values():
        task.cancel()
    for task in _push_listeners.values():
        try:
            await task
        except asyncio.CancelledError:
            pass
    _push_listeners.clear()
