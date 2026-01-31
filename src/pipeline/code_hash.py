"""Code hash calculation for change detection.

Tracks hash of node execution code to detect when code changes
and outputs need to be regenerated.
"""

from __future__ import annotations

import hashlib
import inspect
from typing import Callable

# Cache for code hashes to avoid recalculation
_code_hash_cache: dict[str, str] = {}


def calculate_function_hash(func: Callable) -> str:
    """Calculate hash of a function's source code.

    Args:
        func: Function to hash

    Returns:
        8-character hex hash of the function source

    Note:
        This hashes the source code text, so changes to whitespace,
        comments, or formatting will change the hash. This is intentional -
        any change to the code triggers a rebuild.
    """
    try:
        source = inspect.getsource(func)
        return hashlib.md5(source.encode()).hexdigest()[:8]
    except (OSError, TypeError):
        # Can't get source (builtin, C extension, etc.)
        # Return a static hash
        return "builtin0"


def get_code_hash(type_id: str, node_types: dict | None = None) -> str:
    """Get the code hash for a node type.

    Args:
        type_id: Node type identifier (e.g., "claude_agent", "http")
        node_types: Optional dict of node types (for testing).
                   If None, imports from modules.

    Returns:
        8-character hex hash of the node's execute function,
        or "static00" if no execute function.

    Raises:
        ValueError: If node type is not found
    """
    if type_id in _code_hash_cache:
        return _code_hash_cache[type_id]

    # Get node types registry
    if node_types is None:
        from src.modules import get_all_node_types

        node_types = get_all_node_types()

    node_type = node_types.get(type_id)
    if not node_type:
        raise ValueError(f"Unknown node type: {type_id}")

    execute_fn = node_type.get("execute")
    if not execute_fn:
        # No execute function = static node (e.g., start)
        code_hash = "static00"
    else:
        code_hash = calculate_function_hash(execute_fn)

    _code_hash_cache[type_id] = code_hash
    return code_hash


def invalidate_code_hashes() -> None:
    """Clear the code hash cache.

    Call this after hot-reloading modules to force recalculation
    of all code hashes.
    """
    _code_hash_cache.clear()


def get_all_code_hashes(node_types: dict | None = None) -> dict[str, str]:
    """Get code hashes for all node types.

    Args:
        node_types: Optional dict of node types. If None, imports from modules.

    Returns:
        Dict mapping type_id to code hash
    """
    if node_types is None:
        from src.modules import get_all_node_types

        node_types = get_all_node_types()

    return {type_id: get_code_hash(type_id, node_types) for type_id in node_types}
