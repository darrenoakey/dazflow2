# dazflow2 Project Rules

## Server Management (CRITICAL)

**NEVER use `./run start` directly.**

Always use `auto` to manage the server:
```bash
auto start dazflow    # Start the server
auto stop dazflow     # Stop the server
auto restart dazflow  # Restart the server
```

## Testing Requirements (CRITICAL)

**Playwright tests MUST pass at these checkpoints:**

1. **Before starting any task** - Run Playwright tests and FIX any failures before proceeding
2. **After completing each task** - Verify no regressions
3. **Before marking work complete** - Final verification

**CRITICAL: Test failures are NOT baselines to record - they MUST be fixed before starting new work.**

### Running Tests

```bash
./run check           # Runs full test suite and quality gates
./run test <target>   # Runs a specific test (e.g., ./run test tests/e2e/)
```

### UI Features Require Playwright Tests

**Every new UI feature MUST have corresponding Playwright tests.**

When adding UI functionality:
- Add E2E tests that verify the feature works
- Tests should cover the main user interactions
- Run Playwright tests before AND after implementation

### Test Failure = Task Failure

If Playwright tests fail at any checkpoint:
- STOP work immediately
- FIX the issue before continuing
- Do NOT commit with failing tests
- Do NOT skip or disable tests

## Architecture Notes

### Trigger vs Non-Trigger Nodes

**CRITICAL:** A node is a "trigger node" only if it has BOTH:
1. No upstream connections (no incoming edges)
2. A `register` function in its node type definition (in `modules/*/nodes.py`)

Trigger nodes (like `scheduled`) are auto-completed with default output `{"time": ...}`.
Non-trigger nodes (like `set`, `transform`) MUST actually execute even with no upstream.

The check is in `src/worker.py:is_trigger_node()`. If nodes aren't executing, check this function.

### Node Type Registration

Each node type is defined in two places:
- **Backend:** `modules/*/nodes.py` - `execute` function + `NODE_TYPES` dict
- **Frontend:** `modules/*/nodes_ui.js` - UI definition with `getProperties()`

The `register` key in NODE_TYPES indicates a trigger node that sets up scheduling.

### Cache Busting

Module UI files (`modules/*/nodes_ui.js`) are loaded with `?v=<server_start_time>` query parameter.
This ensures browsers fetch fresh JS after server restart - no hard refresh needed.

The cache busting is added in `src/api.py` in the `/api/modules` endpoint.

### Python Environment

