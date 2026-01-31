# Technical Design: Pipeline Workflows

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE WORKFLOW SYSTEM                      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  State Store │────▶│   Scanner    │────▶│  Work Queue  │
│  (filesystem)│     │ (find stale) │     │ (per-entity) │
└──────────────┘     └──────────────┘     └──────────────┘
       │                                         │
       │                                         ▼
       │                              ┌──────────────────┐
       │                              │ Pipeline Worker  │
       │                              │ (execute nodes)  │
       │                              └──────────────────┘
       │                                         │
       ▼                                         ▼
┌──────────────┐                      ┌──────────────────┐
│   Manifest   │◀─────────────────────│   Write State    │
│  (.dazflow/) │                      │ (with code hash) │
└──────────────┘                      └──────────────────┘
```

---

## State Store

### Directory Structure

```
output/                          # stateRoot from workflow config
├── .dazflow/                    # Metadata directory
│   ├── manifests/               # Per-entity manifests
│   │   └── 2026-01-15.json
│   ├── failures/                # Failure tracking
│   │   └── 2026-01-15.json
│   └── index.json              # Entity index for fast scanning
│
├── logs/                        # Stage: logs
│   └── 2026-01-15/
│       ├── claude_logs.txt
│       └── git_commits.txt
│
├── summaries/                   # Stage: summaries
│   └── 2026-01-15.txt
│
├── blogs/                       # Stage: blogs
│   └── 2026-01-15.md
│
└── podcasts/                    # Stage: podcasts
    └── 2026-01-15.md
```

### Manifest Format

`.dazflow/manifests/{entity_id}.json`:

```json
{
  "entity_id": "2026-01-15",
  "states": {
    "logs": {
      "path": "logs/2026-01-15/",
      "is_source": true,
      "discovered_at": "2026-01-15T00:00:00Z"
    },
    "summary": {
      "path": "summaries/2026-01-15.txt",
      "code_hash": "a1b2c3d4",
      "content_hash": "e5f6g7h8",
      "produced_at": "2026-01-15T10:00:00Z",
      "produced_by": "auto-blog#summarize",
      "input_hashes": {
        "logs": "i9j0k1l2"
      }
    },
    "blog": {
      "path": "blogs/2026-01-15.md",
      "code_hash": "m3n4o5p6",
      "content_hash": "q7r8s9t0",
      "produced_at": "2026-01-15T10:05:00Z",
      "produced_by": "auto-blog#blog",
      "input_hashes": {
        "summary": "e5f6g7h8"
      }
    }
  }
}
```

### Failure Tracking

`.dazflow/failures/{entity_id}.json`:

```json
{
  "entity_id": "2026-01-15",
  "failures": {
    "podcast": {
      "error": "Claude API timeout",
      "error_details": "...",
      "attempts": 3,
      "first_failed_at": "2026-01-15T10:10:00Z",
      "last_failed_at": "2026-01-15T11:30:00Z",
      "next_retry_at": "2026-01-15T15:30:00Z"
    }
  }
}
```

---

## State Patterns

### Pattern Syntax

Patterns use `{variable}` placeholders:

```
logs/{date}/           # Matches: logs/2026-01-15/, logs/2026-01-16/
summaries/{date}.txt   # Matches: summaries/2026-01-15.txt
feeds/{feed}/{guid}    # Matches: feeds/hackernews/12345
```

### Entity ID Extraction

The first `{variable}` becomes the primary entity ID. Additional variables become entity attributes:

```python
pattern = "feeds/{feed}/{guid}"
path = "feeds/hackernews/12345"
# Result:
#   entity_id = "hackernews/12345"  # Composite
#   entity.feed = "hackernews"
#   entity.guid = "12345"
```

### Pattern Matching Implementation

```python
import re

def pattern_to_regex(pattern: str) -> tuple[re.Pattern, list[str]]:
    """Convert state pattern to regex with capture groups."""
    variables = []
    regex_parts = []

    for part in re.split(r'(\{[^}]+\})', pattern):
        if part.startswith('{') and part.endswith('}'):
            var_name = part[1:-1]
            variables.append(var_name)
            regex_parts.append(r'([^/]+)')  # Capture non-slash chars
        else:
            regex_parts.append(re.escape(part))

    return re.compile('^' + ''.join(regex_parts) + '$'), variables

