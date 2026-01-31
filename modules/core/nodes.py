"""
Core node type definitions for dazflow2.
Each node type defines how to execute given node data and input.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from croniter import croniter


def execute_start(_node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Start node - just passes through or creates empty item."""
    return [{}]


def execute_scheduled(_node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Scheduled node - returns current timestamp."""
    return [{"time": datetime.now().isoformat()}]


def execute_hardwired(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Hardwired node - returns parsed JSON data."""
    json_str = node_data.get("json", "[]")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return [{"error": "Invalid JSON", "message": str(e)}]


def execute_set(node_data: dict, _item: dict, _credential_data: dict | None = None) -> dict:
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


def execute_transform(node_data: dict, _item: dict, _credential_data: dict | None = None) -> dict:
    """Transform node (map node) - transforms data using expression.

    Expression evaluation happens before this is called.
    """
    # Transform uses the expression field which should already be evaluated
    expression_result = node_data.get("expression", "")
    return {"result": expression_result}


def execute_if(node_data: dict, input_data: Any, _credential_data: dict | None = None) -> list:
    """IF node - filters items based on condition.

    Expression evaluation happens before this is called.
    """
    condition = node_data.get("condition", "true")
    # Condition should be evaluated to a boolean by expression evaluator
    if condition and str(condition).lower() not in ("false", "0", "null", "undefined", ""):
        return input_data if isinstance(input_data, list) else [input_data]
    return []


def execute_http(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """HTTP node - makes HTTP/HTTPS requests.

    Supports GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS methods.
    Can send JSON body or form-encoded data.
    """
    import urllib.request
    import urllib.error
    import urllib.parse

    url = node_data.get("url", "")
    method = node_data.get("method", "GET").upper()
    timeout = node_data.get("timeout", 30)

    if not url:
        return [{"error": "URL is required"}]

    # Build headers from fieldlist
    headers_list = node_data.get("headers", [])
    headers = {}
    for header in headers_list:
        name = header.get("name", "")
        value = header.get("value", "")
        if name:
            headers[name] = value

    # Build request body
    body_mode = node_data.get("body_mode", "none")
    body_data = None

    if body_mode == "json":
        json_body = node_data.get("json_body", "")
        if json_body:
            try:
                # Validate JSON
                json.loads(json_body)
                body_data = json_body.encode("utf-8")
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"
            except json.JSONDecodeError as e:
                return [{"error": f"Invalid JSON body: {e}"}]
    elif body_mode == "fields":
        body_fields = node_data.get("body_fields", [])
        body_obj = {}
        for field in body_fields:
            name = field.get("name", "")
            value = field.get("value", "")
            if name:
                # Try to parse value as JSON for nested objects/arrays/numbers
                try:
                    body_obj[name] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    body_obj[name] = value
        if body_obj:
            body_data = json.dumps(body_obj).encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

    try:
        request = urllib.request.Request(url, data=body_data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            response_headers = dict(response.headers)

            # Try to parse response as JSON
            try:
                response_data = json.loads(response_body)
            except json.JSONDecodeError:
                response_data = response_body

            return [
                {
                    "status": response.status,
                    "statusText": response.reason,
                    "headers": response_headers,
                    "body": response_data,
                    "url": response.url,
                }
            ]
    except urllib.error.HTTPError as e:
        # HTTP error (4xx, 5xx)
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
            try:
                error_body = json.loads(error_body)
            except json.JSONDecodeError:
                pass
        except Exception:
            pass
        return [
            {
                "error": f"HTTP {e.code}: {e.reason}",
                "status": e.code,
                "statusText": e.reason,
                "headers": dict(e.headers) if e.headers else {},
                "body": error_body,
            }
        ]
    except urllib.error.URLError as e:
        return [{"error": f"URL error: {e.reason}"}]
    except TimeoutError:
        return [{"error": f"Request timed out after {timeout} seconds"}]
    except Exception as e:
        return [{"error": str(e)}]


def execute_rss(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """RSS node - fetches RSS feed (placeholder for now)."""
    url = node_data.get("url", "")
    # TODO: Implement actual RSS fetching
    return [{"feed_url": url, "status": "not_implemented"}]


def execute_append_to_file(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Append to file node - appends content to a file."""
    filepath = node_data.get("filepath", "")
    content = node_data.get("content", "")
    if filepath:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "a") as f:
            f.write(str(content) + "\n")
    return [{"written": bool(filepath), "filepath": filepath}]


# ##################################################################
# Trigger registration functions
# These return scheduling info for trigger nodes


def register_scheduled(node_data: dict, _callback: Callable, last_execution_time: float | None = None) -> dict:
    """Register a scheduled trigger. Returns timing info for scheduler.

    Args:
        node_data: Node configuration (mode, interval, unit, cron)
        _callback: Callback function (not used here, handled by scheduler)
        last_execution_time: Unix timestamp of the last execution, or None if never run

    Supports two modes:
        - interval: Run every X seconds/minutes/hours/days
        - cron: Run according to cron expression (e.g., "0 9 * * 1-5" for weekdays at 9am)
    """
    mode = node_data.get("mode", "interval")
    now = time.time()

    if mode == "cron":
        cron_expression = node_data.get("cron", "*/5 * * * *")  # Default: every 5 minutes
        try:
            # Use the current time as base for calculating next trigger
            base_time = datetime.fromtimestamp(last_execution_time) if last_execution_time else datetime.now()
            cron = croniter(cron_expression, base_time)
            next_time = cron.get_next(datetime)
            trigger_at = next_time.timestamp()

            # If the next trigger time is in the past (shouldn't happen often), adjust
            if trigger_at <= now:
                cron = croniter(cron_expression, datetime.now())
                next_time = cron.get_next(datetime)
                trigger_at = next_time.timestamp()

            return {
                "type": "timed",
                "trigger_at": trigger_at,
                "cron": cron_expression,
            }
        except (ValueError, KeyError) as e:
            # Invalid cron expression - fall back to 5-minute interval
            return {
                "type": "timed",
                "trigger_at": now + 300,
                "interval_seconds": 300,
                "error": f"Invalid cron expression: {e}",
            }
    else:
        # Interval mode (default)
        interval = node_data.get("interval", 5)
        unit = node_data.get("unit", "minutes")

        # Convert to seconds
        multipliers = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400}
        interval_seconds = interval * multipliers.get(unit, 60)

        if last_execution_time is None:
            # Never executed before - fire immediately
            trigger_at = now
        else:
            # Calculate next trigger based on last execution
            trigger_at = last_execution_time + interval_seconds
            # If that time has already passed, fire immediately
            if trigger_at <= now:
                trigger_at = now

        return {
            "type": "timed",
            "trigger_at": trigger_at,
            "interval_seconds": interval_seconds,
        }


# Node type registry
# kind: "map" means the node processes single items (infrastructure handles array iteration)
NODE_TYPES = {
    "start": {
        "execute": execute_start,
        "kind": "array",
    },
    "scheduled": {
        "execute": execute_scheduled,
        "register": register_scheduled,
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
    "append_to_file": {
        "execute": execute_append_to_file,
        "kind": "array",
    },
}
