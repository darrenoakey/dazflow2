"""
Workflow executor for dazflow2.
Handles expression evaluation using V8 and node execution.
"""

import json
import re
from datetime import datetime
from typing import Any

from py_mini_racer import MiniRacer

from .nodes import get_node_type


# Create a V8 context for evaluating JavaScript expressions
def create_js_context() -> MiniRacer:
    """Create a fresh V8 context for expression evaluation."""
    return MiniRacer()


def evaluate_expression(expr: str, context_data: dict) -> tuple[Any, str | None]:
    """
    Evaluate a JavaScript expression with $ as the context data.

    Returns: (result, error) - error is None if successful
    """
    ctx = create_js_context()
    try:
        # Set up $ as the context data
        ctx.eval(f"var $ = {json.dumps(context_data)};")
        result = ctx.eval(expr)
        return result, None
    except Exception as e:
        return None, str(e)


def evaluate_template(template: str, context_data: dict) -> tuple[str | Any, bool]:
    """
    Evaluate a template string containing {{expression}} blocks.

    If the entire template is a single expression, returns the raw value (preserving type).
    Otherwise concatenates all parts as strings.

    Returns: (result, had_errors)
    """
    if not template or not isinstance(template, str):
        return template, False

    # Parse {{...}} blocks
    pattern = r"\{\{([\s\S]*?)\}\}"
    parts = []
    last_end = 0
    has_expressions = False
    has_errors = False

    for match in re.finditer(pattern, template):
        has_expressions = True
        # Add text before this expression
        if match.start() > last_end:
            parts.append(("text", template[last_end : match.start()]))

        # Evaluate expression
        expr = match.group(1)
        value, error = evaluate_expression(expr, context_data)
        if error:
            has_errors = True
            parts.append(("error", match.group(0)))  # Keep original {{...}}
        else:
            parts.append(("expr", value))

        last_end = match.end()

    # Add remaining text
    if last_end < len(template):
        parts.append(("text", template[last_end:]))

    if not has_expressions:
        return template, False

    if has_errors:
        # Return original template if any errors
        return template, True

    # If single expression, return raw value (preserve type)
    if len(parts) == 1 and parts[0][0] == "expr":
        return parts[0][1], False

    # Concatenate all parts as strings
    result = ""
    for part_type, part_value in parts:
        if part_type == "text":
            result += part_value
        else:
            result += str(part_value) if part_value is not None else ""

    return result, False


def evaluate_data_expressions(data: Any, context_data: dict) -> Any:
    """
    Recursively evaluate all {{...}} expressions in a data structure.

    Args:
        data: The data structure (can be dict, list, string, or primitive)
        context_data: The $ context for expression evaluation

    Returns:
        Data with all expressions evaluated
    """
    if data is None:
        return data

    if isinstance(data, str):
        result, _ = evaluate_template(data, context_data)
        return result

    if isinstance(data, list):
        return [evaluate_data_expressions(item, context_data) for item in data]

    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Evaluate both keys and values
            evaluated_key = evaluate_data_expressions(key, context_data)
            result[evaluated_key] = evaluate_data_expressions(value, context_data)
        return result

    return data


def execute_node(
    node_id: str,
    workflow: dict,
    execution: dict,
) -> dict:
    """
    Execute a node and return updated execution state.

    If upstream nodes haven't been executed, executes them first (recursively).

    Args:
        node_id: ID of the node to execute
        workflow: Workflow definition {nodes: [...], connections: [...]}
        execution: Current execution state {nodeId: {input, nodeOutput, output, executedAt}}

    Returns:
        Updated execution state
    """
    nodes = workflow.get("nodes", [])
    connections = workflow.get("connections", [])

    # Find the node
    node = next((n for n in nodes if n.get("id") == node_id), None)
    if not node:
        return execution

    # Get node type
    node_type = get_node_type(node.get("typeId"))
    if not node_type or not node_type.get("execute"):
        return execution

    # Find upstream connections
    incoming = [c for c in connections if c.get("targetNodeId") == node_id]

    # Get input from upstream - execute upstream if needed
    input_data = None
    for conn in incoming:
        source_id = conn.get("sourceNodeId")
        source_execution = execution.get(source_id)

        if not source_execution or not source_execution.get("output"):
            # Execute upstream node first
            execution = execute_node(source_id, workflow, execution)

        # Get the (now available) output
        source_execution = execution.get(source_id)
        if source_execution and source_execution.get("output"):
            input_data = source_execution["output"]
            break

    # Normalize input
    if input_data is None:
        input_data = []
    if not isinstance(input_data, list):
        input_data = [input_data]
    if len(input_data) == 0:
        input_data = [{}]

    # Execute the node
    node_data = node.get("data", {})
    execute_fn = node_type["execute"]

    if node_type.get("kind") == "map":
        # Map node: execute per-item with expression evaluation per-item
        node_output = []
        for item in input_data:
            # Evaluate expressions in node_data for this item
            evaluated_data = evaluate_data_expressions(node_data, item)
            result = execute_fn(evaluated_data, item)
            node_output.append(result)
    else:
        # Array node: execute once with full input
        # Use first item for expression evaluation context
        context = input_data[0] if input_data else {}
        evaluated_data = evaluate_data_expressions(node_data, context)
        node_output = execute_fn(evaluated_data, input_data)

    # Ensure output is a list
    if not isinstance(node_output, list):
        node_output = [node_output]

    # Merge input with node output, namespaced by node name
    node_name = node.get("name", node_id)
    combined_output = []
    for i, out in enumerate(node_output):
        inp = input_data[i] if i < len(input_data) else {}
        combined = {**inp, node_name: out}
        combined_output.append(combined)

    # Update execution state
    execution = dict(execution)  # Copy to avoid mutation
    execution[node_id] = {
        "input": input_data,
        "nodeOutput": node_output,
        "output": combined_output,
        "executedAt": datetime.now().isoformat(),
    }

    return execution
