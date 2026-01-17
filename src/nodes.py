"""
Node type definitions for dazflow2.
Each node type defines how to execute given node data and input.
"""

import json
from datetime import datetime
from typing import Any


def execute_start(_node_data: dict, _input_data: Any) -> list:
    """Start node - just passes through or creates empty item."""
    return [{}]


def execute_scheduled(_node_data: dict, _input_data: Any) -> list:
    """Scheduled node - returns current timestamp."""
    return [{"time": datetime.now().isoformat()}]


def execute_hardwired(node_data: dict, _input_data: Any) -> list:
    """Hardwired node - returns parsed JSON data."""
    json_str = node_data.get("json", "[]")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return [{"error": "Invalid JSON", "message": str(e)}]


def execute_set(node_data: dict, _item: dict) -> dict:
    """Set node (map node) - creates output with configured fields.

    This is a map node - receives single item, returns single item.
    Expression evaluation happens before this is called.
    """
    result = {}
    fields = node_data.get("fields", [])
    for field in fields:
        name = field.get("name", "")
        if name:
            value = field.get("value", "")
            # Try to parse as JSON, otherwise keep as string
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
            result[name] = value
    return result


def execute_transform(node_data: dict, _item: dict) -> dict:
    """Transform node (map node) - transforms data using expression.

    Expression evaluation happens before this is called.
    """
    # Transform uses the expression field which should already be evaluated
    expression_result = node_data.get("expression", "")
    return {"result": expression_result}


def execute_if(node_data: dict, input_data: Any) -> list:
    """IF node - filters items based on condition.

    Expression evaluation happens before this is called.
    """
    condition = node_data.get("condition", "true")
    # Condition should be evaluated to a boolean by expression evaluator
    if condition and str(condition).lower() not in ("false", "0", "null", "undefined", ""):
        return input_data if isinstance(input_data, list) else [input_data]
    return []


def execute_http(node_data: dict, _input_data: Any) -> list:
    """HTTP node - makes HTTP requests (placeholder for now)."""
    url = node_data.get("url", "")
    method = node_data.get("method", "GET")
    # TODO: Implement actual HTTP requests
    return [{"url": url, "method": method, "status": "not_implemented"}]


def execute_rss(node_data: dict, _input_data: Any) -> list:
    """RSS node - fetches RSS feed (placeholder for now)."""
    url = node_data.get("url", "")
    # TODO: Implement actual RSS fetching
    return [{"feed_url": url, "status": "not_implemented"}]


# Node type registry
# kind: "map" means the node processes single items (infrastructure handles array iteration)
NODE_TYPES = {
    "start": {
        "execute": execute_start,
        "kind": "array",
    },
    "scheduled": {
        "execute": execute_scheduled,
        "kind": "array",
    },
    "hardwired": {
        "execute": execute_hardwired,
        "kind": "array",
    },
    "set": {
        "execute": execute_set,
        "kind": "map",
    },
    "transform": {
        "execute": execute_transform,
        "kind": "map",
    },
    "if": {
        "execute": execute_if,
        "kind": "array",
    },
    "http": {
        "execute": execute_http,
        "kind": "array",
    },
    "rss": {
        "execute": execute_rss,
        "kind": "array",
    },
}


def get_node_type(type_id: str) -> dict | None:
    """Get node type definition by ID."""
    return NODE_TYPES.get(type_id)
