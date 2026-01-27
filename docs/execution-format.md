# dazflow2 Execution Format

This document describes the structure of workflow executions.

## Overview

When a workflow runs, an execution record tracks:
- The workflow snapshot at execution time
- Input/output for each node
- Status, timing, and errors

## Execution Lifecycle

1. **Queued**: Workflow added to queue
2. **Running**: Worker picked up, executing nodes
3. **Completed**: All nodes finished successfully
4. **Error**: A node failed, execution stopped

## Queue Item Structure

```json
{
  "id": "20250127-120000-workflow-name",
  "workflow_path": "folder/workflow.json",
  "workflow": {...},
  "execution": {...},
  "status": "completed",
  "queued_at": 1706353200.123,
  "started_at": 1706353205.456,
  "completed_at": 1706353210.789,
  "current_step": 4,
  "error": null,
  "error_node_id": null,
  "error_details": null,
  "logs": []
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique execution ID (timestamp-based) |
| `workflow_path` | string | Path to workflow file |
| `workflow` | object | Snapshot of workflow at queue time |
| `execution` | object | Node execution results (see below) |
| `status` | string | `"queued"`, `"running"`, `"completed"`, `"error"` |
| `queued_at` | float | Unix timestamp when queued |
| `started_at` | float | Unix timestamp when started (null if not started) |
| `completed_at` | float | Unix timestamp when finished (null if not finished) |
| `current_step` | int | Number of nodes executed |
| `error` | string | Error message if failed |
| `error_node_id` | string | Node ID that caused failure |
| `error_details` | string | Detailed error information |
| `logs` | array | Log entries from execution |

## Execution Object

Maps node IDs to their execution results:

```json
{
  "node-1": {
    "input": [...],
    "nodeOutput": [...],
    "output": [...],
    "executedAt": "2025-01-27T12:00:00Z",
    "pinned": false
  },
  "node-2": {
    "input": [...],
    "nodeOutput": [...],
    "output": [...],
    "executedAt": "2025-01-27T12:00:01Z",
    "pinned": false
  }
}
```

### Node Execution Entry

| Field | Type | Description |
|-------|------|-------------|
| `input` | array | Array of input items received from upstream |
| `nodeOutput` | array | Raw output from node's execute function |
| `output` | array | Merged input + output, namespaced by node name |
| `executedAt` | string | ISO timestamp of execution |
| `pinned` | boolean | True if used pinned output instead of executing |

### Output Merging

Each output item merges the input item with the node's output, namespaced:

```json
// Input item
{"upstream_field": "value"}

// Node output
{"result": 42}

// Merged output (node.name = "my_node")
{
  "upstream_field": "value",
  "my_node": {"result": 42}
}
```

This allows downstream nodes to access all upstream data via `$.node_name.field`.

## Trigger Node Output

Trigger nodes (scheduled, discord_trigger) output timing information:

```json
// Scheduled trigger output
[{"time": "2025-01-27T12:00:00Z"}]

// Discord trigger output
[{
  "id": "message_id",
  "content": "message text",
  "author": {"id": "...", "username": "..."},
  "channel_id": "...",
  "guild_id": "..."
}]
```

## Log Entries

Execution logs track progress and debugging info:

```json
{
  "timestamp": "2025-01-27T12:00:00Z",
  "level": "info",
  "message": "Starting node execution",
  "node_id": "node-1",
  "data": {...}
}
```

## Storage Location

Executions are stored in a date-based hierarchy:

```
data_dir/local/work/
├── queue/              # Pending executions
├── inprogress/         # Currently running
├── executions/         # Completed executions
│   └── 2025/
│       └── 01/
│           └── 27/
│               └── 120000-workflow-name.json
└── indexes/            # JSONL index files
    └── workflow-name.jsonl
```

## Index File Format

Each workflow has an index file (JSONL) for fast listing:

```json
{"id": "20250127-120000-workflow", "file": "executions/2025/01/27/...", "workflow_path": "workflow.json", "status": "completed", "queued_at": 1706353200, "started_at": 1706353205, "completed_at": 1706353210, "duration_ms": 5000, "error": null}
{"id": "20250127-130000-workflow", "file": "executions/2025/01/27/...", "workflow_path": "workflow.json", "status": "error", "queued_at": 1706356800, "started_at": 1706356805, "completed_at": 1706356810, "duration_ms": 5000, "error": "Connection refused"}
```

## API Endpoints

### List Executions

```
GET /api/executions?limit=100&before=timestamp&workflow_path=path
```

Returns:
```json
{
  "items": [...],
  "has_more": true,
  "last_updated": 1706353210.789
}
```

### Get Single Execution

```
GET /api/execution/{execution_id}
```

Returns the full execution object.

### Get Execution Logs

```
GET /api/executions/{execution_id}/logs
```

Returns:
```json
{
  "logs": [...]
}
```

## Execution Flow Details

### 1. Queue Phase

When a workflow is queued:
```json
{
  "id": "generated-id",
  "workflow_path": "path/to/workflow.json",
  "workflow": {/* snapshot */},
  "execution": {},
  "status": "queued",
  "queued_at": 1706353200.123
}
```

### 2. Start Phase

Worker claims the item:
```json
{
  "status": "running",
  "started_at": 1706353205.456,
  "current_step": 0
}
```

### 3. Node Execution

For each node, the worker:

1. Finds ready nodes (all upstream dependencies satisfied)
2. Evaluates expressions in node.data with upstream output as context
3. Calls node type's execute function
4. Merges output and stores in execution object
5. Increments current_step

### 4. Completion

On success:
```json
{
  "status": "completed",
  "completed_at": 1706353210.789
}
```

On error:
```json
{
  "status": "error",
  "completed_at": 1706353210.789,
  "error": "Connection refused",
  "error_node_id": "node-3",
  "error_details": "..."
}
```

## Expression Context During Execution

When evaluating expressions, `$` contains the current item from upstream:

```javascript
// Upstream output (after merging)
{
  "trigger": {"time": "2025-01-27T12:00:00Z"},
  "fetch_data": {"rows": [...], "count": 42}
}

// Expression can access:
$.trigger.time       // "2025-01-27T12:00:00Z"
$.fetch_data.count   // 42
$.fetch_data.rows[0] // First row
```

## Map vs Array Nodes

### Map Nodes (kind: "map")

Process each input item individually:
- Execute function called once per item
- Output array has same length as input

### Array Nodes (kind: "array")

Process all items at once:
- Execute function receives full array
- Output can be any length

Example:
```
Input: [{a: 1}, {a: 2}, {a: 3}]

Map node: execute called 3 times, one per item
Array node: execute called once with all 3 items
```
