# Distributed Agent Execution System - Design Document

## Overview

This document describes the architecture for a distributed agent-based execution system for dazflow2. The system allows workflow nodes to be executed on multiple machines (agents) that connect to a central server.

## Goals

1. **Distributed Execution** - Run workflow nodes on different machines
2. **Resilience** - Agents can come and go, tasks get requeued on failure
3. **Capability-based Routing** - Route tasks based on agent tags and credentials
4. **Resource Protection** - Concurrency groups limit simultaneous executions
5. **Zero Downtime Upgrades** - Agents auto-upgrade when server updates

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              SERVER                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │  Workflow   │  │    Task     │  │   Agent     │  │  Concurrency │  │
│  │   Engine    │  │    Queue    │  │  Registry   │  │   Tracker    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘  │
│         │                │                │                 │          │
│         └────────────────┴────────────────┴─────────────────┘          │
│                                   │                                     │
│                            WebSocket Hub                                │
│                                   │                                     │
│  ┌────────────────────────────────┼────────────────────────────────┐   │
│  │                    Built-in Agent                                │   │
│  │                    (in-process, same code as remote)             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ WebSocket
              ┌────────────────────┼────────────────────┐
              │                    │                    │
         ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
         │  Agent  │          │  Agent  │          │  Agent  │
         │ "gpu-1" │          │ "docker"│          │ "mac-m2"│
         │ [gpu]   │          │ [docker]│          │ [apple] │
         │ pri: 10 │          │ pri: 5  │          │ pri: 5  │
         └─────────┘          └─────────┘          └─────────┘
```

## Key Concepts

### Agents

An **agent** is a process that can execute workflow nodes. Agents:
- Connect to the server via WebSocket
- Pull tasks from the queue
- Execute nodes and report results
- Can run on any machine (local, remote, Docker, etc.)

The **built-in agent** is compiled into the server and uses the exact same code as remote agents. It connects to the server via internal WebSocket.

### Tags

**Tags** are strings that describe agent capabilities (e.g., "gpu", "docker", "linux"). Tags are:
- Managed manually from the Agents tab
- Assigned to agents by clicking/double-clicking
- Used for task routing (nodes can require specific tags)

### Credentials as Implicit Tags

When a node requires a credential (e.g., discord_send requires "discord" credential), only agents that have that credential can run the node. This is automatic - no manual configuration needed.

### Concurrency Groups

**Concurrency groups** limit how many tasks of a certain type can run simultaneously across all agents. Example: "claude" group with limit 3 means only 3 Claude API calls at once system-wide.

### Agent Selection Per Node

Each node can configure:
- **Specific agents** - Only these agents can run this node (OR logic)
- **Required tags** - Agent must have ALL these tags (AND logic)
- **Concurrency group** - Task counts against this group's limit

Default is "any agent" with no required tags.

## Data Model

### Agents (`{data_dir}/agents.json`)

```json
{
  "built-in": {
    "name": "built-in",
    "enabled": true,
    "priority": 0,
    "tags": [],
    "status": "online",
    "last_seen": "2024-01-20T10:30:00Z",
    "ip_address": "127.0.0.1",
    "version": "1.0.0",
    "total_tasks": 47,
    "secret_hash": "abc123..."
  },
  "gpu-worker": {
    "name": "gpu-worker",
    "enabled": true,
    "priority": 10,
    "tags": ["gpu", "cuda"],
    "status": "offline",
    "last_seen": "2024-01-20T08:00:00Z",
    "ip_address": "10.0.0.50",
    "version": "1.0.0",
    "total_tasks": 23,
    "secret_hash": "def456..."
  }
}
```

### Tags (`{data_dir}/tags.json`)

```json
["gpu", "cuda", "docker", "linux", "macos", "windows"]
```

### Concurrency Groups (`{data_dir}/concurrency_groups.json`)

```json
{
  "claude": { "limit": 3 },
  "3d-printer": { "limit": 1 },
  "heavy-compute": { "limit": 2 }
}
```

### Node Agent Configuration (in workflow JSON)

```json
{
  "nodes": {
    "node-1": {
      "type": "discord/discord_send",
      "data": { ... },
      "agentConfig": {
        "agents": [],
        "requiredTags": ["gpu"],
        "concurrencyGroup": "heavy-compute"
      }
    }
  }
}
```

- `agents: []` means "any agent"
- `agents: ["worker-1", "worker-2"]` means "worker-1 OR worker-2"
- `requiredTags: ["gpu", "cuda"]` means "must have gpu AND cuda"

## Task Queue

### Task Entry

```json
{
  "id": "task-uuid",
  "execution_id": "exec-uuid",
  "workflow_name": "my-workflow",
  "node_id": "node-1",
  "execution_snapshot": { ... },
  "agent_config": {
    "agents": [],
    "requiredTags": ["gpu"],
    "concurrencyGroup": "heavy-compute"
  },
  "required_credential": "discord",
  "queued_at": "2024-01-20T10:30:00Z",
  "claimed_by": null,
  "claimed_at": null
}
```

### Matching Algorithm

```python
def can_agent_run_task(agent: Agent, task: Task) -> bool:
    # 1. Agent must be enabled and online
    if not agent.enabled or agent.status != "online":
        return False

    # 2. Check agent selection (OR logic)
    if task.agent_config.agents:  # Specific agents listed
        if agent.name not in task.agent_config.agents:
            return False

    # 3. Check required tags (AND logic)
    for tag in task.agent_config.requiredTags:
        if tag not in agent.tags:
            return False

    # 4. Check credential requirement (implicit)
    if task.required_credential:
        if task.required_credential not in agent.credentials:
            return False

    # 5. Check concurrency group
    if task.agent_config.concurrencyGroup:
        group = get_concurrency_group(task.agent_config.concurrencyGroup)
        if current_count(group) >= group.limit:
            return False

    return True

