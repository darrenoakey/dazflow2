"""Pipeline executor for running stages.

Executes individual stages for entities, managing state reads/writes
and error handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .code_hash import get_code_hash
from .patterns import extract_variables_from_entity_id, resolve_pattern

if TYPE_CHECKING:
    from .state_store import StateStore

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a stage."""

    success: bool
    output_path: str | None = None
    error: str | None = None
    error_details: str | None = None
    duration_ms: int = 0


async def execute_stage(
    store: "StateStore",
    entity_id: str,
    stage: dict,
    workflow: dict,
    node_executor: Any | None = None,
) -> ExecutionResult:
    """Execute a single stage for a single entity.

    Args:
        store: State store instance
        entity_id: Entity identifier
        stage: Stage definition
        workflow: Full workflow definition
        node_executor: Optional custom node executor (for testing)

    Returns:
        ExecutionResult with success status and output path
    """
    start_time = datetime.now()
    stage_id = stage["id"]
    stage_pattern = stage["pattern"]

    try:
        # Get stage configuration
        node = stage.get("node", {})
        type_id = node.get("typeId", "unknown")

        # Load input data if we have an input stage
        input_data = None
        input_content_hash = None
        input_stage_id = stage.get("input")

        if input_stage_id:
            input_stage = _get_stage(workflow.get("stages", []), input_stage_id)
            if input_stage:
                input_pattern = input_stage["pattern"]
                input_data = store.read(input_pattern, entity_id)
                input_content_hash = store.get_content_hash(entity_id, input_pattern)

                if input_data is None:
                    return ExecutionResult(
                        success=False,
                        error=f"Input state '{input_stage_id}' not found",
                        duration_ms=_duration_ms(start_time),
                    )

        # Build execution context
        variables = extract_variables_from_entity_id(stage_pattern, entity_id)
        context = {
            "entity": {"id": entity_id, **variables},
        }

        if input_stage_id and input_data:
            context[input_stage_id] = {
                "content": input_data,
                "path": resolve_pattern(
                    _get_stage(workflow.get("stages", []), input_stage_id)["pattern"],
                    variables,
                ),
            }

        # Evaluate expressions in node data
        evaluated_data = _evaluate_data(node.get("data", {}), context)

        # Execute the node
        if node_executor:
            result = await node_executor(type_id, evaluated_data, context)
        else:
            result = await _execute_node(type_id, evaluated_data, context)

        # Validate result if validation rules exist
        validation = stage.get("validation", {})
        if validation:
            _validate_result(result, validation)

        # Determine content to write
        content = _extract_content(result)

        # Get code hash
        try:
            code_hash = get_code_hash(type_id)
        except ValueError:
            code_hash = "unknown0"

        # Write state
        input_hashes = {}
        if input_stage_id and input_content_hash:
            input_hashes[input_stage_id] = input_content_hash

        output_path = store.write(
            pattern=stage_pattern,
            entity_id=entity_id,
            content=content,
            code_hash=code_hash,
            produced_by=f"{workflow.get('name', 'unknown')}#{stage_id}",
            input_hashes=input_hashes,
        )

        return ExecutionResult(
            success=True,
            output_path=output_path,
            duration_ms=_duration_ms(start_time),
        )

    except Exception as e:
        logger.exception(f"Error executing stage {stage_id} for {entity_id}")

        # Record failure
        store.record_failure(
            entity_id=entity_id,
            stage_pattern=stage_pattern,
            error=str(e),
            error_details=None,
            backoff_schedule=workflow.get("retryPolicy", {}).get("backoffSeconds"),
        )

        return ExecutionResult(
            success=False,
            error=str(e),
            duration_ms=_duration_ms(start_time),
        )


async def _execute_node(type_id: str, data: dict, context: dict) -> Any:
    """Execute a node type with the given data.

    This is a placeholder that should integrate with the actual
    node execution system.
    """
    # Import the actual executor
    try:
        from src.executor import execute_node_type

        return execute_node_type(type_id, data, context)
    except ImportError:
        # Fallback for testing
        logger.warning(f"No executor available for {type_id}, returning empty")
        return {"result": "placeholder"}


def _get_stage(stages: list[dict], stage_id: str) -> dict | None:
    """Get stage definition by ID."""
    for stage in stages:
        if stage["id"] == stage_id:
            return stage
    return None


def _evaluate_data(data: dict, context: dict) -> dict:
    """Evaluate template expressions in node data.

    This should integrate with the existing expression evaluation
    system, but for now does simple string replacement.
    """
    # Import the actual evaluator
    try:
        from src.executor import evaluate_data_expressions

        return evaluate_data_expressions(data, context)
    except ImportError:
        # Fallback: simple passthrough
        return data


def _validate_result(result: Any, validation: dict) -> None:
    """Validate result against validation rules.

    Raises:
        ValueError: If validation fails
    """
    content = _extract_content(result)

    min_size = validation.get("minSize")
    if min_size is not None:
        if isinstance(content, str) and len(content) < min_size:
            raise ValueError(f"Output too small: {len(content)} < {min_size} chars")
        elif isinstance(content, bytes) and len(content) < min_size:
            raise ValueError(f"Output too small: {len(content)} < {min_size} bytes")


def _extract_content(result: Any) -> str | bytes:
    """Extract writable content from execution result.

    Args:
        result: Raw result from node execution

    Returns:
        Content as string or bytes
    """
    if isinstance(result, str):
        return result
    if isinstance(result, bytes):
        return result
    if isinstance(result, dict):
        # Try common keys
        for key in ["content", "output", "result", "text", "body"]:
            if key in result:
                return str(result[key])
        # Fallback to JSON
        import json

        return json.dumps(result, indent=2)
    if isinstance(result, list):
        import json

        return json.dumps(result, indent=2)
    return str(result)


def _duration_ms(start_time: datetime) -> int:
    """Calculate duration in milliseconds since start time."""
    return int((datetime.now() - start_time).total_seconds() * 1000)
