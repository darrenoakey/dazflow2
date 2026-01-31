"""
Pipeline node type definitions for dazflow2.
State-based workflow nodes that integrate with the standard execution model.

These nodes allow workflows to:
- Trigger on state changes (new files, updated content)
- Read existing states
- Write states with manifest tracking for change detection
- Check state existence for conditional logic
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Import pipeline infrastructure
from src.pipeline.state_store import StateStore
from src.pipeline.patterns import scan_pattern, extract_variables_from_entity_id


def _get_state_store(node_data: dict) -> StateStore:
    """Get or create state store from node data."""
    state_root = node_data.get("state_root", "output/")
    # Use data directory as base
    from src.config import get_config

    root = Path(get_config().data_dir) / state_root
    store = StateStore(root)
    store.init()
    return store


# ##################################################################
# State Trigger Node
# Watches for entities needing work and triggers workflow execution


def execute_state_trigger(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """State trigger execution - returns entity info for the triggered entity.

    When triggered (either by scheduler or manually), returns the entity
    that needs processing along with its state information.
    """
    pattern = node_data.get("pattern", "")
    entity_id = node_data.get("_triggered_entity_id", "")  # Set by register

    if not entity_id:
        # Manual execution - scan for first entity needing work
        store = _get_state_store(node_data)
        matches = scan_pattern(store.root, pattern)
        if matches:
            entity_id = matches[0].entity_id

    if not entity_id:
        return [{"error": "No entity to process", "pattern": pattern}]

    # Extract variables from entity ID
    try:
        variables = extract_variables_from_entity_id(pattern, entity_id)
    except ValueError:
        variables = {"id": entity_id}

    return [
        {
            "entity_id": entity_id,
            "pattern": pattern,
            "variables": variables,
            "triggered_at": datetime.now().isoformat(),
        }
    ]


def register_state_trigger(node_data: dict, _callback: Callable, last_execution_time: float | None = None) -> dict:
    """Register a state trigger. Scans for entities needing work.

    Returns timing info similar to scheduled trigger, but triggers
    for each entity that needs processing.
    """
    pattern = node_data.get("pattern", "")
    scan_interval = node_data.get("scan_interval", 60)  # seconds
    now = time.time()

    if not pattern:
        return {
            "type": "timed",
            "trigger_at": now + scan_interval,
            "interval_seconds": scan_interval,
            "error": "No pattern configured",
        }

    # Scan for entities needing work
    store = _get_state_store(node_data)
    matches = scan_pattern(store.root, pattern)

    # Find entities with missing downstream states
    # For now, just return entities that match the pattern
    # Full staleness checking would require workflow context

    entities_needing_work = []
    for match in matches:
        # Check if this entity has failures in backoff
        if not store.should_retry(match.entity_id, pattern):
            continue
        entities_needing_work.append(match.entity_id)

    if entities_needing_work:
        # Trigger immediately for first entity
        return {
            "type": "timed",
            "trigger_at": now,
            "interval_seconds": scan_interval,
            "entity_id": entities_needing_work[0],
            "pending_count": len(entities_needing_work),
        }
    else:
        # No work found, check again after interval
        return {
            "type": "timed",
            "trigger_at": now + scan_interval,
            "interval_seconds": scan_interval,
            "pending_count": 0,
        }


# ##################################################################
# State Read Node
# Reads content from a state file


def execute_state_read(node_data: dict, input_data: Any, _credential_data: dict | None = None) -> list:
    """Read state content for an entity.

    Uses entity_id from input ($.entity_id) or from node data.
    Returns the state content and metadata.
    """
    pattern = node_data.get("pattern", "")
    entity_id = node_data.get("entity_id", "")

    # Get entity_id from input if not specified
    if not entity_id and isinstance(input_data, list) and input_data:
        entity_id = input_data[0].get("entity_id", "")

    if not pattern or not entity_id:
        return [{"error": "Pattern and entity_id are required"}]

    store = _get_state_store(node_data)

    # Read the state
    content = store.read(pattern, entity_id)
    if content is None:
        return [
            {
                "exists": False,
                "entity_id": entity_id,
                "pattern": pattern,
            }
        ]

    # Get manifest info
    state_info = store.get_state_info(entity_id, pattern)

    # Try to parse as JSON
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = content

    return [
        {
            "exists": True,
            "entity_id": entity_id,
            "pattern": pattern,
            "content": parsed,
            "raw_content": content,
            "code_hash": state_info.code_hash if state_info else None,
            "content_hash": state_info.content_hash if state_info else None,
            "produced_at": state_info.produced_at if state_info else None,
        }
    ]


# ##################################################################
# State Write Node
# Writes content to state store with manifest tracking


def execute_state_write(node_data: dict, input_data: Any, _credential_data: dict | None = None) -> list:
    """Write content to state store.

    Writes the content and updates manifest with code hash, content hash,
    and input hashes for change detection.
    """
    pattern = node_data.get("pattern", "")
    entity_id = node_data.get("entity_id", "")
    content = node_data.get("content", "")

    # Get entity_id from input if not specified
    if not entity_id and isinstance(input_data, list) and input_data:
        entity_id = input_data[0].get("entity_id", "")

    if not pattern or not entity_id:
        return [{"error": "Pattern and entity_id are required"}]

    if not content and isinstance(input_data, list) and input_data:
        # Use input data as content if not specified
        content = input_data[0].get("content", input_data[0])

    # Serialize content if needed
    if isinstance(content, (dict, list)):
        content = json.dumps(content, indent=2)
    else:
        content = str(content)

    # Validate content if validation rules exist
    min_size = node_data.get("min_size", 0)
    if len(content) < min_size:
        return [
            {
                "error": f"Content too small: {len(content)} < {min_size}",
                "entity_id": entity_id,
                "pattern": pattern,
            }
        ]

    store = _get_state_store(node_data)

    # Get code hash for this node type
    code_hash = node_data.get("_code_hash", "unknown0")

    # Collect input hashes from input data
    input_hashes = {}
    if isinstance(input_data, list) and input_data:
        for key in ["input_pattern", "source_pattern"]:
            input_pattern = input_data[0].get(key)
            if input_pattern:
                input_hash = store.get_content_hash(entity_id, input_pattern)
                if input_hash:
                    input_hashes[key] = input_hash

    # Write the state
    output_path = store.write(
        pattern=pattern,
        entity_id=entity_id,
        content=content,
        code_hash=code_hash,
        produced_by=node_data.get("_produced_by", "workflow"),
        input_hashes=input_hashes,
    )

    return [
        {
            "success": True,
            "entity_id": entity_id,
            "pattern": pattern,
            "path": output_path,
            "size": len(content),
        }
    ]


# ##################################################################
# State Check Node
# Checks if a state exists (for conditional logic)


def execute_state_check(node_data: dict, input_data: Any, _credential_data: dict | None = None) -> list:
    """Check if a state exists.

    Returns exists=True/False. Can be used with IF node for conditional logic.
    Also checks staleness if check_staleness is enabled.
    """
    pattern = node_data.get("pattern", "")
    entity_id = node_data.get("entity_id", "")
    check_staleness = node_data.get("check_staleness", False)

    # Get entity_id from input if not specified
    if not entity_id and isinstance(input_data, list) and input_data:
        entity_id = input_data[0].get("entity_id", "")

    if not pattern or not entity_id:
        return [{"error": "Pattern and entity_id are required"}]

    store = _get_state_store(node_data)
    exists = store.exists(pattern, entity_id)

    result = {
        "exists": exists,
        "entity_id": entity_id,
        "pattern": pattern,
    }

    if exists and check_staleness:
        state_info = store.get_state_info(entity_id, pattern)
        current_code_hash = node_data.get("expected_code_hash", state_info.code_hash if state_info else "")

        # Check if stale
        from src.pipeline.staleness import is_stale

        staleness_result = is_stale(
            store,
            entity_id=entity_id,
            stage_id="check",
            stage_pattern=pattern,
            current_code_hash=current_code_hash,
        )
        result["is_stale"] = staleness_result.is_stale
        result["staleness_reason"] = staleness_result.reason.value if staleness_result.is_stale else None

    return [result]


# ##################################################################
# State List Node
# Lists all entities matching a pattern


def execute_state_list(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List all entities matching a pattern.

    Returns array of entity info. Useful for batch processing.
    """
    pattern = node_data.get("pattern", "")
    include_stale_only = node_data.get("include_stale_only", False)

    if not pattern:
        return [{"error": "Pattern is required"}]

    store = _get_state_store(node_data)
    matches = scan_pattern(store.root, pattern)

    entities = []
    for match in matches:
        entity_info = {
            "entity_id": match.entity_id,
            "path": match.path,
            "variables": match.variables,
        }

        # Get manifest info if available
        state_info = store.get_state_info(match.entity_id, pattern)
        if state_info:
            entity_info["produced_at"] = state_info.produced_at
            entity_info["code_hash"] = state_info.code_hash

        # Check failure status
        failure = store.get_failure(match.entity_id, pattern)
        if failure:
            entity_info["has_failure"] = True
            entity_info["failure_attempts"] = failure.attempts
            entity_info["can_retry"] = store.should_retry(match.entity_id, pattern)

        # Filter based on include_stale_only
        if include_stale_only:
            # Only include if has failure or no manifest (never processed)
            if not failure and state_info:
                continue  # Skip - not stale

        entities.append(entity_info)

    return entities if entities else [{"count": 0, "pattern": pattern}]


