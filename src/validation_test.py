"""Tests for workflow validation module."""

from src.validation import ValidationError, ValidationResult, validate_json_string, validate_workflow


# ##################################################################
# test ValidationResult
def test_validation_result_to_dict():
    """ValidationResult converts to dict correctly."""
    result = ValidationResult(
        valid=False,
        errors=[ValidationError("nodes[0]", "Missing field")],
        warnings=[ValidationError("nodes[1].name", "Duplicate name", severity="warning")],
    )
    d = result.to_dict()
    assert d["valid"] is False
    assert len(d["errors"]) == 1
    assert d["errors"][0]["path"] == "nodes[0]"
    assert d["errors"][0]["message"] == "Missing field"
    assert len(d["warnings"]) == 1


def test_validation_result_error_summary():
    """error_summary returns formatted error list."""
    result = ValidationResult(
        valid=False,
        errors=[
            ValidationError("nodes[0]", "Error 1"),
            ValidationError("nodes[1]", "Error 2"),
        ],
        warnings=[],
    )
    summary = result.error_summary()
    assert "2 validation error(s)" in summary
    assert "nodes[0]: Error 1" in summary
    assert "nodes[1]: Error 2" in summary


def test_validation_result_error_summary_no_errors():
    """error_summary returns 'No errors' when valid."""
    result = ValidationResult(valid=True, errors=[], warnings=[])
    assert result.error_summary() == "No errors"


# ##################################################################
# test validate_workflow - basic structure
def test_validate_workflow_not_dict():
    """Non-dict workflow fails validation."""
    result = validate_workflow([])
    assert not result.valid
    assert any("must be a JSON object" in e.message for e in result.errors)


def test_validate_workflow_missing_nodes():
    """Workflow without nodes fails validation."""
    result = validate_workflow({"connections": []})
    assert not result.valid
    assert any("must have 'nodes'" in e.message for e in result.errors)


def test_validate_workflow_missing_connections():
    """Workflow without connections fails validation."""
    result = validate_workflow({"nodes": []})
    assert not result.valid
    assert any("must have 'connections'" in e.message for e in result.errors)


def test_validate_workflow_empty_valid():
    """Empty workflow (no nodes, no connections) is valid."""
    result = validate_workflow({"nodes": [], "connections": []})
    assert result.valid
    assert len(result.errors) == 0


# ##################################################################
# test validate_workflow - node validation
def test_validate_workflow_node_missing_id():
    """Node without id fails validation."""
    workflow = {
        "nodes": [{"typeId": "start", "name": "test", "position": {"x": 0, "y": 0}, "data": {}}],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("must have 'id'" in e.message for e in result.errors)


def test_validate_workflow_node_missing_type():
    """Node without typeId fails validation."""
    workflow = {
        "nodes": [{"id": "node-1", "name": "test", "position": {"x": 0, "y": 0}, "data": {}}],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("must have 'typeId'" in e.message for e in result.errors)


def test_validate_workflow_node_unknown_type():
    """Node with unknown typeId fails validation."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "nonexistent_type_xyz",
                "name": "test",
                "position": {"x": 0, "y": 0},
                "data": {},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("Unknown node type" in e.message for e in result.errors)


def test_validate_workflow_duplicate_node_id():
    """Duplicate node IDs fail validation."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "n1", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "node-1", "typeId": "start", "name": "n2", "position": {"x": 100, "y": 0}, "data": {}},
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("Duplicate node ID" in e.message for e in result.errors)


def test_validate_workflow_duplicate_node_name_warning():
    """Duplicate node names generate warning."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "same", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "node-2", "typeId": "start", "name": "same", "position": {"x": 100, "y": 0}, "data": {}},
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert result.valid  # Still valid, just warning
    assert any("Duplicate node name" in w.message for w in result.warnings)


def test_validate_workflow_valid_node():
    """Valid node passes validation."""
    workflow = {
        "nodes": [{"id": "node-1", "typeId": "start", "name": "trigger", "position": {"x": 0, "y": 0}, "data": {}}],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert result.valid


# ##################################################################
# test validate_workflow - connection validation
def test_validate_workflow_connection_missing_source():
    """Connection without sourceNodeId fails validation."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "n1", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "node-2", "typeId": "start", "name": "n2", "position": {"x": 100, "y": 0}, "data": {}},
        ],
        "connections": [{"id": "conn-1", "targetNodeId": "node-2"}],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("must have 'sourceNodeId'" in e.message for e in result.errors)


def test_validate_workflow_connection_invalid_source():
    """Connection with nonexistent source fails validation."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "n1", "position": {"x": 0, "y": 0}, "data": {}},
        ],
        "connections": [{"id": "conn-1", "sourceNodeId": "nonexistent", "targetNodeId": "node-1"}],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("Source node not found" in e.message for e in result.errors)


def test_validate_workflow_self_connection():
    """Self-referencing connection fails validation."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "n1", "position": {"x": 0, "y": 0}, "data": {}},
        ],
        "connections": [{"id": "conn-1", "sourceNodeId": "node-1", "targetNodeId": "node-1"}],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("cannot connect a node to itself" in e.message for e in result.errors)