def match_pattern(pattern: str, path: str) -> dict | None:
    """Match path against pattern, extract variables."""
    regex, variables = pattern_to_regex(pattern)
    match = regex.match(path)
    if not match:
        return None
    return dict(zip(variables, match.groups()))
```

---

## Pipeline Workflow Schema

```json
{
  "mode": "pipeline",
  "stateRoot": "output/",
  "scanInterval": 60,
  "maxConcurrentEntities": 10,
  "retryPolicy": {
    "maxAttempts": 6,
    "backoffSeconds": [60, 300, 900, 3600, 14400, 86400]
  },
  "stages": [
    {
      "id": "logs",
      "name": "logs",
      "type": "source",
      "pattern": "logs/{date}/",
      "filter": {
        "minFiles": 1
      }
    },
    {
      "id": "summary",
      "name": "summary",
      "type": "transform",
      "input": "logs",
      "pattern": "summaries/{date}.txt",
      "node": {
        "typeId": "claude_agent",
        "data": {
          "prompt": "Summarize the following logs...",
          "input_files": ["{{$.logs.path}}/*.txt"]
        }
      },
      "validation": {
        "minSize": 500
      }
    },
    {
      "id": "blog",
      "name": "blog",
      "type": "transform",
      "input": "summary",
      "pattern": "blogs/{date}.md",
      "node": {
        "typeId": "claude_agent",
        "data": {
          "prompt": "Write a blog post based on this summary..."
        }
      },
      "validation": {
        "minSize": 500
      }
    }
  ]
}
```

### Stage Types

1. **`source`**: External data that arrives (logs, RSS items, uploads)
   - No input stage
   - Only scanned, never produced by pipeline

2. **`transform`**: Produced from input stage
   - Has `input` reference to another stage
   - Has `node` definition for how to produce it

3. **`sink`**: Final output (optional)
   - Like transform but marked as pipeline endpoint
   - Could trigger external actions (S3 upload, notification)

---

## Staleness Detection

### Rules for Staleness

A state is **stale** if ANY of these are true:

1. **Missing**: State file doesn't exist
2. **Code changed**: `manifest.code_hash != current_node_code_hash`
3. **Input changed**: `manifest.input_hashes[input] != current_input_content_hash`
4. **Upstream stale**: Any input stage is stale (recursive)

### Staleness Check Algorithm

```python
def is_stale(entity_id: str, stage_id: str, workflow: dict, manifests: dict) -> bool:
    stage = get_stage(workflow, stage_id)
    manifest = manifests.get(entity_id, {}).get('states', {}).get(stage_id)

    # Rule 1: Missing
    if manifest is None:
        return True

    # Rule 2: Code changed
    current_code_hash = get_code_hash(stage['node']['typeId'])
    if manifest.get('code_hash') != current_code_hash:
        return True

    # Rule 3 & 4: Check inputs
    if 'input' in stage:
        input_stage_id = stage['input']

        # Recursive: input must not be stale
        if is_stale(entity_id, input_stage_id, workflow, manifests):
            return True

        # Input content changed since we produced our output
        input_manifest = manifests.get(entity_id, {}).get('states', {}).get(input_stage_id)
        if input_manifest:
            input_content_hash = input_manifest.get('content_hash')
            our_input_hash = manifest.get('input_hashes', {}).get(input_stage_id)
            if input_content_hash != our_input_hash:
                return True

    return False
