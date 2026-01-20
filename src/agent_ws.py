"""WebSocket handler for agent connections."""

from datetime import UTC, datetime

from fastapi import WebSocket, WebSocketDisconnect

from .agents import get_registry
from .task_queue import get_queue

# Track connected agents
_connected_agents: dict[str, WebSocket] = {}


# ##################################################################
# handle agent websocket connection
# authenticates agent, accepts connection, tracks status, handles messages
async def handle_agent_connection(websocket: WebSocket, name: str, secret: str):
    registry = get_registry()

    # Verify the agent exists and secret is valid
    if not registry.verify_secret(name, secret):
        await websocket.close(code=4001, reason="Invalid credentials")
        return

    agent = registry.get_agent(name)
    if not agent:
        await websocket.close(code=4001, reason="Agent not found")
        return

    if not agent.enabled:
        await websocket.close(code=4002, reason="Agent is disabled")
        return

    # Accept the connection
    await websocket.accept()

    # Track the connection
    _connected_agents[name] = websocket

    # Update agent status
    registry.update_agent(
        name,
        status="online",
        last_seen=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        ip_address=websocket.client.host if websocket.client else None,
    )

    # Send connect acknowledgment
    await websocket.send_json({"type": "connect_ok"})

    try:
        # Handle messages until disconnect
        while True:
            data = await websocket.receive_json()
            await handle_agent_message(name, data, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        # Clean up on disconnect
        if name in _connected_agents:
            del _connected_agents[name]

        registry.update_agent(name, status="offline", last_seen=datetime.now(UTC).isoformat().replace("+00:00", "Z"))

        # Requeue any tasks claimed by this agent
        queue = get_queue()
        queue.requeue_agent_tasks(name)


# ##################################################################
# handle message from agent
# processes different message types from connected agents
async def handle_agent_message(name: str, message: dict, websocket: WebSocket):
    msg_type = message.get("type")

    if msg_type == "heartbeat":
        # Update last seen and respond
        registry = get_registry()
        registry.update_agent(name, last_seen=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        await websocket.send_json({"type": "heartbeat_ack"})

    elif msg_type == "task_claim":
        # Agent wants to claim a task
        task_id = message.get("task_id")
        queue = get_queue()
        success = queue.claim_task(task_id, name)
        if success:
            await websocket.send_json({"type": "task_claimed_ok", "task_id": task_id})
        else:
            await websocket.send_json({"type": "task_claimed_fail", "task_id": task_id, "reason": "Task not available"})

    elif msg_type == "task_complete":
        # Agent completed a task
        task_id = message.get("task_id")
        result = message.get("result", {})
        queue = get_queue()
        queue.complete_task(task_id, result)

    elif msg_type == "task_failed":
        # Agent failed a task
        task_id = message.get("task_id")
        error = message.get("error", "Unknown error")
        queue = get_queue()
        queue.fail_task(task_id, error)

    elif msg_type == "credentials_report":
        # Agent reports what credentials it has
        credentials = message.get("credentials", [])
        registry = get_registry()
        registry.update_agent(name, credentials=credentials)

    elif msg_type == "credential_ack":
        # Agent acknowledges receiving a credential
        cred_name = message.get("name")
        status = message.get("status")
        if status == "success":
            # Add credential to agent's list
            registry = get_registry()
            agent = registry.get_agent(name)
            if agent and cred_name not in agent.credentials:
                updated_creds = agent.credentials + [cred_name]
                registry.update_agent(name, credentials=updated_creds)

    # Other message types will be added in later PRs


# ##################################################################
# get list of connected agent names
# returns names of all currently connected agents
def get_connected_agents() -> list[str]:
    return list(_connected_agents.keys())


# ##################################################################
# check if agent is connected
# returns true if agent has active websocket connection
def is_agent_connected(name: str) -> bool:
    return name in _connected_agents


# ##################################################################
# send message to connected agent
# sends json message to agent if connected, returns success status
async def send_to_agent(name: str, message: dict) -> bool:
    websocket = _connected_agents.get(name)
    if websocket:
        await websocket.send_json(message)
        return True
    return False


# ##################################################################
# push credential to agent
# sends credential data to connected agent via websocket
async def push_credential_to_agent(agent_name: str, credential_name: str, credential_data: dict) -> bool:
    if not is_agent_connected(agent_name):
        return False

    message = {"type": "credential_push", "name": credential_name, "credential": credential_data}

    return await send_to_agent(agent_name, message)
