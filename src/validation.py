"""Workflow validation module.

Provides validation/linting for workflow JSON to ensure:
- Valid JSON syntax
- Known node types
- Valid connections
- No duplicate IDs
- Required fields present
"""

from dataclasses import dataclass
from typing import Any

from src.module_loader import get_all_node_types


@dataclass
class ValidationError:
    """A single validation error."""

    path: str  # JSON path to the error location (e.g., "nodes[0].typeId")
    message: str  # Human-readable error message
    severity: str = "error"  # "error" or "warning"


@dataclass
class ValidationResult:
    """Result of workflow validation."""

    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "valid": self.valid,
            "errors": [{"path": e.path, "message": e.message, "severity": e.severity} for e in self.errors],
            "warnings": [{"path": w.path, "message": w.message, "severity": w.severity} for w in self.warnings],
        }

    def error_summary(self) -> str:
        """Get a summary of all errors for display."""
        if not self.errors:
            return "No errors"
        lines = [f"Found {len(self.errors)} validation error(s):"]
        for err in self.errors:
            lines.append(f"  - {err.path}: {err.message}")
        return "\n".join(lines)


def validate_workflow(workflow: Any) -> ValidationResult:
    """Validate a workflow object.

    Args:
        workflow: The workflow dict to validate

    Returns:
        ValidationResult with errors and warnings
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    # Check basic structure
    if not isinstance(workflow, dict):
        errors.append(ValidationError("", "Workflow must be a JSON object"))
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # Check required top-level fields
    if "nodes" not in workflow:
        errors.append(ValidationError("", "Workflow must have 'nodes' array"))
    elif not isinstance(workflow["nodes"], list):
        errors.append(ValidationError("nodes", "'nodes' must be an array"))

    if "connections" not in workflow:
        errors.append(ValidationError("", "Workflow must have 'connections' array"))
    elif not isinstance(workflow["connections"], list):
        errors.append(ValidationError("connections", "'connections' must be an array"))

    if errors:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # Get all valid node types
    valid_node_types = set(get_all_node_types().keys())

    # Track node IDs for connection validation
    node_ids: set[str] = set()
    node_names: set[str] = set()

    # Validate nodes
    for i, node in enumerate(workflow["nodes"]):
        node_path = f"nodes[{i}]"

        if not isinstance(node, dict):
            errors.append(ValidationError(node_path, "Node must be an object"))
            continue

        # Required fields
        if "id" not in node:
            errors.append(ValidationError(node_path, "Node must have 'id' field"))
        elif not isinstance(node["id"], str):
            errors.append(ValidationError(f"{node_path}.id", "Node 'id' must be a string"))
        else:
            if node["id"] in node_ids:
                errors.append(ValidationError(f"{node_path}.id", f"Duplicate node ID: {node['id']}"))
            node_ids.add(node["id"])

        if "typeId" not in node:
            errors.append(ValidationError(node_path, "Node must have 'typeId' field"))
        elif not isinstance(node["typeId"], str):
            errors.append(ValidationError(f"{node_path}.typeId", "Node 'typeId' must be a string"))
        elif node["typeId"] not in valid_node_types:
            errors.append(
                ValidationError(
                    f"{node_path}.typeId",
                    f"Unknown node type: '{node['typeId']}'. Valid types: {', '.join(sorted(valid_node_types))}",
                )
            )

        if "name" not in node:
            errors.append(ValidationError(node_path, "Node must have 'name' field"))
        elif not isinstance(node["name"], str):
            errors.append(ValidationError(f"{node_path}.name", "Node 'name' must be a string"))
        else:
            if node["name"] in node_names:
                warnings.append(
                    ValidationError(
                        f"{node_path}.name",
                        f"Duplicate node name: {node['name']} (may cause expression issues)",
                        severity="warning",
                    )
                )
            node_names.add(node["name"])

        if "position" not in node:
            errors.append(ValidationError(node_path, "Node must have 'position' field"))
        elif not isinstance(node["position"], dict):
            errors.append(ValidationError(f"{node_path}.position", "Node 'position' must be an object"))
        else:
            if "x" not in node["position"]:
                errors.append(ValidationError(f"{node_path}.position", "Position must have 'x' field"))
            if "y" not in node["position"]:
                errors.append(ValidationError(f"{node_path}.position", "Position must have 'y' field"))

        if "data" not in node:
            errors.append(ValidationError(node_path, "Node must have 'data' field"))
        elif not isinstance(node["data"], dict):
            errors.append(ValidationError(f"{node_path}.data", "Node 'data' must be an object"))

        # Validate node-specific data if we have the type
        if "typeId" in node and node["typeId"] in valid_node_types:
            node_errors = _validate_node_data(node, node_path)
            errors.extend(node_errors)

    # Track connection IDs
    connection_ids: set[str] = set()

    # Validate connections
    for i, conn in enumerate(workflow["connections"]):
        conn_path = f"connections[{i}]"

        if not isinstance(conn, dict):
            errors.append(ValidationError(conn_path, "Connection must be an object"))
            continue

        # Required fields
        if "id" not in conn:
            errors.append(ValidationError(conn_path, "Connection must have 'id' field"))
        elif not isinstance(conn["id"], str):
            errors.append(ValidationError(f"{conn_path}.id", "Connection 'id' must be a string"))
        else:
            if conn["id"] in connection_ids:
                errors.append(ValidationError(f"{conn_path}.id", f"Duplicate connection ID: {conn['id']}"))
            connection_ids.add(conn["id"])

        if "sourceNodeId" not in conn:
            errors.append(ValidationError(conn_path, "Connection must have 'sourceNodeId' field"))
        elif not isinstance(conn["sourceNodeId"], str):
            errors.append(ValidationError(f"{conn_path}.sourceNodeId", "'sourceNodeId' must be a string"))
        elif conn["sourceNodeId"] not in node_ids:
            errors.append(
                ValidationError(
                    f"{conn_path}.sourceNodeId",
                    f"Source node not found: '{conn['sourceNodeId']}'",
                )
            )

        if "targetNodeId" not in conn:
            errors.append(ValidationError(conn_path, "Connection must have 'targetNodeId' field"))
        elif not isinstance(conn["targetNodeId"], str):
            errors.append(ValidationError(f"{conn_path}.targetNodeId", "'targetNodeId' must be a string"))
        elif conn["targetNodeId"] not in node_ids:
            errors.append(
                ValidationError(
                    f"{conn_path}.targetNodeId",
                    f"Target node not found: '{conn['targetNodeId']}'",
                )
            )

        # Self-connection check
        if conn.get("sourceNodeId") and conn.get("targetNodeId") and conn["sourceNodeId"] == conn["targetNodeId"]:
            errors.append(ValidationError(conn_path, "Connection cannot connect a node to itself"))

    # Check for cycles
    if node_ids and not errors:  # Only check cycles if basic validation passed
        cycle_errors = _check_cycles(workflow)
        errors.extend(cycle_errors)

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def _validate_node_data(node: dict, node_path: str) -> list[ValidationError]:
    """Validate node-specific data fields.

    Args:
        node: The node dict
        node_path: Path prefix for error messages

    Returns:
        List of validation errors
    """
    errors: list[ValidationError] = []
    type_id = node.get("typeId", "")
    data = node.get("data", {})

    # Type-specific validation
    if type_id == "scheduled":
        mode = data.get("mode", "interval")
        if mode == "interval":
            if "interval" not in data:
                errors.append(
                    ValidationError(f"{node_path}.data", "Scheduled node (interval mode) requires 'interval'")
                )
            if "unit" not in data:
                errors.append(ValidationError(f"{node_path}.data", "Scheduled node (interval mode) requires 'unit'"))
            elif data.get("unit") not in ["seconds", "minutes", "hours", "days"]:
                errors.append(
                    ValidationError(
                        f"{node_path}.data.unit",
                        f"Invalid unit: '{data.get('unit')}'. Must be seconds/minutes/hours/days",
                    )
                )
        elif mode == "cron":
            if "cron" not in data:
                errors.append(
                    ValidationError(f"{node_path}.data", "Scheduled node (cron mode) requires 'cron' expression")
                )

    elif type_id == "set":
        if "fields" not in data:
            errors.append(ValidationError(f"{node_path}.data", "Set node requires 'fields' array"))
        elif not isinstance(data["fields"], list):
            errors.append(ValidationError(f"{node_path}.data.fields", "'fields' must be an array"))
        else:
            for j, field in enumerate(data["fields"]):
                if not isinstance(field, dict):
                    errors.append(ValidationError(f"{node_path}.data.fields[{j}]", "Field must be an object"))
                elif "name" not in field:
                    errors.append(ValidationError(f"{node_path}.data.fields[{j}]", "Field must have 'name'"))

    elif type_id == "if":
        if "condition" not in data:
            errors.append(ValidationError(f"{node_path}.data", "If node requires 'condition' expression"))

    elif type_id == "transform":
        if "expression" not in data:
            errors.append(ValidationError(f"{node_path}.data", "Transform node requires 'expression'"))

    elif type_id == "hardwired":
        if "json" not in data:
            errors.append(ValidationError(f"{node_path}.data", "Hardwired node requires 'json' field"))
        else:
            # Validate JSON syntax
            import json

            try:
                parsed = json.loads(data["json"])
                if not isinstance(parsed, list):
                    errors.append(ValidationError(f"{node_path}.data.json", "Hardwired JSON must be an array"))
            except json.JSONDecodeError as e:
                errors.append(ValidationError(f"{node_path}.data.json", f"Invalid JSON: {e}"))

    elif type_id == "postgres_query":
        if "query" not in data:
            errors.append(ValidationError(f"{node_path}.data", "Postgres query node requires 'query' field"))

    elif type_id == "run_command":
        if "command" not in data:
            errors.append(ValidationError(f"{node_path}.data", "Run command node requires 'command' field"))

    elif type_id == "notification":
        if "message" not in data:
            errors.append(ValidationError(f"{node_path}.data", "Notification node requires 'message' field"))

    elif type_id == "discord_send":
        if "message" not in data:
            errors.append(ValidationError(f"{node_path}.data", "Discord send node requires 'message' field"))

    return errors


def _check_cycles(workflow: dict) -> list[ValidationError]:
    """Check for cycles in the workflow graph.

    Args:
        workflow: The workflow dict

    Returns:
        List of validation errors if cycles found
    """
    errors: list[ValidationError] = []

    # Build adjacency list
    graph: dict[str, list[str]] = {}
    for node in workflow["nodes"]:
        graph[node["id"]] = []

    for conn in workflow["connections"]:
        source = conn.get("sourceNodeId")
        target = conn.get("targetNodeId")
        if source and target and source in graph:
            graph[source].append(target)

    # DFS for cycle detection
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycle_path: list[str] = []

    def dfs(node_id: str) -> bool:
        visited.add(node_id)
        rec_stack.add(node_id)
        cycle_path.append(node_id)

        for neighbor in graph.get(node_id, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                # Found cycle
                cycle_start = cycle_path.index(neighbor)
                cycle_nodes = cycle_path[cycle_start:] + [neighbor]
                errors.append(
                    ValidationError(
                        "connections",
                        f"Cycle detected: {' -> '.join(cycle_nodes)}",
                    )
                )
                return True

        cycle_path.pop()
        rec_stack.remove(node_id)
        return False

    for node_id in graph:
        if node_id not in visited:
            if dfs(node_id):
                break  # Stop after finding first cycle

    return errors


def validate_json_string(json_string: str) -> ValidationResult:
    """Validate a JSON string as a workflow.

    Args:
        json_string: JSON string to parse and validate

    Returns:
        ValidationResult with errors
    """
    import json

    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    try:
        workflow = json.loads(json_string)
    except json.JSONDecodeError as e:
        errors.append(ValidationError("", f"Invalid JSON syntax: {e}"))
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    return validate_workflow(workflow)