def test_validate_workflow_valid_connection():
    """Valid connection passes validation."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "n1", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "node-2", "typeId": "start", "name": "n2", "position": {"x": 100, "y": 0}, "data": {}},
        ],
        "connections": [{"id": "conn-1", "sourceNodeId": "node-1", "targetNodeId": "node-2"}],
    }
    result = validate_workflow(workflow)
    assert result.valid


# ##################################################################
# test validate_workflow - cycle detection
def test_validate_workflow_cycle_detected():
    """Cycle in workflow graph fails validation."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "n1", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "node-2", "typeId": "start", "name": "n2", "position": {"x": 100, "y": 0}, "data": {}},
            {"id": "node-3", "typeId": "start", "name": "n3", "position": {"x": 200, "y": 0}, "data": {}},
        ],
        "connections": [
            {"id": "conn-1", "sourceNodeId": "node-1", "targetNodeId": "node-2"},
            {"id": "conn-2", "sourceNodeId": "node-2", "targetNodeId": "node-3"},
            {"id": "conn-3", "sourceNodeId": "node-3", "targetNodeId": "node-1"},  # Creates cycle
        ],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("Cycle detected" in e.message for e in result.errors)


def test_validate_workflow_no_cycle():
    """Linear workflow passes cycle check."""
    workflow = {
        "nodes": [
            {"id": "node-1", "typeId": "start", "name": "n1", "position": {"x": 0, "y": 0}, "data": {}},
            {"id": "node-2", "typeId": "start", "name": "n2", "position": {"x": 100, "y": 0}, "data": {}},
            {"id": "node-3", "typeId": "start", "name": "n3", "position": {"x": 200, "y": 0}, "data": {}},
        ],
        "connections": [
            {"id": "conn-1", "sourceNodeId": "node-1", "targetNodeId": "node-2"},
            {"id": "conn-2", "sourceNodeId": "node-2", "targetNodeId": "node-3"},
        ],
    }
    result = validate_workflow(workflow)
    assert result.valid


# ##################################################################
# test validate_workflow - node-specific validation
def test_validate_workflow_scheduled_interval_missing_fields():
    """Scheduled node in interval mode requires interval and unit."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "scheduled",
                "name": "trigger",
                "position": {"x": 0, "y": 0},
                "data": {"mode": "interval"},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("requires 'interval'" in e.message for e in result.errors)
    assert any("requires 'unit'" in e.message for e in result.errors)


def test_validate_workflow_scheduled_cron_missing_cron():
    """Scheduled node in cron mode requires cron expression."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "scheduled",
                "name": "trigger",
                "position": {"x": 0, "y": 0},
                "data": {"mode": "cron"},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("requires 'cron'" in e.message for e in result.errors)


def test_validate_workflow_scheduled_valid():
    """Valid scheduled node passes validation."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "scheduled",
                "name": "trigger",
                "position": {"x": 0, "y": 0},
                "data": {"mode": "interval", "interval": 5, "unit": "minutes"},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert result.valid


def test_validate_workflow_set_missing_fields():
    """Set node requires fields array."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "set",
                "name": "mapper",
                "position": {"x": 0, "y": 0},
                "data": {},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("requires 'fields'" in e.message for e in result.errors)


def test_validate_workflow_if_missing_condition():
    """If node requires condition."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "if",
                "name": "filter",
                "position": {"x": 0, "y": 0},
                "data": {},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("requires 'condition'" in e.message for e in result.errors)


def test_validate_workflow_hardwired_invalid_json():
    """Hardwired node with invalid JSON fails."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "hardwired",
                "name": "data",
                "position": {"x": 0, "y": 0},
                "data": {"json": "not valid json"},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("Invalid JSON" in e.message for e in result.errors)


def test_validate_workflow_hardwired_not_array():
    """Hardwired node JSON must be an array."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "hardwired",
                "name": "data",
                "position": {"x": 0, "y": 0},
                "data": {"json": '{"key": "value"}'},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert not result.valid
    assert any("must be an array" in e.message for e in result.errors)


def test_validate_workflow_hardwired_valid():
    """Valid hardwired node passes."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "hardwired",
                "name": "data",
                "position": {"x": 0, "y": 0},
                "data": {"json": '[{"name": "Alice"}]'},
            }
        ],
        "connections": [],
    }
    result = validate_workflow(workflow)
    assert result.valid


# ##################################################################
# test validate_json_string
def test_validate_json_string_invalid_syntax():
    """Invalid JSON syntax is detected."""
    result = validate_json_string("{invalid json}")
    assert not result.valid
    assert any("Invalid JSON syntax" in e.message for e in result.errors)


def test_validate_json_string_valid():
    """Valid JSON string passes."""
    result = validate_json_string('{"nodes": [], "connections": []}')
    assert result.valid


# ##################################################################
# test complete workflow validation
def test_validate_complete_workflow():
    """Complete valid workflow passes all checks."""
    workflow = {
        "nodes": [
            {
                "id": "node-1",
                "typeId": "scheduled",
                "name": "trigger",
                "position": {"x": 100, "y": 100},
                "data": {"mode": "interval", "interval": 5, "unit": "minutes"},
            },
            {
                "id": "node-2",
                "typeId": "set",
                "name": "mapper",
                "position": {"x": 300, "y": 100},
                "data": {"fields": [{"name": "time", "value": "{{$.trigger.time}}"}]},
            },
            {
                "id": "node-3",
                "typeId": "notification",
                "name": "notify",
                "position": {"x": 500, "y": 100},
                "data": {"title": "Alert", "message": "Time: {{$.mapper.time}}"},
            },
        ],
        "connections": [
            {"id": "conn-1", "sourceNodeId": "node-1", "targetNodeId": "node-2"},
            {"id": "conn-2", "sourceNodeId": "node-2", "targetNodeId": "node-3"},
        ],
    }
    result = validate_workflow(workflow)
    assert result.valid
    assert len(result.errors) == 0
