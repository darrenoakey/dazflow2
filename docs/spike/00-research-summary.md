# Research Summary: Existing Pipeline Patterns

## Overview

This document summarizes the patterns found in three existing projects that implement idempotent, state-based pipelines. Understanding these patterns informs the design of a generalized workflow system.

---

## Project 1: news-feed

**Pipeline:** RSS Discovery -> Scoring -> Discord Publishing

### Architecture Pattern: Queue Tables
- Explicit queue tables for each stage: `PendingEntry`, `ScoredEntry`, `ErrorEntry`
- Entry moves between tables as it progresses
- Presence in table = membership in that stage's queue

### Idempotency
- **GUID-based deduplication** at discovery: `(feed_id, guid)` unique constraint
- Entry is deleted from source queue BEFORE processing begins
- If processing fails, entry moves to error queue (no retry)

### Triggers
- Async workers poll each queue independently
- One item per cycle (prevents starvation)
- Adaptive frequency adjustment based on activity

### Failure Handling
- Failed scoring -> ErrorEntry (no auto-retry)
- Failed Discord send -> entry lost (acceptable for this use case)
- Recovery: manual re-scoring via `update_trained` command

### Key Insight
> Queue tables make state transitions explicit and atomic. Presence = state.

---

## Project 2: auto-blog

**Pipeline:** Logs -> Summary -> Blog -> Podcast -> Audio

### Architecture Pattern: Existence-Based Idempotency
- Each stage checks: does output exist AND meet quality threshold?
- `has_summary()`, `has_final_blog()`, `has_podcast()`, `has_audio()`
- No timestamps, no versions - just "does the file exist?"

### State Storage
- Filesystem is the source of truth
- `output/daily/YYYY/MM/DD/summary.txt` etc.
- Each stage reads previous stage's output file

### Execution Model
- **All entities through Stage 1, then all through Stage 2**, etc.
- NOT per-entity serial (A1->B1->C1, then A2->B2->C2)
- This optimizes for batch processing efficiency

### Dependency Chain
```
has_daily_data() + !has_summary() -> Stage 1
has_summary() + !has_final_blog() -> Stage 2
has_final_blog() + !has_podcast() -> Stage 3
has_podcast() + !has_audio() -> Stage 4
```

### Failure Handling
- Fail-fast: one failure stops entire pipeline
- Idempotent restart: skips already-completed work
- Minimum size thresholds prevent corrupt outputs

### Key Insight
> Filesystem as state store is simple and debuggable. File existence = completion.

---

## Project 3: portfolio

**Pipeline:** GitHub -> AI Discovery -> Image Capture -> Content Generation -> S3 Sync

### Architecture Pattern: Multi-Layer Caching
1. **File-based**: Image exists -> skip generation
2. **Metadata cache**: `github_metadata.json` for AI descriptions
3. **Tracking**: `auto_blog_seen.json` for processed dates
4. **Deployment state**: Git tracks what's been synced

### Git as State Machine
- All generated content in `local/web/` (a git repo)
- `git status --porcelain` = what changed since last sync
- After sync, commit marks state as "deployed"

### Graceful Degradation
- Multi-fallback for image capture: window -> web -> AI-generated
- Failure in one step doesn't break entire pipeline
- Missing images -> continue without them

### Key Insight
> Git provides free change detection with `status --porcelain`. Only sync what changed.

---

## Common Patterns Across All Three

### 1. Idempotency Through State Checking
All three check state before doing work:
- news-feed: unique constraint prevents duplicates
- auto-blog: file existence check
- portfolio: multi-layer cache checks

### 2. Clear Dependency Chains
Each step knows its input and output:
- Input: what must exist before I can run?
- Output: what do I produce when I run?

### 3. Filesystem/Database as Source of Truth
- Not in-memory state that can be lost
- Persistent, observable, debuggable

### 4. Failure Isolation
- One item failing doesn't necessarily kill everything
- State allows retry from where you left off

### 5. No Complex State Machines
- Presence/absence, not status enums
- Binary: done or not done

---

## Differences to Consider

| Aspect | news-feed | auto-blog | portfolio |
|--------|-----------|-----------|-----------|
| State store | Database tables | Filesystem | Filesystem + Git |
| Idempotency | GUID unique constraint | File existence | Multi-layer cache |
| Parallelism | One per worker cycle | All through each stage | Per-step |
| Failure | Move to error queue | Fail-fast | Graceful degradation |
| Retry | Manual only | Re-run skips done | Re-run skips done |
| Cross-workflow | N/A | N/A | N/A |

---

## What None of These Have (The Gap)

1. **Code change detection**: If I update the blog generation code, existing blogs aren't regenerated
2. **Cross-workflow triggers**: Output of workflow 1 doesn't trigger workflow 2
3. **Automatic retry with backoff**: Failed items stay failed until manual intervention
4. **Unified view**: Each pipeline is standalone code, not a composable workflow

These gaps are exactly what the new design should address.
