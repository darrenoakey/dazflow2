"""Workflow testing framework.

Execute workflows and assert against real results - no mocking.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import get_config
from .executor import execute_node
from .module_loader import load_all_modules


# ##################################################################
# test result types
@dataclass
class TestAssertion:
    """A single assertion result."""

    description: str
    passed: bool
    actual: Any = None
    expected: Any = None
    error: str | None = None


@dataclass
class WorkflowTestResult:
    """Result of a workflow test run."""

    workflow_path: str
    passed: bool
    execution_time_ms: float
    assertions: list[TestAssertion] = field(default_factory=list)
    execution_result: dict = field(default_factory=dict)
    error: str | None = None


# ##################################################################
# assertion helpers
class WorkflowTestAssertions:
    """Helper class for making assertions on workflow execution results."""

    def __init__(self, execution: dict):
        """Initialize with execution results.

        execution: dict mapping node names to their outputs
        """
        self.execution = execution
        self.assertions: list[TestAssertion] = []

    def node_executed(self, node_name: str) -> "WorkflowTestAssertions":
        """Assert that a node was executed."""
        passed = node_name in self.execution
        self.assertions.append(
            TestAssertion(
                description=f"Node '{node_name}' was executed",
                passed=passed,
                actual=list(self.execution.keys()) if not passed else node_name,
                expected=node_name,
            )
        )
        return self

    def node_output_equals(self, node_name: str, expected: Any) -> "WorkflowTestAssertions":
        """Assert that a node's output equals expected value."""
        actual = self.execution.get(node_name, {}).get("output")
        passed = actual == expected
        self.assertions.append(
            TestAssertion(
                description=f"Node '{node_name}' output equals expected",
                passed=passed,
                actual=actual,
                expected=expected,
            )
        )
        return self

    def node_output_contains(self, node_name: str, key: str, expected: Any = None) -> "WorkflowTestAssertions":
        """Assert that a node's output contains a key (and optionally a value)."""
        output = self.execution.get(node_name, {}).get("output", {})
        has_key = key in output if isinstance(output, dict) else False
        if expected is not None and has_key:
            passed = output.get(key) == expected
            actual = output.get(key)
        else:
            passed = has_key
            actual = list(output.keys()) if isinstance(output, dict) else type(output).__name__
        self.assertions.append(
            TestAssertion(
                description=f"Node '{node_name}' output contains key '{key}'"
                + (f" with value {expected!r}" if expected is not None else ""),
                passed=passed,
                actual=actual,
                expected=expected if expected is not None else f"key '{key}'",
            )
        )
        return self

    def node_output_matches(
        self, node_name: str, predicate: Callable, description: str | None = None
    ) -> "WorkflowTestAssertions":
        """Assert that a node's output matches a predicate function."""
        output = self.execution.get(node_name, {}).get("output")
        try:
            passed = predicate(output)
            error = None
        except Exception as e:
            passed = False
            error = str(e)
        self.assertions.append(
            TestAssertion(
                description=description or f"Node '{node_name}' output matches predicate",
                passed=passed,
                actual=output,
                expected="<predicate>",
                error=error,
            )
        )
        return self

    def no_errors(self) -> "WorkflowTestAssertions":
        """Assert that no node had an error."""
        errors = []
        for node_name, data in self.execution.items():
            if "error" in data and data["error"]:
                errors.append(f"{node_name}: {data['error']}")
        passed = len(errors) == 0
        self.assertions.append(
            TestAssertion(
                description="No execution errors",
                passed=passed,
                actual=errors if errors else "No errors",
                expected="No errors",
            )
        )
        return self

    def get_all_assertions(self) -> list[TestAssertion]:
        """Get all recorded assertions."""
        return self.assertions

    def all_passed(self) -> bool:
        """Check if all assertions passed."""
        return all(a.passed for a in self.assertions)


