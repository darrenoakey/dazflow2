# Design Proposal: State-Based Pipeline Workflows

## The Problem

Current dazflow2 workflows are **trigger-based**: something happens (schedule fires, webhook received), workflow runs once, done.

The user wants **state-based** workflows:
- A -> B -> C -> D where each step is idempotent
- Existence of A triggers production of B
- If step C fails, retry with backoff until it succeeds
- If code for step C changes, regenerate all Cs (and downstream Ds)
- Cross-workflow triggers: C in workflow 1 also triggers workflow 2's C -> E -> F

This is essentially a **build system** pattern (like Make, Airflow, Luigi) applied to data pipelines.

---

## Core Concepts

### State vs Events

**Current model (Event-driven):**
```
[Schedule fires] --> [Run workflow once] --> [Done]
                           |
                      One execution
```

**Proposed model (State-driven):**
```
[State appears] --> [Check: output exists?] --> [No: produce it] --> [Next stage]
     |                      |
     |                      +-- [Yes: skip]
     |
  Continuous scanning for new/missing states
```

### Key Principles

1. **States, not events**: The existence of something triggers work, not the arrival of an event
2. **Idempotent by design**: Running again produces the same result (or skips if already done)
3. **Dependency-aware**: Know what must exist before running, what is produced
4. **Code-aware**: Track code versions, rebuild when code changes
5. **Retry-aware**: Failed states retry with exponential backoff

---

## Proposed Design: "Pipeline Mode" Workflows

A workflow can operate in two modes:
1. **Trigger mode** (current): Fires on event, runs once
2. **Pipeline mode** (new): Continuously processes entities through stages

### Pipeline Workflow Structure

```json
{
  "mode": "pipeline",
  "stateStore": "filesystem",  // or "database"
  "stateRoot": "output/",      // base path for states
  "scanInterval": 60,          // seconds between scans
  "nodes": [...]
}
```

### State Producer/Consumer Nodes

New node types that understand state:

**`state_scan` (Trigger node)**
- Scans for entities matching a pattern
- Produces list of entity IDs that need processing
- Pattern: `logs/{date}` finds all dates with logs

**`state_check` (Gate node)**
- Checks if state exists for current entity
- Passes through if exists, blocks if not

**`state_write` (Sink node)**
- Writes output to state store
- Records code hash for invalidation

### Entity Context

Unlike current workflows where items flow through, pipeline workflows have an **entity context**:

```javascript
$.entity      // The current entity being processed
$.entity.id   // e.g., "2026-01-15"
$.entity.path // e.g., "logs/2026-01-15"
```

---

## Design Option A: Scan-and-Process Model

The simplest approach: periodically scan for work.

### How It Works

1. **Scanner** finds all entities matching input pattern
2. For each entity, check if output exists
3. If output missing (or stale), queue for processing
4. Worker executes node, writes output

### Example: auto-blog as Pipeline Workflow

```json
{
  "mode": "pipeline",
  "stateRoot": "output/",
  "nodes": [
    {
      "id": "scan-logs",
      "typeId": "state_scan",
      "name": "dates",
      "data": {
        "pattern": "daily/{date}/",
        "filter": "hasFiles"
      }
    },
    {
      "id": "summarize",
      "typeId": "state_transform",
      "name": "summary",
      "data": {
        "input": "{{$.dates.path}}/*.txt",
        "output": "{{$.dates.path}}/summary.txt",
        "transform": "claude_summarize",
        "minSize": 500
      }
    },
    {
      "id": "blog",
      "typeId": "state_transform",
      "name": "blog",
      "data": {
        "input": "{{$.summary.path}}",
        "output": "final/{{$.dates.id}}-daily-digest.md",
        "transform": "claude_blog",
        "minSize": 500
      }
    }
  ],
  "connections": [
    {"sourceNodeId": "scan-logs", "targetNodeId": "summarize"},
    {"sourceNodeId": "summarize", "targetNodeId": "blog"}
  ]
}
```

### Execution Flow

```
Every 60 seconds:
  1. Run state_scan: Find all dates with logs
  2. For each date:
     - Does summary exist? No -> run summarize
     - Does blog exist? No -> run blog
  3. Sleep until next scan
```

### Pros
- Simple to understand
- Works with existing workflow UI
- Minimal changes to core

### Cons
- Polling-based (not event-driven)
- Full scan every interval (could be slow)
- No cross-workflow triggers

---

## Design Option B: State Events Model

More sophisticated: state changes emit events.

### How It Works

1. **State store** emits events when state is written
2. Event triggers downstream workflows
3. Event contains: entity ID, state type, code hash

### State Store Schema

```sql
CREATE TABLE states (
  entity_id TEXT,        -- e.g., "2026-01-15"
  state_type TEXT,       -- e.g., "summary"
  code_hash TEXT,        -- hash of producing node's code
  content_hash TEXT,     -- hash of actual content
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (entity_id, state_type)
);

CREATE TABLE state_failures (
  entity_id TEXT,
  state_type TEXT,
  error TEXT,
  attempt INT,
  next_retry_at TIMESTAMP,
  PRIMARY KEY (entity_id, state_type)
);
```