The `run` script uses `/opt/homebrew/bin/python3.13` explicitly because:
- `auto` daemon may have different PATH than interactive shell
- uvicorn is installed in Python 3.13's site-packages
- Using `#!/usr/bin/env python3` can pick up wrong Python (e.g., Xcode's)

### Config Auto-Discovery

The `src/config.py` auto-discovers the project root based on `__file__` location:
- Default `data_dir` is the project root (parent of `src/`), not the current working directory
- This ensures the server finds workflows regardless of where it's started from
- Critical for `auto` daemon which may have different cwd than the project

### Built-in Agent Event Loop

**CRITICAL:** The built-in agent runs in-process with the server. Node execution MUST use `asyncio.to_thread()`:

```python
# In agent/agent.py _execute_task():
new_execution = await asyncio.to_thread(execute_node, node_id, workflow, execution)
```

Without this, long-running nodes (e.g., `run_command` with 24-hour timeout) block the entire event loop, making the server unresponsive. This caused the server to appear "crashed" when executing workflows with shell commands.

### Git-Based Workflow Versioning

The data directory is automatically initialized as a git repo on startup:
- **src/git.py** - Git operations (init, add, commit, log, show, diff)
- **src/git_ai.py** - AI commit message generation using Claude Agent SDK
- **.gitignore** excludes runtime files: `local/`, `agents.json`, `tags.json`, etc.

**On workflow save:**
1. File is written to disk
2. Staged immediately with `git_add()`
3. Background task generates AI commit message via Claude
4. Commit is created asynchronously (non-blocking)

**History API endpoints:**
- `GET /api/workflow/{path}/history` - Git log for workflow
- `GET /api/workflow/{path}/version/{hash}` - Get workflow at commit
- `POST /api/workflow/{path}/restore/{hash}` - Restore to version (creates new commit)

## Documentation Maintenance (CRITICAL)

**When modifying nodes, workflows, or API endpoints, update the corresponding documentation:**

- `docs/nodes.md` - Node types, properties, examples
- `docs/workflow-format.md` - Workflow JSON structure
- `docs/execution-format.md` - Execution data structure
- `docs/api.md` - API endpoints

**Triggers for documentation updates:**
- Adding/removing/modifying node types in `modules/*/nodes.py`
- Changing node properties or behavior
- Adding/removing API endpoints
- Changing request/response formats
- Modifying workflow or execution structure

**The AI system uses these docs as its knowledge base. Outdated docs = broken AI.**

## AI Integration

The system includes AI-powered features via Claude Agent SDK:

- **Dashboard Chat**: Natural language commands for repository management
- **Editor Chat**: Context-aware commands for workflow editing
- **CLI**: `./run ai <command>` for terminal access

**Key files:**
- `src/ai_brain.py` - Claude integration, session management
- `src/validation.py` - Workflow validation/linting
- `docs/*.md` - Documentation provided to Claude

**AI can:**
- Create/modify/delete workflows
- Create/move folders
- Manage tags and concurrency groups
- Enable/disable workflows
- Execute workflows for testing

**AI cannot:**
- Modify credentials (security)
- Access files outside data directory
- Make permanent external changes

## Editor UI Layout

### Header with Tabs

The workflow editor has a header bar with:
- "← Dashboard" button to return to main view
- Workflow name (without .json extension)
- Save status indicator (Saved/Modified/Saving)
- Tabs: Editor | Executions | History

The Executions tab shows executions filtered to the current workflow only.

### Collapsible Node Categories

Sidebar node categories are collapsible (click to expand/collapse):
- **Expanded by default:** Input, Transform, Logic, Action
- **Collapsed by default:** Pipeline, Output, AI, Discord, System, Database

Each category header shows an arrow (▶/▼) and count of nodes.

### Pipeline Node Styling

Pipeline nodes have a distinctive **teal color scheme** (#14b8a6) to differentiate them from regular nodes (purple #667eea):
- **Sidebar:** Dark teal background with teal icons
- **Canvas:** Teal border and icons; selected state uses brighter teal (#2dd4bf)

This visual distinction makes pipeline nodes immediately identifiable in complex workflows.

### Layout CSS

The editor uses viewport units (`100vw`, `100vh`) and `overflow: hidden` to prevent page scrollbar:
- All container elements must have `overflow: hidden` or `overflow: auto`
- Use `flex: 1` with `min-height: 0` for flex children that should fill remaining space
- Never use `height: 100%` on flex children that need to shrink

### Browser Caching

HTML responses include no-cache headers to ensure fresh content after server restart:
```
Cache-Control: no-cache, no-store, must-revalidate
```

### Debugging Tool

Use `screenshot-editor.js` with Playwright to debug layout issues:
```bash
node screenshot-editor.js
```
This captures dimensions and checks for scrollbar issues against the running server.

## Workflow Settings Tab

The editor has a **Settings** tab (alongside Editor/Executions/History) for workflow-level configuration:

- **Data Directory**: Root directory for file/directory path fields
  - When set, file browsers are restricted to this directory
  - Falls back to home directory (~) if not set
  - Stored in workflow JSON as `settings.dataDirectory`

## File and Directory Path Properties

Nodes can use `file_path` and `directory_path` property types for filesystem paths:

- **`directory_path`**: Shows directory-only browser (no files)
- **`file_path`**: Shows full file browser (directories for navigation, files for selection)

**Features:**
- Toggle between Browse mode (visual tree) and Expression mode (text input)
- Path validation (red indicator if path doesn't exist)
- Hidden files toggle
- Respects workflow's data directory setting for root restriction

**Nodes using path types:**
- `append_to_file`: `filepath` (file_path)
- `run_command`: `workingDirectory` (directory_path)
- `claude_agent`: `cwd` (directory_path)
- Pipeline nodes: `state_root` (directory_path)

## Autosave

The editor has debounced autosave that triggers 1 second after changes:

- **State tracking:** `lastSavedSnapshot` stores JSON of last saved state
- **Status:** `saveStatus` can be 'clean' | 'modified' | 'saving' | 'saved' | 'error'
- **Visual indicator:** `SaveStatusIndicator` component in editor header shows current status

The autosave is triggered via Zustand subscription watching `nodes` and `connections`.

## Workflow Testing Framework

Test workflows by executing them and asserting results (no mocking):

```bash
./run workflow-test                           # Run all tests in workflows/tests/
./run workflow-test tests/my_test.json        # Run specific test
./run workflow-test --test-dir custom-tests   # Custom test directory
```

Test workflows should be named `*_test.json` or `test_*.json`.

**Key files:**
- `src/workflow_testing.py` - Test runner and assertions
- `src/workflow_testing_test.py` - Unit tests for the framework

**Assertion helpers:**
- `node_executed(name)` - Check node ran
- `node_output_equals(name, expected)` - Exact output match
- `node_output_contains(name, key, value?)` - Partial output match
- `node_output_matches(name, predicate)` - Custom predicate
- `no_errors()` - No node errors

## Pipeline Workflow System

State-based idempotent workflows for data pipelines (auto-blog, news-feed patterns).

### Key Files
- **Infrastructure:** `src/pipeline/` (patterns, state_store, staleness, scanner)
- **Nodes:** `modules/pipeline/` (state_trigger, state_read, state_write, state_check, state_list)
- **Design docs:** `docs/spike/` (research, design decisions, examples)

### How It Works

Pipeline nodes use the standard workflow infrastructure but add:
1. **Pattern matching:** `{variable}` syntax extracts entity IDs from paths
2. **State manifests:** `.dazflow/manifests/` tracks code hash, content hash, input hashes
3. **Staleness detection:** Rebuilds if code changes, inputs change, or output missing
4. **Failure tracking:** `.dazflow/failures/` with exponential backoff

### Pipeline Node Types

| Node | Purpose |
|------|---------|
| `state_trigger` | Watch pattern, trigger on new/stale entities |
| `state_read` | Read state content for entity |
| `state_write` | Write with manifest tracking |
| `state_check` | Check existence (for IF logic) |
| `state_list` | List all entities matching pattern |

### Cross-Workflow Triggers

Workflows share state through patterns:
- Workflow A writes to `articles/{slug}.md`
- Workflow B's `state_trigger` watches `articles/{slug}.md`
- When A produces, B finds new work automatically
