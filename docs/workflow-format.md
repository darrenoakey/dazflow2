# dazflow2 Workflow Format

This document describes the JSON structure of workflow files.

## Overview

Workflows are stored as JSON files in `data_dir/local/work/workflows/`. They can be organized in subdirectories (folders).

## Workflow Structure

```json
{
  "nodes": [...],
  "connections": [...]
}
```

### Nodes Array

Each node represents a processing step in the workflow.

```json
{
  "id": "node-1",
  "typeId": "set",
  "name": "my_mapper",
  "position": {"x": 100, "y": 200},
  "data": {
    "fields": [
      {"name": "output_field", "value": "{{$.input.field}}"}
    ]
  },
  "pinned": false,
  "pinnedOutput": null,
  "agentConfig": {
    "concurrencyGroup": "api-limit",
    "tags": ["gpu-capable"]
  }
}
```

#### Node Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (e.g., "node-1", "node-2") |
| `typeId` | string | Yes | Node type from modules (e.g., "scheduled", "set", "postgres_query") |
| `name` | string | Yes | Display name, also used for output namespace |
| `position` | object | Yes | Canvas position `{x: number, y: number}` |
| `data` | object | Yes | Node-specific configuration |
| `pinned` | boolean | No | If true, use pinnedOutput instead of executing |
| `pinnedOutput` | any | No | Pre-set output value when pinned=true |
| `agentConfig` | object | No | Agent routing configuration |

#### Agent Config

| Field | Type | Description |
|-------|------|-------------|
| `concurrencyGroup` | string | Name of concurrency group to limit parallel execution |
| `tags` | array | Required agent capability tags |

### Connections Array

Connections define data flow between nodes.

```json
{
  "id": "conn-1",
  "sourceNodeId": "node-1",
  "sourceConnectorId": "output",
  "targetNodeId": "node-2",
  "targetConnectorId": "input"
}
```

#### Connection Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier |
| `sourceNodeId` | string | Yes | ID of the source node |
| `sourceConnectorId` | string | No | Output connector name (descriptive) |
| `targetNodeId` | string | Yes | ID of the target node |
| `targetConnectorId` | string | No | Input connector name (descriptive) |

## Expression Syntax

String fields in node.data support JavaScript expressions:

### Template Syntax

```
"{{expression}}"
```

- Single expression: Returns raw value (number, boolean, object)
- Multiple expressions or mixed: Concatenated as string

### Context Variable

The `$` variable contains the current item from upstream nodes:

```javascript
$.nodeName.field        // Access field from node output
$.data[0].items         // Array access
$.count * 2             // Arithmetic
$.items.filter(i => i.active)  // Array methods
```

### Examples

```json
// Access upstream node output
{"value": "{{$.trigger.time}}"}

// String interpolation
{"message": "Hello {{$.user.name}}, you have {{$.data.count}} items"}

// Arithmetic (returns number)
{"doubled": "{{$.input.value * 2}}"}

// Conditional
{"status": "{{$.data.active ? 'enabled' : 'disabled'}}"}

// Array operations
{"names": "{{$.users.map(u => u.name).join(', ')}}"}
```

## File Organization

### Directory Structure

```
workflows/
├── workflow1.json
├── workflow2.json
├── news/
│   ├── rss-aggregator.json
│   └── daily-digest.json
└── monitoring/
    └── health-check.json
```

### Naming Conventions

- Use lowercase with hyphens: `my-workflow.json`
- Always include `.json` extension
- Folder names follow same convention

### Moving Workflows

Use the `/api/workflow/{path}/move` endpoint:
```json
POST /api/workflow/old-name.json/move
{"destination": "folder/new-name.json"}
```

## Enabled State

Workflows can be enabled or disabled:

- **Enabled**: Triggers fire automatically (scheduled, discord_trigger, etc.)
- **Disabled**: Triggers don't fire, but manual execution still works

Enabled state is stored separately in `enabled.json`, not in the workflow file.

## Version Control

Workflows are version-controlled with git:

- Every save creates a commit with AI-generated message
- View history: `GET /api/workflow/{path}/history`
- Restore version: `POST /api/workflow/{path}/restore/{hash}`

## Validation Rules

A valid workflow must have:

1. **Unique node IDs**: No duplicate `id` values
2. **Valid typeIds**: All `typeId` values must exist in registered modules
3. **Valid connections**: `sourceNodeId` and `targetNodeId` must reference existing nodes
4. **No cycles**: Connections must form a DAG (directed acyclic graph)
5. **Valid JSON**: Proper JSON syntax

## Complete Example

```json
{
  "nodes": [
    {
      "id": "node-1",
      "typeId": "scheduled",
      "name": "trigger",
      "position": {"x": 100, "y": 100},
      "data": {
        "mode": "interval",
        "interval": 30,
        "unit": "minutes"
      }
    },
    {
      "id": "node-2",
      "typeId": "postgres_query",
      "name": "fetch_data",
      "position": {"x": 300, "y": 100},
      "data": {
        "query": "SELECT * FROM metrics WHERE created_at > NOW() - INTERVAL '1 hour'",
        "params": []
      }
    },
    {
      "id": "node-3",
      "typeId": "if",
      "name": "filter_high",
      "position": {"x": 500, "y": 100},
      "data": {
        "condition": "$.fetch_data.value > 100"
      }
    },
    {
      "id": "node-4",
      "typeId": "notification",
      "name": "alert",
      "position": {"x": 700, "y": 100},
      "data": {
        "title": "High Value Alert",
        "message": "Value {{$.fetch_data.value}} exceeds threshold"
      }
    }
  ],
  "connections": [
    {
      "id": "conn-1",
      "sourceNodeId": "node-1",
      "targetNodeId": "node-2"
    },
    {
      "id": "conn-2",
      "sourceNodeId": "node-2",
      "targetNodeId": "node-3"
    },
    {
      "id": "conn-3",
      "sourceNodeId": "node-3",
      "targetNodeId": "node-4"
    }
  ]
}
```
