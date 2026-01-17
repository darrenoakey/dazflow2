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