```

---

## Pipeline Executor

### Scan and Queue

```python
async def scan_for_work(workflow: dict) -> list[WorkItem]:
    """Find all entities with stale stages."""
    state_root = workflow['stateRoot']
    manifests = load_all_manifests(state_root)
    failures = load_all_failures(state_root)

    work_items = []

    # Find all entities from source stages
    entities = set()
    for stage in workflow['stages']:
        if stage['type'] == 'source':
            for entity_id in scan_pattern(state_root, stage['pattern']):
                entities.add(entity_id)

    # For each entity, find stale stages
    for entity_id in entities:
        for stage in workflow['stages']:
            if stage['type'] == 'source':
                continue  # Sources aren't produced

            if is_stale(entity_id, stage['id'], workflow, manifests):
                # Check if in failure backoff
                if should_skip_due_to_failure(entity_id, stage['id'], failures):
                    continue

                work_items.append(WorkItem(
                    entity_id=entity_id,
                    stage_id=stage['id'],
                    priority=get_priority(entity_id, stage)
                ))

    return work_items
```

### Execute Stage for Entity

```python
async def execute_stage(entity_id: str, stage: dict, workflow: dict) -> Result:
    """Execute a single stage for a single entity."""
    try:
        # Load input state
        input_data = None
        if 'input' in stage:
            input_stage = get_stage(workflow, stage['input'])
            input_path = resolve_pattern(input_stage['pattern'], entity_id)
            input_data = read_state(workflow['stateRoot'], input_path)

        # Build execution context
        context = {
            'entity': {'id': entity_id},
            stage['input']: {'content': input_data, 'path': input_path} if input_data else {}
        }

        # Execute node
        node = stage['node']
        evaluated_data = evaluate_expressions(node['data'], context)
        result = execute_node_type(node['typeId'], evaluated_data)

        # Validate result
        if 'validation' in stage:
            validate_output(result, stage['validation'])

        # Write state
        output_path = resolve_pattern(stage['pattern'], entity_id)
        write_state(workflow['stateRoot'], output_path, result)

        # Update manifest
        update_manifest(entity_id, stage['id'], {
            'path': output_path,
            'code_hash': get_code_hash(node['typeId']),
            'content_hash': hash_content(result),
            'produced_at': now(),
            'input_hashes': {stage['input']: get_content_hash(entity_id, stage['input'])}
        })

        # Clear any failure record
        clear_failure(entity_id, stage['id'])

        return Result.success(output_path)

    except Exception as e:
        record_failure(entity_id, stage['id'], str(e))
        return Result.failure(str(e))
```

---

## Cross-Workflow Triggers

### Pattern: Shared State Namespace

Multiple workflows can share state patterns:

**Workflow A: content-pipeline**
```json
{
  "stages": [
    {"id": "article", "pattern": "articles/{slug}.md", "type": "transform"}
  ]
}
```

**Workflow B: social-publisher**
```json
{
  "stages": [
    {"id": "article", "pattern": "articles/{slug}.md", "type": "source"},
    {"id": "tweet", "pattern": "tweets/{slug}.json", "type": "transform", "input": "article"}
  ]
}
```

Both reference `articles/{slug}.md`. When Workflow A produces an article, Workflow B's scanner finds it as a new source entity.

### Implementation

No special cross-workflow logic needed! Just:
1. Workflows share state patterns
2. Each workflow scans its source patterns
3. New states from other workflows appear as new entities

---

## Code Hash Implementation

### Automatic Hash Calculation

```python
import hashlib
import inspect

def calculate_code_hash(func: Callable) -> str:
    """Calculate hash of function source code."""
    source = inspect.getsource(func)
    return hashlib.md5(source.encode()).hexdigest()[:8]

def get_node_code_hash(type_id: str) -> str:
    """Get code hash for a node type."""
    node_type = NODE_TYPES.get(type_id)
    if not node_type:
        raise ValueError(f"Unknown node type: {type_id}")

    execute_fn = node_type.get('execute')
    if not execute_fn:
        return "static"  # No execute function = no code to hash

    return calculate_code_hash(execute_fn)
```

### Hash Cache and Invalidation

```python
_code_hash_cache: dict[str, str] = {}

def get_code_hash(type_id: str) -> str:
    """Get cached code hash, recalculate if needed."""
    if type_id not in _code_hash_cache:
        _code_hash_cache[type_id] = calculate_node_code_hash(type_id)
    return _code_hash_cache[type_id]

def invalidate_code_hashes():
    """Clear cache (call after hot-reload)."""
    _code_hash_cache.clear()
