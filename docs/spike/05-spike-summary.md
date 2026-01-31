# Pipeline Workflow Spike Summary

## What Was Built

### Core Infrastructure (Working, Tested)

1. **Pattern Matching** (`src/pipeline/patterns.py`)
   - `{variable}` syntax for state patterns
   - Pattern to regex conversion
   - Entity ID extraction from paths
   - Filesystem scanning for pattern matches
   - 12 passing tests

2. **State Store** (`src/pipeline/state_store.py`)
   - Filesystem-based state storage
   - Manifest tracking (code hash, content hash, input hashes)
   - Failure recording with exponential backoff
   - Source registration for external data
   - 11 passing tests

3. **Staleness Detection** (`src/pipeline/staleness.py`)
   - Missing state detection
   - Code change detection
   - Input change detection
   - Failure backoff checking
   - 4 passing tests

4. **Work Scanner** (`src/pipeline/scanner.py`)
   - Discovers entities from source patterns
   - Finds stale stages needing work
   - Respects failure backoff
   - Priority-based work ordering
   - 3 passing tests

5. **Code Hash** (`src/pipeline/code_hash.py`)
   - Calculates hash from function source
   - Cached for performance
   - 2 passing tests

6. **Stage Executor** (`src/pipeline/executor.py`)
   - Executes individual stages
   - Loads input data, evaluates expressions
   - Writes output with manifest update
   - Records failures on error

**Total: 32 passing tests**

### Design Documents

- `00-research-summary.md` - Analysis of news-feed, auto-blog, portfolio patterns
- `01-design-proposal.md` - Problem statement and design options
- `02-technical-design.md` - Detailed technical specification
- `03-questions-and-decisions.md` - Design decisions and rationale
- `04-demo-walkthrough.md` - Usage examples

### Example Workflows

- `examples/auto-blog-pipeline.json` - Daily logs to blog/podcast/audio
- `examples/news-pipeline.json` - RSS to scoring to Discord
- `examples/echo-pipeline.json` - Simple test pipeline

---

## What Works

### Idempotent State Processing
```python
# First run: finds missing work
work = scan_for_work(store, workflow)  # [entity1, entity2]

# After processing entity1...
work = scan_for_work(store, workflow)  # [entity2] - entity1 done
```

### Code Change Detection
```python
# State produced with code hash "abc123"
# Code changes, new hash is "xyz999"
is_stale(store, "entity1", "stage", "pattern", "xyz999")
# -> StalenessResult(is_stale=True, reason=CODE_CHANGED)
```

### Input Change Detection
```python
# Update source file
# Staleness check sees input_hash mismatch
is_stale(store, "entity1", "stage", "pattern", code_hash, input_stage="source", input_pattern="...")
# -> StalenessResult(is_stale=True, reason=INPUT_CHANGED)
```

### Failure with Backoff
```python
store.record_failure("entity1", "pattern", "Error message")
store.should_retry("entity1", "pattern")  # False initially
# After backoff period...
store.should_retry("entity1", "pattern")  # True
```

### Cross-Workflow State Sharing
Workflows share state through common patterns - no special configuration needed.

---

## What's Missing (Next Steps)

### Immediate Needs

1. **Pipeline Worker**
   - Background service running scan/execute loop
   - Configurable scan interval
   - Concurrent entity processing

2. **Integration with Existing Executor**
   - Wire up actual node execution
   - Expression evaluation with entity context
   - Credential handling

3. **API Endpoints**
   - `GET /api/pipeline/{path}/status` - Overview
   - `GET /api/pipeline/{path}/entities` - List with states
   - `POST /api/pipeline/{path}/invalidate` - Force rebuild
   - `POST /api/pipeline/{path}/retry` - Clear failure, retry

4. **CLI Commands**
   - `./run pipeline status <workflow>`
   - `./run pipeline run <workflow>` - Manual scan/execute
   - `./run pipeline invalidate <workflow> <stage>`

### Future Enhancements

1. **UI Components**
   - Pipeline status dashboard
   - Entity state browser
   - Manual rerun buttons
   - Failure details view

2. **Advanced Features**
   - Partial rebuild (only affected stages)
   - Dependency visualization
   - Metrics/observability
   - Webhook triggers for source changes

3. **Performance**
   - Index for faster entity scanning
   - Batch manifest updates
   - Parallel entity processing

---

## Key Design Decisions

1. **Filesystem State Store** - Simple, debuggable, git-friendly
2. **Manifest Sidecar Files** - Keep metadata separate from data
3. **Code Hash from Source** - Automatic, no manual versioning
4. **Pattern-Based Sharing** - Cross-workflow through shared patterns
5. **Exponential Backoff** - Configurable per-workflow

---

## Validation Notes

### What Went Well
- Pattern matching works cleanly
- State store abstraction is clean
- Staleness detection logic is correct
- Test coverage is comprehensive

### Potential Issues Discovered
- Directory patterns need special handling for content hash
- Input hash tracking requires careful coordination
- Entity ID format for multi-variable patterns needs documentation

### Open Questions
1. Should manifests be versioned with git?
2. How to handle very large state files?
3. Should there be a "manual hold" status for stages?

---

## Conclusion

The spike demonstrates the core concepts work:
- Idempotent, state-based processing
- Code change detection
- Input change detection
- Failure handling with backoff
- Cross-workflow state sharing

The foundation is solid for building the full pipeline system. Next step would be integrating with the existing dazflow2 worker and adding API/CLI support.
