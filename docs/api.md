# dazflow2 API Reference

This document describes all HTTP API endpoints.

## Base URL

```
http://localhost:31415
```

## Authentication

No authentication required for local access.

---

## Health & Status

### GET /health

Server health check.

**Response:**
```json
{
  "status": "ok",
  "start_time": 1706353200.123
}
```

### GET /heartbeat

Server-Sent Events stream for detecting server restarts.

**Response:** SSE stream with periodic heartbeats.

---

## Modules & Node Types

### GET /api/modules

Get all registered node types and credential types.

**Response:**
```json
{
  "nodeTypes": [
    {
      "id": "scheduled",
      "module": "core",
      "kind": "array",
      "requiredCredential": null,
      "hasDynamicEnums": false
    }
  ],
  "credentialTypes": [
    {
      "id": "discord",
      "module": "discord_nodes",
      "fields": [
        {"name": "token", "type": "string", "private": true}
      ]
    }
  ],
  "moduleUIPaths": [
    "/modules/core/nodes_ui.js?v=1706353200",
    "/modules/discord_nodes/nodes_ui.js?v=1706353200"
  ]
}
```

---

## Workflows

### GET /api/workflows

List workflows and folders.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | string | `""` | Folder path to list |

**Response:**
```json
{
  "items": [
    {
      "name": "my-workflow.json",
      "path": "my-workflow.json",
      "type": "workflow",
      "enabled": true,
      "stats": {
        "last_execution": "2025-01-27T12:00:00Z",
        "execution_count": 42
      }
    },
    {
      "name": "subfolder",
      "path": "subfolder",
      "type": "folder"
    }
  ]
}
```

### POST /api/workflows/new

Create a new empty workflow.

**Request:**
```json
{
  "name": "new-workflow",
  "folder": "optional/path"
}
```

**Response:**
```json
{
  "path": "optional/path/new-workflow.json",
  "workflow": {"nodes": [], "connections": []}
}
```

### POST /api/folders/new

Create a new folder.

**Request:**
```json
{
  "name": "folder-name",
  "parent": "optional/parent/path"
}
```

**Response:**
```json
{
  "path": "optional/parent/path/folder-name"
}
```

### GET /api/workflow/{path}

Get a workflow by path.

**Response:** Workflow JSON object.

### PUT /api/workflow/{path}

Save a workflow.

**Request:**
```json
{
  "workflow": {
    "nodes": [...],
    "connections": [...]
  }
}
```

**Response:**
```json
{
  "saved": true,
  "path": "workflow.json"
}
```

### POST /api/workflow/{path}/move

Move or rename a workflow.

**Request:**
```json
{
  "destination": "new/path/name.json"
}
```

**Response:**
```json
{
  "moved": true,
  "from": "old-path.json",
  "to": "new/path/name.json"
}
```

---

## Workflow Execution

### POST /api/workflow/{path}/execute

Execute a workflow synchronously.

**Request:**
```json
{
  "workflow": {...}
}
```

**Response:**
```json
{
  "execution": {...},
  "stats": {
    "duration_ms": 1234,
    "nodes_executed": 5
  }
}
```

### POST /api/workflow/{path}/queue

Queue a workflow for background execution.

**Response:**
```json
{
  "queue_id": "20250127-120000-workflow",
  "status": "queued"
}
```

### POST /api/execute

Execute a single node (used by worker/agents).

**Request:**
```json
{
  "node_id": "node-1",
  "workflow": {...},
  "execution": {...}
}
```

**Response:** Node execution result.

---

## Queue

### GET /api/queue

Get queued and running items.

**Response:**
```json
{
  "items": [
    {
      "id": "20250127-120000-workflow",
      "workflow_path": "workflow.json",
      "status": "running",
      "queued_at": 1706353200.123,
      "started_at": 1706353205.456,
      "current_step": 2
    }
  ]
}
```

---

## Executions

### GET /api/executions

List completed executions.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Max items to return |
| `before` | float | now | Unix timestamp for pagination |
| `workflow_path` | string | null | Filter by workflow |

**Response:**
```json
{
  "items": [...],
  "has_more": true,
  "last_updated": 1706353210.789
}
```

### GET /api/execution/{id}

Get a single execution.

**Response:** Full execution object.

### GET /api/executions/{id}/logs

Get execution logs.

**Response:**
```json
{
  "logs": [...]
}
```

---

## Workflow Versioning

