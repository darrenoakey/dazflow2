# Demo Walkthrough: Pipeline Workflows

This document demonstrates how the pipeline workflow system works using a simple example.

## The Echo Pipeline

The `echo-pipeline.json` is a minimal example:

```
input/{id}.txt -> transformed/{id}.txt -> output/{id}.json
```

1. **Source stage**: Watches for `.txt` files in `input/`
2. **Transform stage**: Converts text to uppercase
3. **Output stage**: Wraps result in JSON with metadata

## Step-by-Step Demo

### 1. Create Source Data

```bash
# Create the state store root
mkdir -p test_output/input

# Add some source files
echo "hello world" > test_output/input/001.txt
echo "pipeline test" > test_output/input/002.txt
```

### 2. Initialize State Store

```python
from src.pipeline import StateStore

store = StateStore("test_output")
store.init()

# Register sources
store.register_source("input/{id}.txt", "001")
store.register_source("input/{id}.txt", "002")
```

### 3. Scan for Work

```python
from src.pipeline.scanner import scan_for_work
import json

workflow = json.load(open("docs/spike/examples/echo-pipeline.json"))
work = scan_for_work(store, workflow)

print(f"Found {len(work)} work items:")
for item in work:
    print(f"  - Entity {item.entity_id}: stage {item.stage_id}")
```

Output:
```
Found 2 work items:
  - Entity 001: stage transformed
  - Entity 002: stage transformed
```

### 4. Execute Work

```python
from src.pipeline.executor import execute_stage

# Get the first work item
item = work[0]
stage = next(s for s in workflow["stages"] if s["id"] == item.stage_id)

# Execute it
result = await execute_stage(store, item.entity_id, stage, workflow)
print(f"Result: {result}")
```

Output:
```
Result: ExecutionResult(success=True, output_path='transformed/001.txt', ...)
```

### 5. Verify State

```python
# Check the manifest
manifest = store.get_manifest("001")
print(f"States for entity 001:")
for pattern, info in manifest.states.items():
    print(f"  {pattern}: code_hash={info.code_hash}")
```

Output:
```
States for entity 001:
  input/{id}.txt: code_hash=source00
  transformed/{id}.txt: code_hash=abc12345
```

### 6. Rescan (Idempotent!)

```python
# Scan again
work = scan_for_work(store, workflow)
print(f"Found {len(work)} work items")
```

Output:
```
Found 1 work items  # Only one left (entity 002 still needs transform)
```

### 7. Code Change Detection

If we modify the transform node's code, existing outputs become stale:

```python
from src.pipeline.staleness import is_stale

# Simulate code change by using different hash
result = is_stale(
    store,
    entity_id="001",
    stage_id="transformed",
    stage_pattern="transformed/{id}.txt",
    current_code_hash="xyz99999",  # Changed!
)

print(f"Is stale: {result.is_stale}")
print(f"Reason: {result.reason.value}")
print(f"Details: {result.details}")
```

Output:
```
Is stale: True
Reason: code_changed
Details: Code hash changed: abc12345 -> xyz99999
```

### 8. Failure Handling

```python
# Simulate a failure
store.record_failure(
    entity_id="003",
    stage_pattern="transformed/{id}.txt",
    error="Connection timeout",
)

# Check if we should retry
should_retry = store.should_retry("003", "transformed/{id}.txt")
print(f"Should retry: {should_retry}")  # False initially

# After backoff period passes...
# should_retry becomes True
```

---

## Cross-Workflow Example

Two workflows sharing state:

**Workflow A: content-creator**
```json
{
  "stages": [
    {"id": "draft", "type": "source", "pattern": "drafts/{slug}.md"},
    {"id": "article", "type": "transform", "input": "draft", "pattern": "articles/{slug}.md"}
  ]
}
```

**Workflow B: social-publisher**
```json
{
  "stages": [
    {"id": "article", "type": "source", "pattern": "articles/{slug}.md"},
    {"id": "tweet", "type": "transform", "input": "article", "pattern": "tweets/{slug}.json"}
  ]
}
```

When Workflow A produces `articles/my-post.md`:
1. Workflow B's scanner finds it as a new source entity
2. Workflow B queues work for `tweets/my-post.json`
3. No special configuration needed - just shared patterns

---

## Key Benefits Demonstrated

1. **Idempotent**: Running scan/execute multiple times is safe
2. **State-aware**: Only processes what needs processing
3. **Code-change detection**: Hash-based rebuild triggers
4. **Failure resilience**: Exponential backoff, clear failure tracking
5. **Cross-workflow**: Natural state sharing through patterns
6. **Observable**: Manifests show complete entity history

---

## What's Not Yet Implemented

This spike has the core infrastructure but missing:

1. **Pipeline worker**: Background service running scan/execute loop
2. **API endpoints**: REST API for pipeline status/control
3. **UI components**: Visualize pipeline state, trigger rebuilds
4. **Integration with existing nodes**: Wire up actual node execution
5. **CLI commands**: `./run pipeline status`, `./run pipeline run`, etc.

These would be the next steps to make this production-ready.
