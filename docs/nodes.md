# dazflow2 Node Types Reference

This document describes all available node types in dazflow2. Each module contributes node types that can be used in workflows.

## Node Type Basics

Every node has:
- **typeId**: The node type identifier (e.g., `scheduled`, `set`, `postgres_query`)
- **kind**: Either `"map"` (processes each item individually) or `"array"` (processes all items at once)
- **data**: Node-specific configuration fields

### Expression Support

All string fields in node.data support template expressions:
- `"{{$.nodeName.field}}"` - Access upstream node output
- `"prefix {{expression}} suffix"` - String interpolation
- `"{{$.data[0].count * 2}}"` - JavaScript expressions (evaluated with dukpy)

The `$` variable contains the current item from upstream nodes.

### Property Types

Node properties can have the following types:

| Type | Description |
|------|-------------|
| `text` | Single-line text input with expression support |
| `textarea` | Multi-line text input with expression support |
| `number` | Numeric input with optional min/max |
| `select` | Dropdown with predefined options |
| `boolean` | Toggle checkbox |
| `fieldlist` | Key-value pair list |
| `dynamicSelect` | Dropdown with options loaded from backend |
| `directory_path` | Directory picker with browse/expression modes |
| `file_path` | File picker with browse/expression modes |

#### Path Types (`directory_path`, `file_path`)

