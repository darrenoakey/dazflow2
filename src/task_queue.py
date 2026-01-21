"""Task queue for distributing work to agents."""

from dataclasses import dataclass
from datetime import datetime, timezone

from .agents import get_registry
from .concurrency import get_tracker


@dataclass
class Task:
    """A task to be executed by an agent."""

    id: str
    execution_id: str
    workflow_name: str
    node_id: str
    execution_snapshot: dict  # Full execution state
    queued_at: str
    claimed_by: str | None = None
    claimed_at: str | None = None
    logs: list[dict] | None = None  # Log lines with timestamps


class TaskQueue:
    """Queue for distributing tasks to agents."""

    def __init__(self):
        self._pending: list[Task] = []
        self._in_progress: dict[str, Task] = {}  # task_id -> Task
        self._callbacks: dict[str, callable] = {}  # task_id -> completion callback

    def _get_node_data(self, task: Task) -> dict:
        """Get the node data from a task's execution snapshot."""
        workflow = task.execution_snapshot.get("workflow", {})
        nodes = workflow.get("nodes", [])
        for node in nodes:
            if node.get("id") == task.node_id:
                return node.get("data", {})
        return {}

    def enqueue(self, task: Task, on_complete: callable = None) -> None:
        """Add a task to the queue."""
        self._pending.append(task)
        if on_complete:
            self._callbacks[task.id] = on_complete
        # Notify agents of new task
        self._notify_agents()

    def get_available_task(self, agent_name: str) -> Task | None:
        """Get the next available task for an agent.

        Returns None if no suitable task is available.
        """
        registry = get_registry()
        agent = registry.get_agent(agent_name)
        if not agent or not agent.enabled:
            return None

        for task in self._pending:
            if self._can_agent_run_task(agent, task):
                return task
        return None

    def claim_task(self, task_id: str, agent_name: str) -> bool:
        """Attempt to claim a task for an agent.

        Returns True if successfully claimed, False otherwise.
        """
        # Find task in pending
        task = None
        for t in self._pending:
            if t.id == task_id:
                task = t
                break

        if not task:
            return False

        # Move to in_progress
        self._pending.remove(task)
        task.claimed_by = agent_name
        task.claimed_at = datetime.now(timezone.utc).isoformat()
        self._in_progress[task_id] = task

        # Update agent current task
        registry = get_registry()
        registry.update_agent(agent_name, current_task=task.execution_id)

        # Increment concurrency group count
        node_data = self._get_node_data(task)
        agent_config = node_data.get("agentConfig", {})
        concurrency_group = agent_config.get("concurrencyGroup")
        if concurrency_group:
            tracker = get_tracker()
            tracker.increment(concurrency_group)

        return True

    def complete_task(self, task_id: str, result: dict) -> None:
        """Mark a task as completed."""
        task = self._in_progress.pop(task_id, None)
        if task:
            # Decrement concurrency group count
            node_data = self._get_node_data(task)
            agent_config = node_data.get("agentConfig", {})
            concurrency_group = agent_config.get("concurrencyGroup")
            if concurrency_group:
                tracker = get_tracker()
                tracker.decrement(concurrency_group)

            # Clear agent current task
            registry = get_registry()
            if task.claimed_by:
                registry.update_agent(task.claimed_by, current_task=None)
                # Increment task count
                agent = registry.get_agent(task.claimed_by)
                if agent:
                    registry.update_agent(task.claimed_by, total_tasks=agent.total_tasks + 1)

            # Include logs in result if available
            if task.logs:
                result = {**result, "logs": task.logs}

            # Call completion callback
            callback = self._callbacks.pop(task_id, None)
            if callback:
                callback(result)

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        task = self._in_progress.pop(task_id, None)
        if task:
            # Decrement concurrency group count
            node_data = self._get_node_data(task)
            agent_config = node_data.get("agentConfig", {})
            concurrency_group = agent_config.get("concurrencyGroup")
            if concurrency_group:
                tracker = get_tracker()
                tracker.decrement(concurrency_group)

            # Clear agent current task
            registry = get_registry()
            agent_name = task.claimed_by
            if agent_name:
                registry.update_agent(agent_name, current_task=None)

            # Call completion callback with error (include agent name for debugging)
            callback = self._callbacks.pop(task_id, None)
            if callback:
                callback({"error": error, "agent": agent_name, "node_id": task.node_id})

    def requeue_agent_tasks(self, agent_name: str) -> None:
        """Requeue all tasks claimed by an agent (on disconnect)."""
        tasks_to_requeue = [task for task in self._in_progress.values() if task.claimed_by == agent_name]

        for task in tasks_to_requeue:
            # Decrement concurrency group count
            node_data = self._get_node_data(task)
            agent_config = node_data.get("agentConfig", {})
            concurrency_group = agent_config.get("concurrencyGroup")
            if concurrency_group:
                tracker = get_tracker()
                tracker.decrement(concurrency_group)

            del self._in_progress[task.id]
            task.claimed_by = None
            task.claimed_at = None
            self._pending.insert(0, task)  # Add to front of queue

    def _can_agent_run_task(self, agent, task: Task) -> bool:
        """Check if an agent can run a task."""
        if not agent.enabled or agent.status != "online":
            return False

        # Get node data from task's execution snapshot
        node_data = self._get_node_data(task)
        agent_config = node_data.get("agentConfig", {})

        # Check agent selection (OR logic - any of the listed agents)
        agents_list = agent_config.get("agents", [])
        if agents_list:  # If specific agents are listed
            if agent.name not in agents_list:
                return False

        # Check required tags (AND logic - must have ALL tags)
        required_tags = agent_config.get("requiredTags", [])
        for tag in required_tags:
            if tag not in agent.tags:
                return False

        # Check required credentials (agent must have the credential)
        required_credential = node_data.get("credentials")
        if required_credential:
            if required_credential not in agent.credentials:
                return False

        # Check concurrency group limits
        concurrency_group = agent_config.get("concurrencyGroup")
        if concurrency_group:
            tracker = get_tracker()
            if not tracker.can_start(concurrency_group):
                return False

        return True

    def _notify_agents(self) -> None:
        """Notify connected agents of available tasks."""
        import asyncio

        from .agent_ws import get_connected_agents, send_to_agent

        async def _send_notifications():
            for agent_name in get_connected_agents():
                task = self.get_available_task(agent_name)
                if task:
                    await send_to_agent(
                        agent_name,
                        {
                            "type": "task_available",
                            "task_id": task.id,
                            "workflow_name": task.workflow_name,
                            "node_id": task.node_id,
                            "execution_snapshot": task.execution_snapshot,
                        },
                    )

        # Run async notification in background
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send_notifications())
        except RuntimeError:
            # No running loop - skip notification
            pass

    def get_pending_count(self) -> int:
        """Get count of pending tasks."""
        return len(self._pending)

    def get_in_progress_count(self) -> int:
        """Get count of in-progress tasks."""
        return len(self._in_progress)

    def add_task_logs(self, task_id: str, logs: list[dict]) -> None:
        """Add log lines to a task.

        Args:
            task_id: Task ID to add logs to
            logs: List of log entries with 'line' and 'timestamp' fields
        """
        task = self._in_progress.get(task_id)
        if task:
            if task.logs is None:
                task.logs = []
            task.logs.extend(logs)


# Global queue instance
_queue: TaskQueue | None = None


# ##################################################################
# get global task queue instance
# creates instance on first call
def get_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue


# ##################################################################
# set global task queue instance
# replaces current queue with new one for testing
def set_queue(queue: TaskQueue) -> None:
    global _queue
    _queue = queue
