"""Pipeline scanner for discovering work.

Scans state store to find entities that need processing,
based on staleness and failure backoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .code_hash import get_code_hash
from .staleness import find_ready_stages

if TYPE_CHECKING:
    from .state_store import StateStore


@dataclass
class WorkItem:
    """A unit of work to be processed."""

    entity_id: str
    stage_id: str
    stage_pattern: str
    priority: int = 0  # Lower = higher priority

    def __lt__(self, other: "WorkItem") -> bool:
        """Compare for sorting (by priority, then entity_id)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.entity_id < other.entity_id


def scan_for_work(
    store: "StateStore",
    workflow: dict,
    max_items: int | None = None,
) -> list[WorkItem]:
    """Scan for all entities that need work.

    Args:
        store: State store instance
        workflow: Pipeline workflow definition
        max_items: Maximum number of work items to return

    Returns:
        List of WorkItem objects sorted by priority
    """
    stages = workflow.get("stages", [])
    if not stages:
        return []

    # Get code hashes for all node types used
    code_hashes = _get_code_hashes_for_workflow(stages)

    # Find all source stages
    source_patterns = [s["pattern"] for s in stages if s.get("type") == "source"]

    # Discover all entities from sources
    entities: set[str] = set()
    for pattern in source_patterns:
        for entity_id in store.list_entities(pattern):
            entities.add(entity_id)

    # For each entity, find ready stages
    work_items: list[WorkItem] = []
    for entity_id in entities:
        ready = find_ready_stages(store, entity_id, stages, code_hashes)
        for stage_id in ready:
            stage = _get_stage(stages, stage_id)
            if stage:
                work_items.append(
                    WorkItem(
                        entity_id=entity_id,
                        stage_id=stage_id,
                        stage_pattern=stage["pattern"],
                        priority=_calculate_priority(entity_id, stage),
                    )
                )

    # Sort by priority
    work_items.sort()

    # Limit if requested
    if max_items is not None:
        work_items = work_items[:max_items]

    return work_items


def count_work(store: "StateStore", workflow: dict) -> dict[str, int]:
    """Count work items by status.

    Args:
        store: State store instance
        workflow: Pipeline workflow definition

    Returns:
        Dict with counts: total_entities, stale, ready, failed, complete
    """
    stages = workflow.get("stages", [])
    if not stages:
        return {"total_entities": 0, "stale": 0, "ready": 0, "failed": 0, "complete": 0}

    code_hashes = _get_code_hashes_for_workflow(stages)

    # Find all source stages
    source_patterns = [s["pattern"] for s in stages if s.get("type") == "source"]

    # Discover all entities
    entities: set[str] = set()
    for pattern in source_patterns:
        for entity_id in store.list_entities(pattern):
            entities.add(entity_id)

    # Count by status
    stale_count = 0
    ready_count = 0
    failed_count = 0
    complete_count = 0

    for entity_id in entities:
        ready = find_ready_stages(store, entity_id, stages, code_hashes)
        if ready:
            ready_count += len(ready)
            stale_count += len(ready)
        else:
            # Check if any failures
            has_failure = False
            for stage in stages:
                if stage.get("type") == "source":
                    continue
                failure = store.get_failure(entity_id, stage["pattern"])
                if failure:
                    failed_count += 1
                    has_failure = True
                    break

            if not has_failure:
                complete_count += 1

    return {
        "total_entities": len(entities),
        "stale": stale_count,
        "ready": ready_count,
        "failed": failed_count,
        "complete": complete_count,
    }


def _get_code_hashes_for_workflow(stages: list[dict]) -> dict[str, str]:
    """Get code hashes for all node types in workflow stages.

    Args:
        stages: List of stage definitions

    Returns:
        Dict mapping type_id to code hash
    """
    hashes: dict[str, str] = {}
    for stage in stages:
        if stage.get("type") == "source":
            continue
        node = stage.get("node", {})
        type_id = node.get("typeId")
        if type_id and type_id not in hashes:
            try:
                hashes[type_id] = get_code_hash(type_id)
            except ValueError:
                # Unknown node type, use placeholder
                hashes[type_id] = "unknown0"
    return hashes


def _get_stage(stages: list[dict], stage_id: str) -> dict | None:
    """Get stage definition by ID."""
    for stage in stages:
        if stage["id"] == stage_id:
            return stage
    return None


def _calculate_priority(_entity_id: str, _stage: dict) -> int:
    """Calculate priority for a work item.

    Lower priority = processed first.
    Currently uses simple alphabetical ordering of entity_id.

    Args:
        _entity_id: Entity identifier (unused for now)
        _stage: Stage definition (unused for now)

    Returns:
        Priority value (0 = highest)
    """
    # For now, just return 0 - all same priority
    # Could be extended to prioritize:
    # - Older entities first (FIFO)
    # - Certain stages first
    # - High-value entities
    return 0
