"""Tests for workflow testing framework."""

import json

import pytest

from src.config import ServerConfig
from src.workflow_testing import (
    TestAssertion,
    TestSuiteResult,
    WorkflowTestAssertions,
    WorkflowTestResult,
    discover_test_workflows,
    format_suite_result,
    format_test_result,
    run_workflow_test,
)


# ##################################################################
# test TestAssertion
def test_test_assertion_dataclass():
    """TestAssertion stores assertion data correctly."""
    assertion = TestAssertion(
        description="Test assertion",
        passed=True,
        actual="actual",
        expected="expected",
    )
    assert assertion.description == "Test assertion"
    assert assertion.passed is True
    assert assertion.actual == "actual"
    assert assertion.expected == "expected"


def test_test_assertion_with_error():
    """TestAssertion can store error message."""
    assertion = TestAssertion(
        description="Failed assertion",
        passed=False,
        error="Something went wrong",
    )
    assert assertion.passed is False
    assert assertion.error == "Something went wrong"


# ##################################################################
# test WorkflowTestResult
def test_workflow_test_result_dataclass():
    """WorkflowTestResult stores test result data correctly."""
    result = WorkflowTestResult(
        workflow_path="test.json",
        passed=True,
        execution_time_ms=100.5,
    )
    assert result.workflow_path == "test.json"
    assert result.passed is True
    assert result.execution_time_ms == 100.5
    assert result.assertions == []
    assert result.execution_result == {}


def test_workflow_test_result_with_assertions():
    """WorkflowTestResult can store assertions."""
    result = WorkflowTestResult(
        workflow_path="test.json",
        passed=True,
        execution_time_ms=50,
        assertions=[
            TestAssertion(description="Test 1", passed=True),
            TestAssertion(description="Test 2", passed=True),
        ],
    )
    assert len(result.assertions) == 2