### GET /api/workflow/{path}/history

Get git commit history for a workflow.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Max commits to return |

**Response:**
```json
{
  "commits": [
    {
      "hash": "abc123",
      "message": "Add notification node",
      "author": "dazflow",
      "timestamp": "2025-01-27T12:00:00Z"
    }
  ]
}
```

### GET /api/workflow/{path}/version/{hash}

Get workflow at a specific commit.

**Response:** Workflow JSON at that version.

### POST /api/workflow/{path}/restore/{hash}

Restore workflow to a previous version.

**Response:**
```json
{
  "restored": true,
  "workflow": {...}
}
```

---

## Enabled State

### GET /api/workflows/enabled

Get all enabled workflows.

**Response:**
```json
{
  "enabled": {
    "workflow1.json": true,
    "folder/workflow2.json": true
  }
}
```

### PUT /api/workflow/{path}/enabled

Enable or disable a workflow.

**Request:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "path": "workflow.json",
  "enabled": true
}
```

---

## Credentials

### GET /api/credentials

List all credential names.

**Response:**
```json
{
  "credentials": ["discord-bot", "postgres-prod"]
}
```

### GET /api/credential/{name}

Get a credential (private fields masked).

**Response:**
```json
{
  "name": "postgres-prod",
  "type": "postgres",
  "data": {
    "host": "localhost",
    "port": 5432,
    "password": "********"
  }
}
```

### PUT /api/credential/{name}

Save a credential.

**Request:**
```json
{
  "type": "postgres",
  "data": {
    "host": "localhost",
    "port": 5432,
    "database": "mydb",
    "user": "admin",
    "password": "secret"
  }
}
```

### DELETE /api/credential/{name}

Delete a credential.

### POST /api/credential/{name}/test

Test a saved credential.

**Response:**
```json
{
  "success": true,
  "message": "Connection successful"
}
```

### POST /api/credential-test

Test an unsaved credential.

**Request:**
```json
{
  "type": "postgres",
  "data": {...}
}
```

---

## Tags

### GET /api/tags

List all tags.

**Response:**
```json
{
  "tags": ["gpu-capable", "discord", "postgres-admin"]
}
```

### POST /api/tags

Create a new tag.

**Request:**
```json
{
  "name": "new-tag"
}
```

### DELETE /api/tags/{name}

Delete a tag.

---

## Concurrency Groups

### GET /api/concurrency-groups

List all concurrency groups.

**Response:**
```json
[
  {
    "name": "api-limit",
    "limit": 3,
    "active": 1
  }
]
```

### POST /api/concurrency-groups

Create a concurrency group.

**Request:**
```json
{
  "name": "new-group",
  "limit": 5
}
```

### GET /api/concurrency-groups/{name}

Get a group's details.

### PUT /api/concurrency-groups/{name}

Update a group's limit.

**Request:**
```json
{
  "limit": 10
}
```

### DELETE /api/concurrency-groups/{name}

Delete a group.

---

## Agents

### GET /api/agents

List all agents.

**Response:**
```json
{
  "agents": [
    {
      "name": "worker-1",
      "enabled": true,
      "priority": 1,
      "tags": ["gpu-capable"],
      "connected": true,
      "last_seen": "2025-01-27T12:00:00Z"
    }
  ]
}
```

### POST /api/agents

Create an agent.

**Request:**
```json
{
  "name": "new-agent"
}
```

### GET /api/agents/{name}

Get agent details.

### PUT /api/agents/{name}

Update agent settings.

**Request:**
```json
{
  "enabled": true,
  "priority": 2,
  "tags": ["discord", "postgres"]
}
```

### DELETE /api/agents/{name}

Delete an agent.

### GET /api/agents/{name}/install-script

Get bash installation script.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `secret` | string | Agent secret key |

---

## Dynamic Enums

### POST /api/dynamic-enum

Get dropdown options for dynamic enum fields.

**Request:**
```json
{
  "nodeTypeId": "discord_trigger",
  "enumKey": "server_id",
  "nodeData": {...},
  "credentialName": "discord-bot"
}
```

**Response:**
```json
{
  "options": [
    {"value": "123456", "label": "My Server"}
  ]
}
```

---

## Error Logging

### POST /api/client-error

Log a client-side error.

**Request:**
```json
{
  "message": "Error message",
  "stack": "Error stack trace",
  "url": "http://localhost:31415/",
  "userAgent": "Mozilla/5.0..."
}
```