```

---

## Retry Policy

### Exponential Backoff

```python
DEFAULT_BACKOFF = [60, 300, 900, 3600, 14400, 86400]  # 1m, 5m, 15m, 1h, 4h, 24h

def calculate_next_retry(attempt: int, backoff_schedule: list[int]) -> datetime:
    """Calculate next retry time based on attempt number."""
    if attempt >= len(backoff_schedule):
        # Max retries exceeded - use last backoff * 2
        delay = backoff_schedule[-1] * 2
    else:
        delay = backoff_schedule[attempt]

    return datetime.now() + timedelta(seconds=delay)

def should_retry(failure: dict) -> bool:
    """Check if enough time has passed for retry."""
    next_retry = datetime.fromisoformat(failure['next_retry_at'])
    return datetime.now() >= next_retry
```

### Manual Retry

```python
async def force_retry(entity_id: str, stage_id: str):
    """Clear failure record and queue for immediate retry."""
    clear_failure(entity_id, stage_id)
    # Scanner will pick it up on next scan
```

---

## API Endpoints

### Pipeline Management

```
GET  /api/pipeline/{workflow_path}/status
     -> {"entities": 150, "stale": 5, "failed": 2, "processing": 1}

GET  /api/pipeline/{workflow_path}/entities
     -> [{"id": "2026-01-15", "stages": {"summary": "complete", "blog": "stale"}}]

GET  /api/pipeline/{workflow_path}/entity/{entity_id}
     -> {"id": "...", "manifest": {...}, "failures": {...}}

POST /api/pipeline/{workflow_path}/entity/{entity_id}/retry
     -> {"status": "queued"}

POST /api/pipeline/{workflow_path}/invalidate
     Body: {"stage_id": "summary"}  # Invalidate all summaries (code change)
     -> {"invalidated": 150}
```

---

## Integration with Existing System

### Coexistence

Pipeline workflows coexist with trigger workflows:
- Mode determined by `"mode": "pipeline"` in workflow JSON
- Different executor paths but shared node types
- Same UI editor with mode-specific features

### Node Type Reuse

Existing node types work in pipeline mode:
- `claude_agent` - Perfect for transforms
- `http` - Good for API-based transforms
- `set`, `transform` - Data manipulation

### New Pipeline-Specific Nodes

1. **`state_read`** - Read state file into context
2. **`state_write`** - Write result as state (auto-manifest)
3. **`state_list`** - List entities matching pattern

---

## Example: news-feed as Pipeline

```json
{
  "mode": "pipeline",
  "stateRoot": "data/",
  "stages": [
    {
      "id": "rss_items",
      "type": "source",
      "pattern": "feeds/{feed_id}/{guid}.json"
    },
    {
      "id": "scores",
      "type": "transform",
      "input": "rss_items",
      "pattern": "scores/{feed_id}/{guid}.json",
      "node": {
        "typeId": "http",
        "data": {
          "url": "http://scorer:8080/score",
          "method": "POST",
          "body_mode": "json",
          "json_body": "{\"url\": \"{{$.rss_items.content.link}}\"}"
        }
      }
    },
    {
      "id": "notifications",
      "type": "transform",
      "input": "scores",
      "pattern": "notifications/{feed_id}/{guid}.json",
      "node": {
        "typeId": "if",
        "data": {
          "condition": "{{$.scores.content.score >= 8}}"
        }
      },
      "then": {
        "typeId": "discord_send",
        "data": {
          "channel": "news",
          "message": "{{$.rss_items.content.title}}"
        }
      }
    }
  ]
}
```

---

## Testing Strategy

### Unit Tests

1. Pattern matching and entity extraction
2. Staleness detection logic
3. Retry policy calculations
4. Manifest read/write

### Integration Tests

1. Full pipeline execution with filesystem
2. Code change triggers rebuild
3. Failure and retry flow
4. Cross-workflow state sharing

### Example Workflows

1. **echo-pipeline**: Simple A -> B -> C for testing
2. **auto-blog-pipeline**: Real-world example
3. **news-pipeline**: Multi-entity example