def select_agent_for_task(task: Task) -> Agent | None:
    eligible = [a for a in agents if can_agent_run_task(a, task)]
    if not eligible:
        return None  # Task waits in queue
    # Sort by priority (descending)
    eligible.sort(key=lambda a: -a.priority)
    return eligible[0]
```

## Agent-Server Protocol (WebSocket)

### Connection Flow

1. Agent connects to `ws://server:port/ws/agent`
2. Agent sends: `{ "type": "connect", "name": "...", "secret": "...", "version": "1.0.0", "credentials": ["discord", "openai"] }`
3. Server validates secret, checks version
4. Server sends: `{ "type": "connect_ok" }` or `{ "type": "upgrade_required", "version": "1.1.0", "url": "..." }` or `{ "type": "connect_rejected", "reason": "..." }`
5. Agent starts heartbeat loop

### Message Types

**Agent → Server:**
```
{ "type": "connect", "name": "...", "secret": "...", "version": "...", "credentials": [...] }
{ "type": "heartbeat" }
{ "type": "task_claim", "task_id": "..." }
{ "type": "task_progress", "task_id": "...", "logs": [...] }
{ "type": "task_complete", "task_id": "...", "result": {...} }
{ "type": "task_failed", "task_id": "...", "error": "..." }
{ "type": "credential_ack", "name": "..." }
```

**Server → Agent:**
```
{ "type": "connect_ok" }
{ "type": "connect_rejected", "reason": "..." }
{ "type": "upgrade_required", "version": "...", "url": "..." }
{ "type": "heartbeat_ack" }
{ "type": "task_available", "task": {...} }
{ "type": "task_claimed_ok", "task_id": "..." }
{ "type": "task_claimed_fail", "task_id": "...", "reason": "..." }
{ "type": "credential_push", "name": "...", "data": {...} }
{ "type": "kill_task", "task_id": "..." }
{ "type": "config_update", "enabled": bool, "priority": int, "tags": [...] }
```

### Heartbeat

- Agent sends heartbeat every 30 seconds
- If server doesn't receive heartbeat for 60 seconds, agent marked offline
- When agent goes offline, any claimed tasks are requeued

### Disconnect Handling

**Server side:**
- Mark agent as offline
- Requeue any tasks claimed by this agent
- Update last_seen timestamp

**Agent side:**
- Immediately abandon any in-progress task (kill subprocess, etc.)
- Attempt to reconnect with exponential backoff

## Agent Program

The agent is a single Python file (`agent/agent.py`) that:
1. Connects to server via WebSocket
2. Maintains connection with heartbeat
3. Receives task notifications
4. Claims and executes tasks
5. Reports results and logs
6. Stores credentials in local keyring
7. Self-upgrades when instructed

### Agent Updater Shim

A small shim (`agent/agent_updater.py`) handles self-upgrade:
1. Starts `agent.py` as subprocess
2. If `agent.py` exits with code 42 (upgrade needed), downloads new version
3. Restarts `agent.py`

### Log Buffering

Agent buffers logs locally and ships them asynchronously:
- Logs added to buffer immediately
- Separate thread ships batches every 500ms
- If disconnected, logs buffer locally until reconnection

## Credentials

### Storage

- Server stores credentials in keyring (as before)
- Each agent stores its own copy in keyring under `dazflow-agent-{name}` service

### Distribution

When saving a credential:
1. UI shows checkbox list of agents
2. User selects which agents should receive it
3. Server pushes credential to selected agents via WebSocket
4. Credential data is encrypted with per-agent key
5. Agent stores in local keyring, sends ack

### Auto-push on Update

When credential is updated, server automatically pushes to all agents that have it.

## Concurrency Groups

### Tracking

Server maintains in-memory count of active tasks per group:
```python
class ConcurrencyTracker:
    _counts: dict[str, int] = {}

    def can_start(self, group: str) -> bool:
        limit = groups[group].limit
        return self._counts.get(group, 0) < limit

    def increment(self, group: str): self._counts[group] = self._counts.get(group, 0) + 1
    def decrement(self, group: str): self._counts[group] = max(0, self._counts.get(group, 0) - 1)
```