# ##################################################################
# State Clear Failure Node
# Clears failure record to allow retry


def execute_state_clear_failure(node_data: dict, input_data: Any, _credential_data: dict | None = None) -> list:
    """Clear failure record for an entity/pattern.

    Allows immediate retry of failed state production.
    """
    pattern = node_data.get("pattern", "")
    entity_id = node_data.get("entity_id", "")

    if not entity_id and isinstance(input_data, list) and input_data:
        entity_id = input_data[0].get("entity_id", "")

    if not pattern or not entity_id:
        return [{"error": "Pattern and entity_id are required"}]

    store = _get_state_store(node_data)
    store.clear_failure(entity_id, pattern)

    return [{"success": True, "entity_id": entity_id, "pattern": pattern}]


# ##################################################################
# Node Type Registry


NODE_TYPES = {
    "state_trigger": {
        "execute": execute_state_trigger,
        "register": register_state_trigger,
        "kind": "array",
    },
    "state_read": {
        "execute": execute_state_read,
        "kind": "array",
    },
    "state_write": {
        "execute": execute_state_write,
        "kind": "array",
    },
    "state_check": {
        "execute": execute_state_check,
        "kind": "array",
    },
    "state_list": {
        "execute": execute_state_list,
        "kind": "array",
    },
    "state_clear_failure": {
        "execute": execute_state_clear_failure,
        "kind": "array",
    },
}
