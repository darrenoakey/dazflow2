"""Tests for docket module nodes.

Tests run against a real Docket instance. If Docket is not running, tests are skipped.
"""

import pytest
import httpx

from modules.docket.nodes import (
    DOCKET_URL,
    execute_docket_create_task,
    execute_docket_get_task,
    execute_docket_list_tasks,
    execute_docket_update_status,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _docket_available() -> bool:
    try:
        resp = httpx.get(f"{DOCKET_URL}/api/statuses", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _docket_available(),
    reason=f"Docket not running at {DOCKET_URL}",
)


def _make_task_data(**kwargs) -> dict:
    base = {
        "title": "Test Job: Software Engineer",
        "company": "Acme Corp",
        "location": "Sydney, NSW",
        "salary": "$120k",
        "url": "https://seek.com.au/job/12345",
        "source": "test",
        "status": "new",
        "tags": "test,automated",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_task():
    task = execute_docket_create_task(_make_task_data(), {})
    assert "id" in task
    assert task["title"] == "Test Job: Software Engineer"
    assert task["company"] == "Acme Corp"
    assert task["status"] == "new"
    assert "test" in task["tags"]


def test_get_task():
    created = execute_docket_create_task(_make_task_data(title="Get Me Task"), {})
    task_id = created["id"]

    fetched = execute_docket_get_task({"task_id": task_id}, {})
    assert fetched["id"] == task_id
    assert fetched["title"] == "Get Me Task"


def test_update_status():
    created = execute_docket_create_task(_make_task_data(title="Update Status Task"), {})
    task_id = created["id"]

    updated = execute_docket_update_status({"task_id": task_id, "status": "reviewing"}, {})
    assert updated["id"] == task_id
    assert updated["status"] == "reviewing"


def test_list_tasks():
    # Create a task to ensure at least one exists
    execute_docket_create_task(_make_task_data(title="List Test Task"), {})

    tasks = execute_docket_list_tasks({}, None)
    assert isinstance(tasks, list)
    assert len(tasks) >= 1


def test_list_tasks_filter_by_status():
    execute_docket_create_task(_make_task_data(title="Archived Task", status="archived"), {})

    archived = execute_docket_list_tasks({"status": "archived"}, None)
    assert all(t["status"] == "archived" for t in archived)


def test_create_task_minimal():
    """Only title is required."""
    task = execute_docket_create_task({"title": "Minimal Task"}, {})
    assert task["id"]
    assert task["title"] == "Minimal Task"
    assert task["status"] == "new"


def test_create_task_tags_as_string():
    task = execute_docket_create_task({"title": "Tag Task", "tags": "seek, python, remote"}, {})
    assert "seek" in task["tags"]
    assert "python" in task["tags"]
    assert "remote" in task["tags"]
