#!/usr/bin/env python3
"""Dazflow2 Agent - Connects to server and executes workflow tasks."""

import argparse
import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

# Add agent directory to path for importing downloaded code
AGENT_DIR = Path(__file__).parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

try:
    import websockets
except ImportError:
    print("ERROR: websockets package required. Install with: pip install websockets")
    sys.exit(1)

try:
    import keyring
except ImportError:
    print("ERROR: keyring package required. Install with: pip install keyring")
    sys.exit(1)


class LogBuffer:
    """Buffers and ships logs to server."""

    def __init__(self, max_lines=100, flush_interval=0.5):
        """Initialize log buffer.

        Args:
            max_lines: Maximum lines before auto-flush
            flush_interval: Seconds between periodic flushes
        """
        self._buffer = []
        self._lock = asyncio.Lock()
        self._max_lines = max_lines
        self._flush_interval = flush_interval

    async def add(self, task_id, line):
        """Add a log line to the buffer.

        Args:
            task_id: Task ID this log belongs to
            line: Log line text
        """
        async with self._lock:
            self._buffer.append(
                {
                    "task_id": task_id,
                    "line": line,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )

    async def add_and_maybe_flush(self, task_id, line, websocket):
        """Add a log line and flush if buffer is full.

        Args:
            task_id: Task ID this log belongs to
            line: Log line text
            websocket: WebSocket connection to flush to
        """
        await self.add(task_id, line)
        async with self._lock:
            if len(self._buffer) >= self._max_lines:
                await self._flush_locked(websocket)

    async def flush(self, websocket):
        """Send buffered logs to server.

        Args:
            websocket: WebSocket connection to send to
        """
        async with self._lock:
            await self._flush_locked(websocket)

    async def _flush_locked(self, websocket):
        """Internal flush - must be called with lock held.

        Args:
            websocket: WebSocket connection to send to
        """
        if not self._buffer:
            return

        # Group logs by task_id
        tasks_logs = {}
        for log_entry in self._buffer:
            task_id = log_entry["task_id"]
            if task_id not in tasks_logs:
                tasks_logs[task_id] = []
            tasks_logs[task_id].append({"line": log_entry["line"], "timestamp": log_entry["timestamp"]})

        # Send one message per task
        for task_id, logs in tasks_logs.items():
            message = {"type": "task_progress", "task_id": task_id, "logs": logs}
            await websocket.send(json.dumps(message))

        # Clear buffer
        self._buffer.clear()

    async def run_shipping_loop(self, websocket):
        """Background task that periodically flushes logs.

        Args:
            websocket: WebSocket connection to send to
        """
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush(websocket)


# ##################################################################
# get agent version from VERSION file
def _get_agent_version() -> str:
    """Read version from VERSION file in agent directory."""
    version_file = AGENT_DIR / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"


# ##################################################################
# dazflow agent
# connects to server and executes tasks
class DazflowAgent:
    """Agent that connects to dazflow2 server and executes tasks."""

    VERSION = _get_agent_version()
    HEARTBEAT_INTERVAL = 30  # seconds
    RECONNECT_DELAY = 5  # seconds
    MAX_RECONNECT_DELAY = 60  # seconds
    UPGRADE_EXIT_CODE = 42  # Exit code to signal upgrade needed

    def __init__(self, server_url: str, name: str, secret: str):
        """Initialize the agent.

        Args:
            server_url: Server URL (e.g., "ws://localhost:5000")
            name: Agent name
            secret: Agent secret for authentication
        """
        self.server_url = server_url.rstrip("/")
        self.name = name
        self.secret = secret
        self.ws = None
        self.running = True
        self.connected = False
        self._reconnect_delay = self.RECONNECT_DELAY
        self._pending_tasks: dict[str, dict] = {}  # task_id -> task details (awaiting claim)
        self._current_task: str | None = None  # Currently executing task

    def _get_ws_url(self) -> str:
        """Get the full WebSocket URL."""
        # Convert http:// to ws:// if needed
        url = self.server_url
        if url.startswith("http://"):
            url = "ws://" + url[7:]
        elif url.startswith("https://"):
            url = "wss://" + url[8:]
        elif not url.startswith("ws://") and not url.startswith("wss://"):
            url = "ws://" + url
        # URL-encode name to handle spaces and special characters
        encoded_name = quote(self.name, safe="")
        return f"{url}/ws/agent/{encoded_name}/{self.secret}"

    async def connect(self):
        """Connect to the server."""
        ws_url = self._get_ws_url()
        print(f"[{self._timestamp()}] Connecting to {self.server_url}...")

        try:
            self.ws = await websockets.connect(ws_url)

            # Wait for connect_ok or rejection
            response = await asyncio.wait_for(self.ws.recv(), timeout=10)
            data = json.loads(response)

            if data.get("type") == "connect_ok":
                self.connected = True
                self._reconnect_delay = self.RECONNECT_DELAY  # Reset delay on success
                print(f"[{self._timestamp()}] Connected successfully")

                # Send version to server
                await self.send({"type": "version", "version": self.VERSION})

                # Report credentials to server
                await self._report_credentials()

                return True
            else:
                print(f"[{self._timestamp()}] Connection rejected: {data}")
                await self.ws.close()
                return False

        except Exception as e:
            print(f"[{self._timestamp()}] Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the server."""
        self.connected = False
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def send(self, message: dict):
        """Send a message to the server."""
        if self.ws and self.connected:
            await self.ws.send(json.dumps(message))

    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self.running and self.connected:
            try:
                await self.send({"type": "heartbeat"})
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
            except Exception as e:
                print(f"[{self._timestamp()}] Heartbeat error: {e}")
                break

    async def _receive_loop(self):
        """Receive and handle messages from server."""
        while self.running and self.connected:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                await self._handle_message(data)
            except websockets.ConnectionClosed:
                print(f"[{self._timestamp()}] Connection closed by server")
                break
            except Exception as e:
                print(f"[{self._timestamp()}] Receive error: {e}")
                break

        self.connected = False

    async def _handle_message(self, message: dict):
        """Handle a message from the server."""
        msg_type = message.get("type")

        if msg_type == "heartbeat_ack":
            pass  # Heartbeat acknowledged
        elif msg_type == "upgrade_required":
            # Server says we need to upgrade
            print(f"[{self._timestamp()}] Upgrade required, exiting for update...")
            self.running = False
            await self.disconnect()
            sys.exit(self.UPGRADE_EXIT_CODE)
        elif msg_type == "task_available":
            # Claim the task if we're not already working
            task_id = message.get("task_id")
            if task_id and not self._current_task:
                print(f"[{self._timestamp()}] Task available: {task_id}, claiming...")
                # Store task details for when claim succeeds
                self._pending_tasks[task_id] = {
                    "execution_snapshot": message.get("execution_snapshot", {}),
                    "workflow_name": message.get("workflow_name", "unknown"),
                    "node_id": message.get("node_id"),
                }
                await self.send({"type": "task_claim", "task_id": task_id})
            else:
                print(f"[{self._timestamp()}] Task available but busy with {self._current_task}")
        elif msg_type == "task_claimed_ok":
            # Task claim was successful - execute it
            task_id = message.get("task_id")
            print(f"[{self._timestamp()}] Successfully claimed task: {task_id}")
            if task_id in self._pending_tasks:
                task_details = self._pending_tasks.pop(task_id)
                self._current_task = task_id
                # Execute in background to not block message handling
                asyncio.create_task(self._execute_task(task_id, task_details))
        elif msg_type == "task_claimed_fail":
            # Task claim failed - remove from pending
            task_id = message.get("task_id", "unknown")
            reason = message.get("reason", "unknown")
            print(f"[{self._timestamp()}] Failed to claim task {task_id}: {reason}")
            self._pending_tasks.pop(task_id, None)
        elif msg_type == "kill_task":
            # Task killing will be implemented in later PRs
            print(f"[{self._timestamp()}] Kill task: {message.get('task_id', 'unknown')}")
        elif msg_type == "config_update":
            print(f"[{self._timestamp()}] Config updated")
        elif msg_type == "credential_push":
            # Server is pushing a credential to us
            await self._handle_credential_push(message)
        else:
            print(f"[{self._timestamp()}] Unknown message type: {msg_type}")

    async def run(self):
        """Main run loop with reconnection logic."""
        print(f"[{self._timestamp()}] Agent '{self.name}' starting (v{self.VERSION})")

        while self.running:
            if await self.connect():
                # Run heartbeat and receive loops concurrently
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                receive_task = asyncio.create_task(self._receive_loop())

                # Wait for either to complete (usually means disconnection)
                done, pending = await asyncio.wait([heartbeat_task, receive_task], return_when=asyncio.FIRST_COMPLETED)

                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                await self.disconnect()

            if self.running:
                print(f"[{self._timestamp()}] Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                # Exponential backoff
                self._reconnect_delay = min(self._reconnect_delay * 2, self.MAX_RECONNECT_DELAY)

    def stop(self):
        """Stop the agent."""
        print(f"[{self._timestamp()}] Stopping agent...")
        self.running = False

    def _timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def _get_keyring_service(self) -> str:
        """Get the keyring service name for this agent."""
        return f"dazflow-agent-{self.name}"

    def _list_credentials(self) -> list[str]:
        """List credentials stored in this agent's keyring."""
        try:
            service = self._get_keyring_service()
            index_json = keyring.get_password(service, "credential_index")
            if index_json:
                return json.loads(index_json)
        except Exception:
            pass
        return []

    def _save_credential_index(self, names: list[str]) -> None:
        """Save the credential index."""
        service = self._get_keyring_service()
        keyring.set_password(service, "credential_index", json.dumps(names))

    async def _report_credentials(self) -> None:
        """Report credentials to server after connecting."""
        credentials = self._list_credentials()
        await self.send({"type": "credentials_report", "credentials": credentials})

    async def _execute_task(self, task_id: str, task_details: dict) -> None:
        """Execute a claimed task."""
        execution = {}
        try:
            print(f"[{self._timestamp()}] Executing task {task_id}...")

            execution_snapshot = task_details.get("execution_snapshot", {})
            workflow = execution_snapshot.get("workflow", {})
            execution = execution_snapshot.get("execution", {})
            node_id = execution_snapshot.get("node_id")

            if not node_id:
                raise ValueError("No node_id in execution snapshot")

            # Import executor from downloaded code
            try:
                from src.executor import execute_node
            except ImportError as e:
                raise RuntimeError(f"Failed to import executor (code not downloaded?): {e}") from e

            # Execute the node in a thread to avoid blocking the event loop
            # This is critical for long-running nodes like run_command
            print(f"[{self._timestamp()}] Running node {node_id}...")
            new_execution = await asyncio.to_thread(execute_node, node_id, workflow, execution)

            # Get the result for this node
            node_result = new_execution.get(node_id, {})

            print(f"[{self._timestamp()}] Task {task_id} completed successfully")

            # Report success
            await self.send(
                {
                    "type": "task_complete",
                    "task_id": task_id,
                    "result": {
                        "success": True,
                        "execution": new_execution,
                        "node_output": node_result.get("output"),
                    },
                }
            )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            tb = traceback.format_exc()
            print(f"[{self._timestamp()}] Task {task_id} failed: {error_msg}")
            print(tb)

            # Report failure — include execution state so error details are preserved
            await self.send(
                {
                    "type": "task_failed",
                    "task_id": task_id,
                    "error": error_msg,
                    "error_details": tb,
                    "execution": execution,
                }
            )

        finally:
            # Always clear current task so agent can accept new work
            self._current_task = None

    async def _handle_credential_push(self, message: dict) -> None:
        """Handle a credential being pushed from the server."""
        cred_name = message.get("name")
        credential = message.get("credential")

        if not cred_name or not credential:
            print(f"[{self._timestamp()}] Invalid credential_push message")
            return

        try:
            # Store credential in keyring
            service = self._get_keyring_service()
            key = f"credential:{cred_name}"
            keyring.set_password(service, key, json.dumps(credential))

            # Update index
            index = self._list_credentials()
            if cred_name not in index:
                index.append(cred_name)
                self._save_credential_index(index)

            print(f"[{self._timestamp()}] Stored credential: {cred_name}")

            # Send acknowledgment
            await self.send({"type": "credential_ack", "name": cred_name, "status": "success"})

        except Exception as e:
            print(f"[{self._timestamp()}] Failed to store credential {cred_name}: {e}")
            # Send failure acknowledgment
            await self.send({"type": "credential_ack", "name": cred_name, "status": "failed", "error": str(e)})


def main():
    parser = argparse.ArgumentParser(description="Dazflow2 Agent")
    parser.add_argument("--server", required=True, help="Server URL (e.g., http://localhost:5000)")
    parser.add_argument("--name", required=True, help="Agent name")
    parser.add_argument("--secret", required=True, help="Agent secret")
    args = parser.parse_args()

    agent = DazflowAgent(args.server, args.name, args.secret)

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