### Event-Driven Triggers

```json
{
  "id": "on-summary-created",
  "typeId": "state_trigger",
  "data": {
    "stateType": "summary",
    "filter": "$.codeHash == currentCodeHash"  // only new/updated
  }
}
```

### Cross-Workflow Triggers

Workflow 1 writes state "article":
```json
{"typeId": "state_write", "data": {"stateType": "article"}}
```

Workflow 2 triggers on "article":
```json
{"typeId": "state_trigger", "data": {"stateType": "article"}}
```

Now Workflow 2 fires whenever Workflow 1 produces an article.

### Pros
- Event-driven (responsive)
- Cross-workflow triggers built-in
- Code invalidation natural

### Cons
- More complex implementation
- Requires state store (database)
- Event ordering/delivery concerns

---

## Design Option C: Hybrid Model (Recommended)

Combine the simplicity of Option A with the power of Option B.

### Core Ideas

1. **Filesystem state store** (simple, debuggable)
2. **Code hash tracking** via sidecar files or manifest
3. **Scan-based discovery** with smart caching
4. **Cross-workflow via shared state patterns**

### State Manifest

Each state directory has a `.manifest.json`:

```json
{
  "states": {
    "summary.txt": {
      "codeHash": "abc123",
      "contentHash": "def456",
      "producedAt": "2026-01-15T10:00:00Z",
      "producedBy": "workflow/auto-blog.json#summarize"
    }
  }
}
```

### Code Hash Calculation

Node types register their code hash:

```python
NODE_TYPES = {
    "claude_summarize": {
        "execute": execute_summarize,
        "code_hash": hashlib.md5(inspect.getsource(execute_summarize)).hexdigest()[:8]
    }
}
```

When code changes, hash changes, existing outputs become stale.

### Stale Detection

State is stale if:
1. Output doesn't exist
2. Output's code hash != current node's code hash
3. Any input state is newer than output
4. Output in failure state past retry time

### Cross-Workflow via State Patterns

Multiple workflows can reference same state pattern:

**Workflow: auto-blog**
```
logs/{date} -> summary/{date} -> blog/{date}
```

**Workflow: daily-podcast**
```
blog/{date} -> podcast/{date} -> audio/{date}
```

Both workflows share `blog/{date}` state. When auto-blog produces a blog, daily-podcast's scanner finds new work.

### Retry with Backoff

```python
BACKOFF_SCHEDULE = [60, 300, 900, 3600, 14400, 86400]  # 1m, 5m, 15m, 1h, 4h, 24h

def should_retry(failure):
    if failure.attempt >= len(BACKOFF_SCHEDULE):
        return False  # Max retries exceeded
    delay = BACKOFF_SCHEDULE[failure.attempt]
    return now() >= failure.failed_at + delay
```

---

## Implementation Plan

### Phase 1: Core Infrastructure

1. **State store abstraction** (`src/state_store.py`)
   - `exists(pattern, entity_id)` -> bool
   - `read(pattern, entity_id)` -> content
   - `write(pattern, entity_id, content, code_hash)`
   - `list_entities(pattern)` -> [entity_id]
   - `get_manifest(entity_id)` -> manifest dict

2. **Code hash registry** (`src/code_hashes.py`)
   - Track hash for each node type
   - Detect changes on module reload

3. **Staleness checker** (`src/staleness.py`)
   - Given entity + node, is output stale?
   - Check existence, code hash, input freshness

### Phase 2: New Node Types

4. **`state_scan`** - Find entities needing work
5. **`state_read`** - Read state into execution context
6. **`state_write`** - Write output as state
7. **`state_gate`** - Check if state exists, block if not

### Phase 3: Pipeline Executor

8. **Pipeline mode worker** (`src/pipeline_worker.py`)
   - Scan for stale states
   - Queue per-entity executions
   - Track failures and retry schedule

### Phase 4: UI Integration

9. **Pipeline workflow editor** mode
10. **State browser** - view all states, staleness
11. **Manual rerun** - invalidate and regenerate

---

## Questions to Resolve

1. **State pattern syntax**: How to express `logs/{date}` patterns?
2. **Entity ID extraction**: How to extract `date` from path?
3. **Partial failures**: If step 3/5 fails, what happens to 4-5?
4. **Concurrency**: Can multiple entities process in parallel?
5. **State format**: Files? Database? Both?

---

## Answered Assumptions (Self-Guessed)

1. **State patterns**: Use glob-like syntax `{var}` for entity extraction
2. **Entity ID**: Variable in pattern becomes entity ID (e.g., `{date}` -> "2026-01-15")
3. **Partial failures**: Entity stuck at failed step, downstream doesn't run
4. **Concurrency**: Yes, parallel by default (configurable)
5. **State format**: Start with filesystem, add database option later

---

## Next Steps

1. Create spike implementation of Option C (Hybrid)
2. Re-implement auto-blog as pipeline workflow
3. Validate design with real usage
4. Iterate based on findings
