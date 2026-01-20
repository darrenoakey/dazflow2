#!/usr/bin/env python3
"""Dazflow2 Agent - Connects to server and executes workflow tasks."""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

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


class DazflowAgent:
    """Agent that connects to dazflow2 server and executes tasks."""

    VERSION = "1.0.0"
    HEARTBEAT_INTERVAL = 30  # seconds
    RECONNECT_DELAY = 5  # seconds
    MAX_RECONNECT_DELAY = 60  # seconds

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
        return f"{url}/ws/agent/{self.name}/{self.secret}"

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
        elif msg_type == "task_available":
            # Task handling will be implemented in later PRs
            print(f"[{self._timestamp()}] Task available: {message.get('task', {}).get('id', 'unknown')}")
        elif msg_type == "task_claimed_ok":
            # Task claim was successful
            task_id = message.get("task_id", "unknown")
            print(f"[{self._timestamp()}] Successfully claimed task: {task_id}")
        elif msg_type == "task_claimed_fail":
            # Task claim failed
            task_id = message.get("task_id", "unknown")
            reason = message.get("reason", "unknown")
            print(f"[{self._timestamp()}] Failed to claim task {task_id}: {reason}")
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