# ##################################################################
# workflow test runner
async def run_workflow_test(
    workflow_path: str,
    input_data: dict | None = None,
    assertions_fn: Callable | None = None,
) -> WorkflowTestResult:
    """Run a workflow test.

    Args:
        workflow_path: Path to the workflow JSON file (relative to workflows directory)
        input_data: Optional input data to pass to the workflow
        assertions_fn: Optional function that receives WorkflowTestAssertions and adds assertions

    Returns:
        WorkflowTestResult with execution details and assertion results
    """
    import time

    config = get_config()
    workflows_dir = Path(config.data_dir) / "workflows"
    full_path = workflows_dir / workflow_path

    start_time = time.time()
    result = WorkflowTestResult(
        workflow_path=workflow_path,
        passed=False,
        execution_time_ms=0,
    )

    try:
        # Load workflow
        if not full_path.exists():
            result.error = f"Workflow not found: {workflow_path}"
            return result

        workflow_data = json.loads(full_path.read_text())
        nodes = workflow_data.get("nodes", [])

        # Load modules
        load_all_modules()

        # Run the workflow by executing all nodes
        execution: dict = {}
        for node in nodes:
            node_id = node.get("id")
            if node_id and node_id not in execution:
                execution = execute_node(node_id, workflow_data, execution)

        result.execution_result = execution
        result.execution_time_ms = (time.time() - start_time) * 1000

        # Run assertions if provided
        if assertions_fn:
            test_assertions = WorkflowTestAssertions(execution)
            assertions_fn(test_assertions)
            result.assertions = test_assertions.get_all_assertions()
            result.passed = test_assertions.all_passed()
        else:
            # No assertions provided, just check for no errors
            test_assertions = WorkflowTestAssertions(execution)
            test_assertions.no_errors()
            result.assertions = test_assertions.get_all_assertions()
            result.passed = test_assertions.all_passed()

    except Exception as e:
        result.execution_time_ms = (time.time() - start_time) * 1000
        result.error = str(e)
        result.passed = False

    return result


def run_workflow_test_sync(
    workflow_path: str,
    input_data: dict | None = None,
    assertions_fn: Callable | None = None,
) -> WorkflowTestResult:
    """Synchronous wrapper for run_workflow_test."""
    return asyncio.run(run_workflow_test(workflow_path, input_data, assertions_fn))


# ##################################################################
# test discovery and running
@dataclass
class TestSuiteResult:
    """Result of running a test suite."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[WorkflowTestResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


def discover_test_workflows(test_dir: str = "tests") -> list[str]:
    """Discover workflow test files in the test directory.

    Test workflows should be named *_test.json or test_*.json
    """
    config = get_config()
    workflows_dir = Path(config.data_dir) / "workflows"
    tests_path = workflows_dir / test_dir

    if not tests_path.exists():
        return []

    test_files = []
    for path in tests_path.rglob("*.json"):
        name = path.stem
        if name.endswith("_test") or name.startswith("test_"):
            # Return path relative to workflows directory
            rel_path = path.relative_to(workflows_dir)
            test_files.append(str(rel_path))

    return sorted(test_files)


async def run_test_suite(
    test_files: list[str] | None = None,
    test_dir: str = "tests",
) -> TestSuiteResult:
    """Run a suite of workflow tests.

    Args:
        test_files: Optional list of specific test files to run
        test_dir: Directory to discover tests from (default: "tests")

    Returns:
        TestSuiteResult with all test results
    """
    if test_files is None:
        test_files = discover_test_workflows(test_dir)

    suite_result = TestSuiteResult()

    for test_file in test_files:
        result = await run_workflow_test(test_file)
        suite_result.results.append(result)
        suite_result.total += 1
        if result.passed:
            suite_result.passed += 1
        else:
            suite_result.failed += 1

    return suite_result


def run_test_suite_sync(
    test_files: list[str] | None = None,
    test_dir: str = "tests",
) -> TestSuiteResult:
    """Synchronous wrapper for run_test_suite."""
    return asyncio.run(run_test_suite(test_files, test_dir))


# ##################################################################
# CLI output formatting
def format_test_result(result: WorkflowTestResult) -> str:
    """Format a test result for CLI output."""
    lines = []
    status = "PASS" if result.passed else "FAIL"
    status_color = "\033[32m" if result.passed else "\033[31m"
    reset = "\033[0m"

    lines.append(f"{status_color}{status}{reset} {result.workflow_path} ({result.execution_time_ms:.0f}ms)")

    if result.error:
        lines.append(f"  Error: {result.error}")

    for assertion in result.assertions:
        if not assertion.passed:
            lines.append(f"  - {assertion.description}")
            lines.append(f"    Expected: {assertion.expected}")
            lines.append(f"    Actual: {assertion.actual}")
            if assertion.error:
                lines.append(f"    Error: {assertion.error}")

    return "\n".join(lines)


def format_suite_result(suite: TestSuiteResult) -> str:
    """Format a test suite result for CLI output."""
    lines = []

    for result in suite.results:
        lines.append(format_test_result(result))

    lines.append("")
    if suite.all_passed:
        lines.append(f"\033[32m{suite.total} tests passed\033[0m")
    else:
        lines.append(f"\033[31m{suite.failed} of {suite.total} tests failed\033[0m")

    return "\n".join(lines)
