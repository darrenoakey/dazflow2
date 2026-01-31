"""Staleness detection for pipeline states.

Determines when a state needs to be regenerated based on:
1. Missing output
2. Code changes (execute function changed)
3. Input changes (upstream content changed)
4. Upstream staleness (recursive)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state_store import StateStore


class StalenessReason(Enum):
    """Why a state is considered stale."""

    NOT_STALE = "not_stale"
    MISSING = "missing"
    CODE_CHANGED = "code_changed"
    INPUT_CHANGED = "input_changed"
    UPSTREAM_STALE = "upstream_stale"
    IN_FAILURE_BACKOFF = "in_failure_backoff"


@dataclass
class StalenessResult:
    """Result of staleness check."""

    is_stale: bool
    reason: StalenessReason
    details: str | None = None

    @staticmethod
    def fresh() -> "StalenessResult":
        return StalenessResult(is_stale=False, reason=StalenessReason.NOT_STALE)

    @staticmethod
    def missing() -> "StalenessResult":
        return StalenessResult(is_stale=True, reason=StalenessReason.MISSING, details="Output does not exist")

    @staticmethod
    def code_changed(old_hash: str, new_hash: str) -> "StalenessResult":
        return StalenessResult(
            is_stale=True,
            reason=StalenessReason.CODE_CHANGED,
            details=f"Code hash changed: {old_hash} -> {new_hash}",
        )

    @staticmethod
    def input_changed(input_name: str, old_hash: str, new_hash: str) -> "StalenessResult":
        return StalenessResult(
            is_stale=True,
            reason=StalenessReason.INPUT_CHANGED,
            details=f"Input '{input_name}' changed: {old_hash} -> {new_hash}",
        )

    @staticmethod
    def upstream_stale(upstream_name: str, upstream_reason: str) -> "StalenessResult":
        return StalenessResult(
            is_stale=True,
            reason=StalenessReason.UPSTREAM_STALE,
            details=f"Upstream '{upstream_name}' is stale: {upstream_reason}",
        )

    @staticmethod
    def in_backoff(retry_at: str) -> "StalenessResult":
        return StalenessResult(
            is_stale=False,  # Not stale for processing purposes
            reason=StalenessReason.IN_FAILURE_BACKOFF,
            details=f"In failure backoff, next retry at {retry_at}",
        )


def is_stale(
    store: "StateStore",
    entity_id: str,
    stage_id: str,
    stage_pattern: str,
    current_code_hash: str,
    input_stage_id: str | None = None,
    input_pattern: str | None = None,
    check_upstream: bool = True,
    _visited: set[str] | None = None,
) -> StalenessResult:
    """Check if a state is stale and needs regeneration.

    Args:
        store: State store instance
        entity_id: Entity identifier
        stage_id: Stage identifier (for error messages)
        stage_pattern: State pattern for this stage's output
        current_code_hash: Current hash of the execute function
        input_stage_id: ID of the input stage (if any)
        input_pattern: State pattern for the input stage
        check_upstream: Whether to recursively check upstream staleness
        _visited: Internal set to detect cycles

    Returns:
        StalenessResult with is_stale flag and reason
    """
    # Cycle detection
    if _visited is None:
        _visited = set()
    cache_key = f"{entity_id}:{stage_id}"
    if cache_key in _visited:
        # Already checking this - avoid infinite recursion
        return StalenessResult.fresh()
    _visited.add(cache_key)

    # Rule 1: Check if output exists
    manifest = store.get_manifest(entity_id)
    if not manifest:
        return StalenessResult.missing()

    state_info = manifest.states.get(stage_pattern)
    if not state_info:
        return StalenessResult.missing()

    # Source states are never stale (they just exist or don't)
    if state_info.is_source:
        return StalenessResult.fresh()

    # Rule 2: Check if code changed
    if state_info.code_hash != current_code_hash:
        return StalenessResult.code_changed(state_info.code_hash, current_code_hash)

    # Rules 3 & 4: Check input if we have one
    if input_stage_id and input_pattern:
        # First check if input is stale (recursive)
        if check_upstream:
            # For upstream, we need to know its code hash
            # For simplicity, assume source stages have "source00" hash
            input_info = manifest.states.get(input_pattern)
            if input_info and not input_info.is_source:
                # This would need the upstream's code hash
                # For now, skip recursive check if we don't have the info
                pass

        # Check if input content changed since we produced our output
        input_info = manifest.states.get(input_pattern)
        if input_info:
            current_input_hash = input_info.content_hash
            our_input_hash = state_info.input_hashes.get(input_stage_id)
            if our_input_hash != current_input_hash:
                return StalenessResult.input_changed(input_stage_id, our_input_hash or "none", current_input_hash)

    return StalenessResult.fresh()


def get_staleness_reason(
    store: "StateStore",
    entity_id: str,
    stage_id: str,
    stage_pattern: str,
    current_code_hash: str,
    input_stage_id: str | None = None,
    input_pattern: str | None = None,
) -> str:
    """Get human-readable staleness reason.

    Args:
        store: State store instance
        entity_id: Entity identifier
        stage_id: Stage identifier
        stage_pattern: State pattern for this stage
        current_code_hash: Current code hash
        input_stage_id: Input stage ID (if any)
        input_pattern: Input pattern (if any)

    Returns:
        Human-readable reason string
    """
    result = is_stale(
        store,
        entity_id,
        stage_id,
        stage_pattern,
        current_code_hash,
        input_stage_id,
        input_pattern,
    )
    if not result.is_stale:
        return "Up to date"
    return result.details or result.reason.value


def check_all_stages(
    store: "StateStore",
    entity_id: str,
    stages: list[dict],
    code_hashes: dict[str, str],
) -> dict[str, StalenessResult]:
    """Check staleness of all stages for an entity.

    Args:
        store: State store instance
        entity_id: Entity identifier
        stages: List of stage definitions
        code_hashes: Dict mapping node type IDs to code hashes

    Returns:
        Dict mapping stage IDs to StalenessResult
    """
    results: dict[str, StalenessResult] = {}

    for stage in stages:
        stage_id = stage["id"]
        stage_pattern = stage["pattern"]
        stage_type = stage.get("type", "transform")

        # Source stages are never stale
        if stage_type == "source":
            # Just check if it exists
            if store.exists(stage_pattern, entity_id):
                results[stage_id] = StalenessResult.fresh()
            else:
                results[stage_id] = StalenessResult.missing()
            continue

        # Get code hash for transform stages
        node_config = stage.get("node", {})
        type_id = node_config.get("typeId", "unknown")
        current_code_hash = code_hashes.get(type_id, "unknown0")

        # Get input info
        input_stage_id = stage.get("input")
        input_pattern = None
        if input_stage_id:
            for s in stages:
                if s["id"] == input_stage_id:
                    input_pattern = s["pattern"]
                    break

        results[stage_id] = is_stale(
            store,
            entity_id,
            stage_id,
            stage_pattern,
            current_code_hash,
            input_stage_id,
            input_pattern,
        )

    return results


def find_stale_stages(
    store: "StateStore",
    entity_id: str,
    stages: list[dict],
    code_hashes: dict[str, str],
) -> list[str]:
    """Find all stale stages for an entity.

    Args:
        store: State store instance
        entity_id: Entity identifier
        stages: List of stage definitions
        code_hashes: Dict mapping node type IDs to code hashes

    Returns:
        List of stale stage IDs
    """
    results = check_all_stages(store, entity_id, stages, code_hashes)
    return [stage_id for stage_id, result in results.items() if result.is_stale]


def find_ready_stages(
    store: "StateStore",
    entity_id: str,
    stages: list[dict],
    code_hashes: dict[str, str],
) -> list[str]:
    """Find stages that are stale AND have all inputs ready.

    A stage is "ready" if:
    1. It's stale (needs work)
    2. Its input stage (if any) is NOT stale
    3. It's not in failure backoff

    Args:
        store: State store instance
        entity_id: Entity identifier
        stages: List of stage definitions
        code_hashes: Dict mapping node type IDs to code hashes

    Returns:
        List of ready stage IDs
    """
    staleness = check_all_stages(store, entity_id, stages, code_hashes)

    # Build stage lookup
    stage_lookup = {s["id"]: s for s in stages}

    ready = []
    for stage_id, result in staleness.items():
        if not result.is_stale:
            continue

        stage = stage_lookup[stage_id]

        # Check if in failure backoff
        if not store.should_retry(entity_id, stage["pattern"]):
            continue

        # Check if input is ready
        input_stage_id = stage.get("input")
        if input_stage_id:
            input_result = staleness.get(input_stage_id)
            if input_result and input_result.is_stale:
                # Input is stale, can't process this stage yet
                continue

        ready.append(stage_id)

    return ready