# ##################################################################
# test WorkflowTestAssertions
def test_assertions_node_executed_pass():
    """node_executed passes when node exists in execution."""
    execution = {"my_node": {"output": {"value": 1}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_executed("my_node")
    assert len(assertions.assertions) == 1
    assert assertions.assertions[0].passed is True


def test_assertions_node_executed_fail():
    """node_executed fails when node doesn't exist."""
    execution = {"other_node": {"output": {"value": 1}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_executed("my_node")
    assert assertions.assertions[0].passed is False


def test_assertions_node_output_equals_pass():
    """node_output_equals passes when output matches."""
    execution = {"my_node": {"output": {"value": 42}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_equals("my_node", {"value": 42})
    assert assertions.assertions[0].passed is True


def test_assertions_node_output_equals_fail():
    """node_output_equals fails when output doesn't match."""
    execution = {"my_node": {"output": {"value": 42}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_equals("my_node", {"value": 100})
    assert assertions.assertions[0].passed is False


def test_assertions_node_output_contains_key_pass():
    """node_output_contains passes when key exists."""
    execution = {"my_node": {"output": {"name": "test", "count": 5}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_contains("my_node", "name")
    assert assertions.assertions[0].passed is True


def test_assertions_node_output_contains_key_fail():
    """node_output_contains fails when key doesn't exist."""
    execution = {"my_node": {"output": {"name": "test"}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_contains("my_node", "count")
    assert assertions.assertions[0].passed is False


def test_assertions_node_output_contains_with_value_pass():
    """node_output_contains passes when key exists with expected value."""
    execution = {"my_node": {"output": {"name": "test"}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_contains("my_node", "name", "test")
    assert assertions.assertions[0].passed is True


def test_assertions_node_output_contains_with_value_fail():
    """node_output_contains fails when value doesn't match."""
    execution = {"my_node": {"output": {"name": "test"}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_contains("my_node", "name", "wrong")
    assert assertions.assertions[0].passed is False


def test_assertions_node_output_matches_pass():
    """node_output_matches passes when predicate returns True."""
    execution = {"my_node": {"output": {"count": 10}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_matches("my_node", lambda o: o["count"] > 5, "count > 5")
    assert assertions.assertions[0].passed is True


def test_assertions_node_output_matches_fail():
    """node_output_matches fails when predicate returns False."""
    execution = {"my_node": {"output": {"count": 3}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_matches("my_node", lambda o: o["count"] > 5, "count > 5")
    assert assertions.assertions[0].passed is False


def test_assertions_node_output_matches_exception():
    """node_output_matches fails when predicate raises exception."""
    execution = {"my_node": {"output": None}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_output_matches("my_node", lambda o: o["count"] > 5, "count > 5")
    assert assertions.assertions[0].passed is False
    assert assertions.assertions[0].error is not None


def test_assertions_no_errors_pass():
    """no_errors passes when no node has error."""
    execution = {
        "node1": {"output": {"value": 1}},
        "node2": {"output": {"value": 2}},
    }
    assertions = WorkflowTestAssertions(execution)
    assertions.no_errors()
    assert assertions.assertions[0].passed is True


def test_assertions_no_errors_fail():
    """no_errors fails when a node has error."""
    execution = {
        "node1": {"output": {"value": 1}},
        "node2": {"output": None, "error": "Something failed"},
    }
    assertions = WorkflowTestAssertions(execution)
    assertions.no_errors()
    assert assertions.assertions[0].passed is False


def test_assertions_chaining():
    """Assertions can be chained."""
    execution = {"my_node": {"output": {"value": 42}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_executed("my_node").node_output_contains("my_node", "value").no_errors()
    assert len(assertions.assertions) == 3


def test_assertions_all_passed_true():
    """all_passed returns True when all assertions pass."""
    execution = {"my_node": {"output": {"value": 42}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_executed("my_node").no_errors()
    assert assertions.all_passed() is True


def test_assertions_all_passed_false():
    """all_passed returns False when any assertion fails."""
    execution = {"my_node": {"output": {"value": 42}}}
    assertions = WorkflowTestAssertions(execution)
    assertions.node_executed("my_node").node_executed("other_node")
    assert assertions.all_passed() is False


# ##################################################################
# test run_workflow_test
@pytest.mark.asyncio
async def test_run_workflow_test_not_found(tmp_path, monkeypatch):
    """run_workflow_test handles missing workflow gracefully."""
    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.workflow_testing.get_config", lambda: mock_config)

    (tmp_path / "workflows").mkdir()

    result = await run_workflow_test("nonexistent.json")
    assert result.passed is False
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_run_workflow_test_basic(tmp_path, monkeypatch):
    """run_workflow_test executes a simple workflow."""
    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.workflow_testing.get_config", lambda: mock_config)

    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()

    # Create a simple workflow with just a set node
    workflow = {
        "nodes": [
            {
                "id": "set-1",
                "typeId": "set",
                "name": "set_value",
                "position": {"x": 0, "y": 0},
                "data": {"values": [{"key": "message", "value": "hello"}]},
            }
        ],
        "connections": [],
    }
    (workflows_dir / "simple_test.json").write_text(json.dumps(workflow))

    result = await run_workflow_test("simple_test.json")
    # The workflow should execute without errors
    assert result.execution_time_ms > 0
    assert result.workflow_path == "simple_test.json"


# ##################################################################
# test discover_test_workflows
def test_discover_test_workflows(tmp_path, monkeypatch):
    """discover_test_workflows finds test workflow files."""
    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.workflow_testing.get_config", lambda: mock_config)

    workflows_dir = tmp_path / "workflows"
    tests_dir = workflows_dir / "tests"
    tests_dir.mkdir(parents=True)

    # Create test files
    (tests_dir / "sample_test.json").write_text("{}")
    (tests_dir / "test_basic.json").write_text("{}")
    (tests_dir / "regular.json").write_text("{}")  # Not a test file

    test_files = discover_test_workflows()
    assert len(test_files) == 2
    assert "tests/sample_test.json" in test_files
    assert "tests/test_basic.json" in test_files
    assert "tests/regular.json" not in test_files


def test_discover_test_workflows_empty(tmp_path, monkeypatch):
    """discover_test_workflows returns empty list when no tests directory."""
    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.workflow_testing.get_config", lambda: mock_config)

    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()

    test_files = discover_test_workflows()
    assert test_files == []


def test_discover_test_workflows_nested(tmp_path, monkeypatch):
    """discover_test_workflows finds tests in nested directories."""
    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.workflow_testing.get_config", lambda: mock_config)

    workflows_dir = tmp_path / "workflows"
    tests_dir = workflows_dir / "tests" / "nested"
    tests_dir.mkdir(parents=True)

    (tests_dir / "deep_test.json").write_text("{}")

    test_files = discover_test_workflows()
    assert len(test_files) == 1
    assert "tests/nested/deep_test.json" in test_files


# ##################################################################
# test TestSuiteResult
def test_suite_result_all_passed_true():
    """TestSuiteResult.all_passed returns True when no failures."""
    suite = TestSuiteResult(total=3, passed=3, failed=0)
    assert suite.all_passed is True


def test_suite_result_all_passed_false():
    """TestSuiteResult.all_passed returns False when failures exist."""
    suite = TestSuiteResult(total=3, passed=2, failed=1)
    assert suite.all_passed is False


# ##################################################################
# test format functions
def test_format_test_result_pass():
    """format_test_result formats passing test correctly."""
    result = WorkflowTestResult(
        workflow_path="test.json",
        passed=True,
        execution_time_ms=50,
    )
    output = format_test_result(result)
    assert "PASS" in output
    assert "test.json" in output
    assert "50ms" in output


def test_format_test_result_fail():
    """format_test_result formats failing test with details."""
    result = WorkflowTestResult(
        workflow_path="test.json",
        passed=False,
        execution_time_ms=100,
        assertions=[
            TestAssertion(
                description="Value should be 5",
                passed=False,
                actual=3,
                expected=5,
            ),
        ],
    )
    output = format_test_result(result)
    assert "FAIL" in output
    assert "test.json" in output
    assert "Value should be 5" in output
    assert "Expected: 5" in output
    assert "Actual: 3" in output


def test_format_test_result_with_error():
    """format_test_result shows error message."""
    result = WorkflowTestResult(
        workflow_path="test.json",
        passed=False,
        execution_time_ms=10,
        error="Workflow not found",
    )
    output = format_test_result(result)
    assert "FAIL" in output
    assert "Workflow not found" in output


def test_format_suite_result():
    """format_suite_result formats suite results correctly."""
    suite = TestSuiteResult(
        total=2,
        passed=1,
        failed=1,
        results=[
            WorkflowTestResult(workflow_path="test1.json", passed=True, execution_time_ms=50),
            WorkflowTestResult(workflow_path="test2.json", passed=False, execution_time_ms=30, error="Failed"),
        ],
    )
    output = format_suite_result(suite)
    assert "PASS" in output
    assert "FAIL" in output
    assert "1 of 2 tests failed" in output


def test_format_suite_result_all_pass():
    """format_suite_result shows success message when all pass."""
    suite = TestSuiteResult(
        total=3,
        passed=3,
        failed=0,
        results=[
            WorkflowTestResult(workflow_path="test1.json", passed=True, execution_time_ms=50),
            WorkflowTestResult(workflow_path="test2.json", passed=True, execution_time_ms=30),
            WorkflowTestResult(workflow_path="test3.json", passed=True, execution_time_ms=40),
        ],
    )
    output = format_suite_result(suite)
    assert "3 tests passed" in output
