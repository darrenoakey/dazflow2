"""Tests for workflow executor."""

from src.executor import (
    evaluate_data_expressions,
    evaluate_expression,
    evaluate_template,
    execute_node,
)


# ##################################################################
# test evaluate_expression
# verifies javascript expression evaluation
def test_evaluate_expression_simple():
    result, error = evaluate_expression("1 + 2", {})
    assert error is None
    assert result == 3


def test_evaluate_expression_with_context():
    result, error = evaluate_expression("$.name", {"name": "test"})
    assert error is None
    assert result == "test"


def test_evaluate_expression_nested_context():
    result, error = evaluate_expression("$.user.email", {"user": {"email": "test@example.com"}})
    assert error is None
    assert result == "test@example.com"


def test_evaluate_expression_array_access():
    result, error = evaluate_expression("$.items[0]", {"items": [1, 2, 3]})
    assert error is None
    assert result == 1


def test_evaluate_expression_invalid_returns_error():
    result, error = evaluate_expression("invalid syntax (((", {})
    assert error is not None
    assert result is None


# ##################################################################
# test evaluate_template
# verifies template string evaluation with {{...}} blocks
def test_evaluate_template_no_expressions():
    result, had_errors = evaluate_template("plain text", {})
    assert result == "plain text"
    assert had_errors is False


def test_evaluate_template_single_expression():
    result, had_errors = evaluate_template("{{$.name}}", {"name": "Alice"})
    assert result == "Alice"
    assert had_errors is False


def test_evaluate_template_preserves_type_for_single_expression():
    result, had_errors = evaluate_template("{{$.count}}", {"count": 42})
    assert result == 42
    assert isinstance(result, int)
    assert had_errors is False


def test_evaluate_template_mixed_text_and_expression():
    result, had_errors = evaluate_template("Hello {{$.name}}!", {"name": "World"})
    assert result == "Hello World!"
    assert had_errors is False


def test_evaluate_template_multiple_expressions():
    result, had_errors = evaluate_template("{{$.a}} + {{$.b}} = {{$.a + $.b}}", {"a": 1, "b": 2})
    assert result == "1 + 2 = 3"
    assert had_errors is False


def test_evaluate_template_error_preserves_original():
    result, had_errors = evaluate_template("value: {{invalid}}", {})
    # On error, returns original template
    assert result == "value: {{invalid}}"
    assert had_errors is True


def test_evaluate_template_none_input():
    result, had_errors = evaluate_template(None, {})
    assert result is None
    assert had_errors is False


def test_evaluate_template_non_string():
    result, had_errors = evaluate_template(123, {})
    assert result == 123
    assert had_errors is False


# ##################################################################
# test evaluate_data_expressions
# verifies recursive expression evaluation in data structures
def test_evaluate_data_expressions_string():
    result = evaluate_data_expressions("{{$.x}}", {"x": "value"})
    assert result == "value"


def test_evaluate_data_expressions_dict():
    data = {"key": "{{$.x}}", "nested": {"inner": "{{$.y}}"}}
    result = evaluate_data_expressions(data, {"x": "a", "y": "b"})
    assert result == {"key": "a", "nested": {"inner": "b"}}


def test_evaluate_data_expressions_list():
    data = ["{{$.a}}", "{{$.b}}"]
    result = evaluate_data_expressions(data, {"a": 1, "b": 2})
    assert result == [1, 2]


def test_evaluate_data_expressions_none():
    result = evaluate_data_expressions(None, {})
    assert result is None


def test_evaluate_data_expressions_primitives():
    assert evaluate_data_expressions(42, {}) == 42
    assert evaluate_data_expressions(3.14, {}) == 3.14
    assert evaluate_data_expressions(True, {}) is True


# ##################################################################
# test execute_node
# verifies node execution with workflow and execution state
def test_execute_node_basic():
    workflow = {"nodes": [{"id": "node1", "typeId": "scheduled", "name": "scheduled1", "data": {}}], "connections": []}
    execution = {}

    result = execute_node("node1", workflow, execution)

    assert "node1" in result
    assert "output" in result["node1"]
    assert "nodeOutput" in result["node1"]
    assert "executedAt" in result["node1"]


def test_execute_node_unknown_node_returns_unchanged():
    workflow = {"nodes": [], "connections": []}
    execution = {"existing": "data"}

    result = execute_node("unknown", workflow, execution)

    assert result == {"existing": "data"}


def test_execute_node_unknown_type_returns_unchanged():
    workflow = {"nodes": [{"id": "node1", "typeId": "nonexistent", "data": {}}], "connections": []}
    execution = {}

    result = execute_node("node1", workflow, execution)

    assert result == {}


def test_execute_node_with_upstream():
    workflow = {
        "nodes": [
            {"id": "node1", "typeId": "scheduled", "name": "scheduled1", "data": {}},
            {
                "id": "node2",
                "typeId": "set",
                "name": "set1",
                "data": {"fields": [{"name": "status", "value": '"done"'}]},
            },
        ],
        "connections": [{"sourceNodeId": "node1", "targetNodeId": "node2"}],
    }
    execution = {}

    result = execute_node("node2", workflow, execution)

    # Both nodes should be executed
    assert "node1" in result
    assert "node2" in result
    # set1 output should contain the status field
    assert result["node2"]["nodeOutput"][0]["status"] == "done"


def test_execute_node_merges_output_with_node_name():
    workflow = {"nodes": [{"id": "node1", "typeId": "scheduled", "name": "mySchedule", "data": {}}], "connections": []}
    execution = {}

    result = execute_node("node1", workflow, execution)

    # Output should be namespaced under node name
    output = result["node1"]["output"]
    assert len(output) == 1
    assert "mySchedule" in output[0]
    assert "time" in output[0]["mySchedule"]


def test_execute_node_map_node_iterates_over_items():
    # Create a workflow with a hardwired source and a set (map) node
    workflow = {
        "nodes": [
            {"id": "source", "typeId": "hardwired", "name": "source", "data": {"json": '[{"x": 1}, {"x": 2}]'}},
            {
                "id": "mapper",
                "typeId": "set",
                "name": "mapper",
                "data": {"fields": [{"name": "y", "value": '"mapped"'}]},
            },
        ],
        "connections": [{"sourceNodeId": "source", "targetNodeId": "mapper"}],
    }
    execution = {}

    result = execute_node("mapper", workflow, execution)

    # Map node should produce 2 outputs
    assert len(result["mapper"]["nodeOutput"]) == 2
    assert all(item["y"] == "mapped" for item in result["mapper"]["nodeOutput"])


def test_execute_node_expression_evaluation():
    # Note: output is namespaced under node name, so $.source.value not $.value
    workflow = {
        "nodes": [
            {"id": "source", "typeId": "hardwired", "name": "source", "data": {"json": '[{"value": 100}]'}},
            {
                "id": "setter",
                "typeId": "set",
                "name": "setter",
                "data": {"fields": [{"name": "doubled", "value": "{{$.source.value * 2}}"}]},
            },
        ],
        "connections": [{"sourceNodeId": "source", "targetNodeId": "setter"}],
    }
    execution = {}

    result = execute_node("setter", workflow, execution)

    # Expression should be evaluated
    assert result["setter"]["nodeOutput"][0]["doubled"] == 200


def test_execute_node_does_not_mutate_input_execution():
    workflow = {"nodes": [{"id": "node1", "typeId": "scheduled", "name": "scheduled1", "data": {}}], "connections": []}
    original_execution = {"preserved": "value"}

    result = execute_node("node1", workflow, original_execution)

    # Original should not be mutated
    assert "node1" not in original_execution
    assert "preserved" in result
