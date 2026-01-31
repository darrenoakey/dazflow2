# Pipeline Integration Complete

The pipeline system is now fully integrated with the existing dazflow2 workflow infrastructure.

## What Was Built

### New Module: `modules/pipeline/`

Six new node types that work exactly like existing nodes:

| Node Type | Category | Purpose |
|-----------|----------|---------|
| `state_trigger` | Input | Watches for entities matching a pattern, triggers workflow |
| `state_read` | Pipeline | Reads state file content for an entity |
| `state_write` | Pipeline | Writes content to state store with manifest tracking |
| `state_check` | Pipeline | Checks if state exists (for conditional logic) |
| `state_list` | Pipeline | Lists all entities matching a pattern |
| `state_clear_failure` | Pipeline | Clears failure record to allow retry |

### Integration Points

1. **Uses existing module loader** - Auto-discovered from `modules/pipeline/`
2. **Uses existing TaskQueue** - Node execution distributed to agents
3. **Uses existing expression evaluation** - `{{ $.entity_id }}` works
4. **Uses existing visual editor** - Drag-drop like any other node
5. **Uses existing trigger system** - `state_trigger` has `register` function

## How It Works

### State-Based Trigger

Instead of a schedule, `state_trigger` watches for entities:

```
1. Scan filesystem for pattern matches (e.g., "input/{date}/")
2. Check each entity for failures in backoff
3. Return first entity needing work
4. Workflow executes with that entity's context
5. Repeat on scan interval
```

### Change Detection

The `state_write` node tracks:
- **Code hash**: Which version of code produced this
- **Content hash**: What the content hash is
- **Input hashes**: What inputs were used

If any of these change, the state is considered stale.

### Visual Workflow Example

```
[State Trigger]     ─────>    [State Read]     ─────>    [Claude Agent]    ─────>    [State Write]
 pattern:                      pattern:                   prompt: "..."              pattern:
 "input/{date}/"               "input/{date}/data.txt"                               "output/{date}.json"
```

This workflow:
1. Triggers when new input appears
2. Reads the input content
3. Processes it with Claude
4. Writes the result with tracking

### Cross-Workflow Sharing

Two workflows can share state patterns:

**Workflow A**:
```
input/{id}/ -> processed/{id}.txt
```

**Workflow B**:
```
processed/{id}.txt -> final/{id}.json
```

When Workflow A writes to `processed/`, Workflow B's `state_trigger` finds new work.

## Test Coverage

- **Infrastructure tests**: 32 tests (`src/pipeline/pipeline_test.py`)
- **Node tests**: 21 tests (`modules/pipeline/nodes_test.py`)
- **Total**: 53 passing tests

## Usage Example

### Create a Pipeline Workflow in the Editor

1. Drag `State Trigger` node onto canvas
2. Configure pattern: `input/{date}/`
3. Add `State Read` node, connect
4. Configure pattern: `input/{date}/content.txt`
5. Add processing node (Set, Transform, Claude, HTTP, etc.)
6. Add `State Write` node, connect
7. Configure output pattern: `output/{date}.json`
8. Enable workflow

### What Happens

1. Scanner runs every N seconds
2. Finds entity `2026-01-15` in `input/2026-01-15/`
3. Checks if `output/2026-01-15.json` exists and is fresh
4. If stale/missing, triggers workflow with entity context
5. Workflow reads input, processes, writes output
6. Manifest updated with code hash, content hash
7. Next scan: entity is up-to-date, skipped

## Files Created

```
modules/pipeline/
├── __init__.py         # Module init
├── nodes.py            # Node type implementations (6 types)
├── nodes_ui.js         # UI definitions for editor
└── nodes_test.py       # 21 tests

src/pipeline/
├── __init__.py         # Package init
├── patterns.py         # Pattern matching ({variable} syntax)
├── state_store.py      # State storage with manifests
├── staleness.py        # Change detection logic
├── code_hash.py        # Code hash calculation
├── scanner.py          # Work discovery
├── executor.py         # Stage execution
└── pipeline_test.py    # 32 tests
```

## What's Still Not Committed

All spike files are untracked per request. To commit:

```bash
git add modules/pipeline/ src/pipeline/ docs/spike/
git commit -m "Add pipeline workflow system for state-based processing"
```

## Next Steps (If Continuing)

1. **Test with real workflow** - Create an actual pipeline in the UI
2. **Add to docs** - Update `docs/nodes.md` with pipeline node docs
3. **Dashboard integration** - Show pipeline status in UI
4. **Backfill example** - Migrate auto-blog as a test case