These types provide a directory tree browser UI with:
- **Browse mode**: Visual file tree for selecting paths
- **Expression mode**: Text input with expression support
- Path validation (red indicator if path doesn't exist)
- Hidden files toggle

When the workflow has a `dataDirectory` setting, the browser is restricted to that directory.

---

## Core Module (`core`)

### `start`
Empty starting point for workflows. Outputs an empty array.

| Property | Type | Description |
|----------|------|-------------|
| (none) | - | No configuration required |

**Kind**: array
**Output**: `[]`

---

### `scheduled`
Trigger node that fires on a schedule. Supports interval or cron modes.

| Property | Type | Description |
|----------|------|-------------|
| `mode` | `"interval"` \| `"cron"` | Schedule mode |
| `interval` | number | Interval value (for interval mode) |
| `unit` | `"seconds"` \| `"minutes"` \| `"hours"` \| `"days"` | Interval unit |
| `cron` | string | Cron expression (for cron mode) |

**Kind**: array
**Trigger**: Yes (auto-fires on schedule when workflow is enabled)
**Output**: `[{"time": "2025-01-27T12:00:00Z"}]`

**Examples**:
```json
// Every 5 minutes
{"mode": "interval", "interval": 5, "unit": "minutes"}

// Every day at 9am (cron)
{"mode": "cron", "cron": "0 9 * * *"}
```

---

### `hardwired`
Outputs static JSON data. Useful for constants or test data.

| Property | Type | Description |
|----------|------|-------------|
| `json` | string | JSON array as string |

**Kind**: array
**Output**: Parsed JSON array

**Example**:
```json
{"json": "[{\"name\": \"Alice\"}, {\"name\": \"Bob\"}]"}
```

---

### `set`
Creates a map/object with configurable fields. Processes each input item.

| Property | Type | Description |
|----------|------|-------------|
| `fields` | array | List of `{name, value}` objects |

**Kind**: map
**Output**: Object with specified fields

**Example**:
```json
{
  "fields": [
    {"name": "timestamp", "value": "{{$.trigger.time}}"},
    {"name": "doubled", "value": "{{$.data.count * 2}}"}
  ]
}
```

---

### `transform`
Evaluates a JavaScript expression and returns the result.

| Property | Type | Description |
|----------|------|-------------|
| `expression` | string | JavaScript expression to evaluate |

**Kind**: map
**Output**: Result of expression evaluation

**Example**:
```json
{"expression": "$.items.filter(i => i.active).map(i => i.name)"}
```

---

### `if`
Conditional filter. Only passes through items where condition is true.

| Property | Type | Description |
|----------|------|-------------|
| `condition` | string | JavaScript boolean expression |

**Kind**: array
**Output**: Filtered array of items

**Example**:
```json
{"condition": "$.data.count > 10"}
```

---

### `http`
Makes HTTP/HTTPS requests to external APIs.

| Property | Type | Description |
|----------|------|-------------|
| `url` | string | Request URL (required) |
| `method` | string | HTTP method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, `OPTIONS` |
| `headers` | array | List of `{name, value}` header objects |
| `body_mode` | string | Body type: `none`, `json`, or `fields` |
| `json_body` | string | Raw JSON body (when `body_mode` is `json`) |
| `body_fields` | array | List of `{name, value}` body fields (when `body_mode` is `fields`) |
| `timeout` | number | Request timeout in seconds (default: 30) |

**Kind**: array
**Output**:
```json
{
  "status": 200,
  "statusText": "OK",
  "headers": {"Content-Type": "application/json", ...},
  "body": {"response": "data"},
  "url": "https://..."
}
```

On error:
```json
{"error": "HTTP 404: Not Found", "status": 404, "statusText": "Not Found", "body": "..."}
```

**Examples**:
```json
// Simple GET
{"url": "https://api.example.com/data", "method": "GET"}

// POST with JSON body
{
  "url": "https://api.example.com/users",
  "method": "POST",
  "body_mode": "json",
  "json_body": "{\"name\": \"Alice\", \"email\": \"alice@example.com\"}"
}

// POST with key-value fields
{
  "url": "https://api.example.com/users",
  "method": "POST",
  "body_mode": "fields",
  "body_fields": [
    {"name": "name", "value": "{{$.input.name}}"},
    {"name": "count", "value": "42"}
  ]
}

// With custom headers
{
  "url": "https://api.example.com/protected",
  "method": "GET",
  "headers": [
    {"name": "Authorization", "value": "Bearer {{$.token}}"},
    {"name": "Accept", "value": "application/json"}
  ]
}
```

---

### `rss`
Fetches RSS feed items. (TODO: Implementation pending)

| Property | Type | Description |
|----------|------|-------------|
| `url` | string | RSS feed URL |

**Kind**: array

---

### `append_to_file`
Appends content to a file.

| Property | Type | Description |
|----------|------|-------------|
| `filepath` | string | Path to file |
| `content` | string | Content to append |

**Kind**: array
**Output**: `[{"written": true, "filepath": "..."}]`

---

## System Module (`system`)

### `dialog`
Shows a macOS dialog box with a message.

| Property | Type | Description |
|----------|------|-------------|
| `message` | string | Dialog message |
| `title` | string | Dialog title |

**Kind**: array
**Output**: `[{"button": "OK"}]`

---

### `prompt`
Shows a prompt dialog with configurable buttons and optional text input.

| Property | Type | Description |
|----------|------|-------------|
| `message` | string | Prompt message |
| `title` | string | Prompt title |
| `buttons` | string | Comma-separated button labels |
| `showInput` | boolean | Show text input field |
| `defaultInput` | string | Default input value |

**Kind**: array
**Output**: `[{"button": "clicked_button", "input": "user_text"}]`

---

### `notification`
Shows a system notification.

| Property | Type | Description |
|----------|------|-------------|
| `message` | string | Notification message |
| `title` | string | Notification title |

**Kind**: array
**Output**: `[{"sent": true}]`

---

### `run_command`
Executes a shell command and captures output.

| Property | Type | Description |
|----------|------|-------------|
| `command` | string | Shell command to execute |
| `workingDirectory` | string | Working directory (optional) |
| `timeout` | number | Timeout in seconds (default: 300) |

**Kind**: array
**Output**: `[{"stdout": "...", "stderr": "...", "returnCode": 0}]`

**Example**:
```json
{
  "command": "ls -la {{$.folder.path}}",
  "workingDirectory": "/tmp",
  "timeout": 60
}
```

---

## Claude Module (`claude`)

### `claude_agent`
Invokes Claude AI as an agent with tool access.

| Property | Type | Description |
|----------|------|-------------|
| `prompt` | string | Prompt to send to Claude |
| `conversation_id` | string | Conversation ID for continuity (optional) |
| `model` | string | Model to use (optional) |
| `allowed_tools` | string | Comma-separated tool names (optional) |
| `system_prompt` | string | System prompt (optional) |
| `permission_mode` | string | Permission mode (optional) |
| `cwd` | string | Working directory for file tools (optional) |

**Kind**: map
**Credential**: None required (uses claude-agent-sdk)
**Output**: `{"response": "Claude's response text", "conversation_id": "..."}`

---

## Discord Module (`discord_nodes`)

### `discord_trigger`
Trigger that fires when new messages arrive in a Discord channel.

| Property | Type | Description |
|----------|------|-------------|
| `server_id` | string | Discord server ID (from dropdown) |
| `channel_id` | string | Discord channel ID (from dropdown) |
| `mode` | string | `"new_messages"`, `"replies"`, or `"new_messages_and_replies"` |

**Kind**: array
**Trigger**: Yes
**Credential**: `discord`
**Output**: `[{"id": "msg_id", "content": "...", "author": {...}, ...}]`

---

### `discord_send`
Sends a message to a Discord channel.

| Property | Type | Description |
|----------|------|-------------|
| `server_id` | string | Discord server ID |
| `channel_id` | string | Discord channel ID |
| `message` | string | Message content |
| `reply_to_id` | string | Message ID to reply to (optional) |

**Kind**: array
**Credential**: `discord`
**Output**: `[{"id": "sent_msg_id", "content": "...", ...}]`

---

## PostgreSQL Module (`postgres`)

### `postgres_query`
Executes a SQL query against a PostgreSQL database.

| Property | Type | Description |
|----------|------|-------------|
| `query` | string | SQL query with `%(name)s` placeholders |
| `params` | array | List of `{name, value}` parameter objects |

**Kind**: array
**Credential**: `postgres`
**Output**: Array of row objects for SELECT, or `[{"affected": N}]` for mutations

**Example**:
```json
{
  "query": "SELECT * FROM users WHERE status = %(status)s",
  "params": [{"name": "status", "value": "active"}]
}
```

---

## Credential Types

### `discord`
Discord bot credentials.

| Field | Description |
|-------|-------------|
| `token` | Bot token (private) |

### `postgres`
PostgreSQL connection credentials.

| Field | Description |
|-------|-------------|
| `host` | Database host |
| `port` | Database port |
| `database` | Database name |
| `user` | Username |
| `password` | Password (private) |

---

## Adding New Nodes to Workflows

When creating or modifying workflows, use this structure:

```json
{
  "nodes": [
    {
      "id": "node-1",
      "typeId": "scheduled",
      "name": "trigger",
      "position": {"x": 100, "y": 100},
      "data": {"mode": "interval", "interval": 5, "unit": "minutes"}
    }
  ],
  "connections": [
    {
      "id": "conn-1",
      "sourceNodeId": "node-1",
      "targetNodeId": "node-2"
    }
  ]
}
```

Node IDs must be unique. The `name` field is used to namespace outputs (e.g., `$.trigger.time`).
