# Questions and Decisions

## Questions Raised During Design

### Q1: Should pipeline mode be a separate workflow type or an attribute?

**Decision: Attribute**
- `"mode": "pipeline"` in workflow JSON
- Same file format, same editor
- Mode determines which executor runs it

**Rationale**: Minimizes code changes, reuses existing infrastructure

---

### Q2: How to represent the dependency chain in the UI?

**Decision: Stage-based view (not node-based)**
- Pipeline workflows show stages linearly: Source -> Transform -> Transform -> Sink
- Each stage can expand to show its node configuration
- Different from DAG view of trigger workflows

**Rationale**: Pipeline workflows are inherently linear per-entity; DAG view would be confusing

---

### Q3: What's the entity ID format for multi-variable patterns?

**Decision: Slash-joined composite**
```
Pattern: feeds/{feed}/{guid}
Entity ID: "hackernews/12345"
```

**Rationale**:
- Simple, filesystem-friendly
- Maintains hierarchy in entity IDs
- Easy to split back into components

---

### Q4: Should pipeline execution reuse the existing worker/task queue?

**Decision: New pipeline worker, reuse task queue for node execution**
- PipelineWorker handles scanning and entity queuing
- Individual node executions still go through TaskQueue
- Allows agents to execute pipeline nodes

**Rationale**: Reuses agent execution infrastructure while adding pipeline-specific scanning

---

### Q5: How to handle stages that produce multiple outputs?

**Example**: RSS stage that produces one file per item

**Decision: Entity multiplication**
- Source stage can discover multiple entities
- Transform stages are 1:1 (one input entity -> one output entity)
- For 1:N transforms, use intermediate stage that lists items, then another that processes each

**Rationale**: Keeps model simple; 1:1 transforms are predictable

---

### Q6: What happens to downstream stages when an upstream stage fails?

**Decision: Downstream stages remain stale (not error)**
- Failed stage has error in failure record
- Downstream stages show as "blocked" (waiting on upstream)
- When upstream succeeds, downstream becomes "ready"

**Rationale**: Distinguishes "can't run" from "tried and failed"

---

### Q7: How to invalidate all outputs of a stage (force rebuild)?

**Decision: API endpoint + manifest clearing**
- `POST /api/pipeline/{workflow}/invalidate?stage={stage_id}`
- Clears code_hash from all manifests for that stage
- Next scan sees all as stale

**Rationale**: Simple, uses existing staleness detection

---

### Q8: Should manifests be per-entity or per-stage?

**Decision: Per-entity**
- One manifest file per entity ID
- Contains all stages for that entity
- Easier to see complete entity state

**Rationale**: Entity is the primary unit of work; want all info in one place

---

### Q9: How to handle "source" stages that need periodic rescanning?

**Example**: RSS feed that may have new items

**Decision: Source scan on every scan interval**
- Sources are always scanned (unlike transforms which check staleness)
- New entities discovered automatically
- Source stage filter determines what counts as "present"

**Rationale**: Can't know if new source entities exist without scanning

---

### Q10: Should state files be the actual content or references?

**Decision: Actual content (small files) or reference + large file storage (large files)**
- States under 1MB: stored directly
- States over 1MB: stored in `large/` directory with reference in manifest
- Node execution can work with either

**Rationale**: Balance simplicity with practicality for large files

---

## Implementation Decisions

### D1: Start with filesystem, not database
- Filesystem is simpler to implement and debug
- Matches auto-blog pattern
- Can add database backend later

### D2: Manifests in `.dazflow/` subdirectory
- Keeps metadata separate from state files
- Easy to gitignore if desired
- Clear separation of concerns

### D3: Code hash calculated from function source
- Uses `inspect.getsource()`
- Automatic, no manual versioning
- Recalculated on module reload

### D4: Backoff schedule is workflow-configurable
- Default: [60, 300, 900, 3600, 14400, 86400]
- Can be overridden per-workflow
- Allows quick retry for known-flaky stages

### D5: Pipeline scanner runs in main process
- Not distributed to agents
- Agents only execute individual node tasks
- Keeps coordination simple

### D6: Use existing expression evaluation
- `{{$.entity.id}}` etc.
- Reuse `evaluate_template()` from executor.py
- Add entity context to evaluation

---

## Open Questions (To Resolve During Spike)

### O1: Performance of full manifest scan
- If 10,000 entities, scanning all manifests could be slow
- May need index file or caching
- **Spike will reveal**: Start simple, optimize if needed

### O2: Concurrent entity execution ordering
- If entity A and B both need work, which runs first?
- Priority based on: age? stage? random?
- **Spike decision**: Oldest entity first (FIFO)

### O3: Hot reload of code hash
- When node code changes, how to detect?
- Currently: restart server
- **Future**: File watching + invalidation

### O4: UI for pipeline status
- Need new components for:
  - Entity list with stage status
  - Failure details and retry buttons
  - Invalidation controls
- **Spike scope**: API only, no UI

---

## Rejected Alternatives

### R1: Event sourcing for state changes
- Considered: Append-only log of state changes
- Rejected: Too complex for initial implementation
- May revisit for audit/debugging features

### R2: Database-first state store
- Considered: SQLite/PostgreSQL for states
- Rejected: Filesystem simpler, more debuggable
- Keep as future option

### R3: Per-stage workers
- Considered: Separate worker for each stage type
- Rejected: Over-engineered for initial needs
- Single pipeline worker is sufficient

### R4: Distributed locking for entity processing
- Considered: Lock entity during processing
- Rejected: File-based locking sufficient for single-process
- Keep simple until proven insufficient
