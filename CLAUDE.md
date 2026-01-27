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