### Events that decrement count:
- Task completes successfully
- Task fails
- Task times out
- Agent disconnects (task requeued)

## Timeouts

### Task Timeout

- Global default timeout (configurable)
- Per-node-type timeout (specified in code, not user-configurable yet)
- When timeout occurs:
  1. Server sends `kill_task` to agent
  2. Agent kills subprocess
  3. Task marked as failed
  4. Concurrency count decremented

## UI Components

### Agents Tab

```
┌─────────────────────────────────────────────────────────────────────┐
│ Agents                                                    [+ Create]│
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ ● built-in          [enabled] pri:0   tags: —         tasks: 47 │ │
│ │   127.0.0.1         online    v1.0.0                            │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ● gpu-worker        [enabled] pri:10  tags: gpu,cuda  tasks: 23 │ │
│ │   10.0.0.50         online    v1.0.0  current: workflow-x       │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ ○ docker-runner     [disabled] pri:5  tags: docker    tasks: 12 │ │
│ │   10.0.0.51         offline   v1.0.0  last: 2h ago              │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ Tags: [gpu] [cuda] [docker]                              [+ Create] │
│ (double-click tag to assign to selected agent)                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Concurrency Tab

```
┌─────────────────────────────────────────────────────────────────────┐
│ Concurrency Groups                                        [+ Create]│
├─────────────────────────────────────────────────────────────────────┤
│ Name              Limit    Active                                   │
│ ─────────────────────────────────────                               │
│ claude            3        1                                        │
│ 3d-printer        1        0                                        │
│ heavy-compute     2        2 (at limit)                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Node Agent Configuration (in node editor)

```
┌─────────────────────────────────────────────────────────────────────┐
│ Agent Configuration                                                  │
├─────────────────────────────────────────────────────────────────────┤
│ Run on:        [▼ Any agent]                                        │
│                ┌─────────────────────────┐                          │
│                │ ☑ Any agent             │                          │
│                │ ─────────────────────── │                          │
│                │ ☐ built-in              │                          │
│                │ ☐ gpu-worker            │                          │
│                │ ☐ docker-runner         │                          │
│                │ ─────────────────────── │                          │
│                │ Require tags:           │                          │
│                │ ☐ gpu                   │                          │
│                │ ☐ cuda                  │                          │
│                └─────────────────────────┘                          │
│                                                                     │
│ Concurrency:   [▼ None]                                             │
└─────────────────────────────────────────────────────────────────────┘
```

## Testing Requirements

### Test Isolation

All tests run with:
- Different port (5099 instead of 5000)
- Isolated data directory (`/tmp/dazflow-test-{uuid}`)
- Real agents (spawned as subprocesses)
- Real task execution

### Test Patterns

```python
# Start test server
server = start_test_server(port=5099, data_dir=temp_dir)

# Create and connect real agent
agent_proc = subprocess.Popen([
    "python", "agent/agent.py",
    "--server", "ws://localhost:5099",
    "--name", "test-agent",
    "--secret", agent_secret
])

# Wait for agent to connect
wait_for_agent_online("test-agent")

# Execute workflow
execute_workflow("test-workflow")

# Verify agent ran task
assert get_execution_result()["executed_by"] == "test-agent"

# Cleanup
agent_proc.terminate()
server.stop()
```

## Implementation Phases

### PR 1: Test Infrastructure + Agent Data Model
- Server configuration (port, data_dir)
- Agent registry with JSON storage
- API endpoints (list, create agents)
- Agents tab UI (view only)

### PR 2: WebSocket Connection + Remote Agent
- WebSocket endpoint for agents
- Agent Python program
- Connect/disconnect handling
- Heartbeat mechanism

### PR 3: Built-in Agent
- Built-in agent using same code
- Auto-create on first startup

### PR 4: Task Queue + Distribution
- Task queue implementation
- Agent matching (any agent)
- Task claim/complete protocol

### PR 5: Agent Selection Per Node
- Node agent configuration
- UI for selecting agents
- Matching with specific agents

### PR 6: Tags
- Tags data model and API
- Tags management UI
- Required tags matching

### PR 7: Credentials Distribution
- Agent selection on credential save
- Credential push protocol
- Credential-based matching

### PR 8: Concurrency Groups
- Concurrency group data model
- Concurrency tab UI
- Limit enforcement

### PR 9: Agent Install + Self-Upgrade
- Install script generator
- Agent updater shim
- Version checking

### PR 10: Log Streaming
- Log buffering on agent
- Log shipping protocol
- Offline buffering

## Constraints

1. **No mocking in tests** - All tests use real agents, real connections
2. **Built-in agent uses same code** - No special-casing
3. **JSON file storage** - Read once on startup, write on changes
4. **Keyring for credentials** - Both server and agents
5. **Resilient connections** - Survive network interruptions
6. **Graceful degradation** - If no agents available, tasks wait
