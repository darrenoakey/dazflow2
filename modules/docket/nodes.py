"""Docket integration nodes for dazflow2.

Provides nodes for interacting with the local Docket task manager:
- docket_create_task: Create a new task
- docket_update_status: Update a task's status
- docket_list_tasks: List tasks with optional filtering
- docket_get_task: Get a single task by ID
- docket_parse_seek_email: AI-parse a SEEK alert email and create tasks

Configuration:
  DOCKET_URL   Base URL (default: http://localhost:8765)
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DOCKET_URL = os.environ.get("DOCKET_URL", "http://localhost:7654")

STATUSES = [
    "new",
    "reviewing",
    "interested",
    "applied",
    "interviewing",
    "offer",
    "rejected",
    "archived",
]


def _call(method: str, path: str, **kwargs) -> Any:
    """Make an HTTP call to the Docket API."""
    url = f"{DOCKET_URL}{path}"
    with httpx.Client(timeout=30) as client:
        resp = getattr(client, method)(url, **kwargs)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Node Implementations
# ---------------------------------------------------------------------------


def execute_docket_create_task(node_data: dict, _item: dict, _credential_data: dict | None = None) -> dict:
    """Create a new task in Docket."""
    payload: dict = {}

    title = node_data.get("title", "")
    if not title:
        title = "Untitled Task"
    payload["title"] = title

    for field in ["description", "url", "company", "location", "salary", "source"]:
        val = node_data.get(field, "")
        if val:
            payload[field] = val

    status = node_data.get("status", "new")
    if status:
        payload["status"] = status

    tags_raw = node_data.get("tags", "")
    if isinstance(tags_raw, list):
        payload["tags"] = tags_raw
    elif tags_raw:
        payload["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

    metadata_raw = node_data.get("metadata", {})
    if isinstance(metadata_raw, str):
        try:
            payload["metadata"] = json.loads(metadata_raw)
        except json.JSONDecodeError:
            payload["metadata"] = {}
    elif metadata_raw:
        payload["metadata"] = metadata_raw

    return _call("post", "/api/tasks", json=payload)


def execute_docket_update_status(node_data: dict, _item: dict, _credential_data: dict | None = None) -> dict:
    """Update a task's status in Docket."""
    task_id = node_data.get("task_id", "")
    if not task_id:
        raise ValueError("task_id is required")

    status = node_data.get("status", "new")
    return _call("put", f"/api/tasks/{task_id}", json={"status": status})


def execute_docket_list_tasks(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List tasks from Docket with optional filtering."""
    params: dict = {}

    status = node_data.get("status", "")
    if status:
        params["status"] = status

    search = node_data.get("search", "")
    if search:
        params["search"] = search

    return _call("get", "/api/tasks", params=params)


def execute_docket_get_task(node_data: dict, _item: dict, _credential_data: dict | None = None) -> dict:
    """Get a single task from Docket by ID."""
    task_id = node_data.get("task_id", "")
    if not task_id:
        raise ValueError("task_id is required")

    return _call("get", f"/api/tasks/{task_id}")


def execute_docket_parse_seek_email(node_data: dict, item: dict, _credential_data: dict | None = None) -> list:
    """Parse a SEEK alert email and create Docket tasks for each job listing.

    Expects the input item to be an email object with a 'body' field (HTML).
    Uses Claude Haiku to extract individual job listings, then creates a Docket
    task for each one.

    Returns: list of created task dicts.
    """
    import anthropic

    # Extract email body - support both direct and nested formats
    body = item.get("body") or item.get("html") or item.get("text") or ""
    subject = item.get("subject", "SEEK Alert")

    if not body:
        return [{"error": "No email body found in input", "subject": subject}]

    # Call Claude Haiku to extract job listings
    client = anthropic.Anthropic()

    prompt = f"""You are parsing a SEEK job alert email. Extract all individual job listings from the HTML below.

Return a JSON array of job objects. Each object must have these fields:
- title: job title (string)
- company: company name (string, empty string if not found)
- location: location/suburb (string, empty string if not found)
- salary: salary info (string, empty string if not found)
- url: direct link to the job on SEEK (string, empty string if not found)
- snippet: brief description or role summary (string, empty string if not found)

Return ONLY the JSON array, no other text. If no jobs found, return [].

Email subject: {subject}

HTML content:
{body[:15000]}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    first_block = message.content[0]
    if not hasattr(first_block, "text"):
        return [{"error": "Unexpected response type from Claude", "type": type(first_block).__name__}]
    response_text = first_block.text.strip()  # type: ignore[union-attr]

    # Parse the JSON response
    try:
        # Strip markdown code fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        jobs = json.loads(response_text)
    except json.JSONDecodeError as e:
        return [{"error": f"Failed to parse AI response as JSON: {e}", "raw": response_text}]

    if not isinstance(jobs, list):
        return [{"error": "AI response was not a JSON array", "raw": response_text}]

    # Create a Docket task for each job
    created_tasks = []
    for job in jobs:
        if not isinstance(job, dict):
            continue

        title = job.get("title", "").strip()
        if not title:
            continue

        payload = {
            "title": title,
            "description": job.get("snippet", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "salary": job.get("salary", ""),
            "url": job.get("url", ""),
            "source": "seek-email",
            "status": "new",
            "tags": ["seek"],
            "metadata": {
                "email_subject": subject,
                "parsed_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        try:
            task = _call("post", "/api/tasks", json=payload)
            created_tasks.append(task)
        except Exception as e:
            created_tasks.append({"error": str(e), "job": job})

    return created_tasks


# ---------------------------------------------------------------------------
# Node Type Registry
# ---------------------------------------------------------------------------

NODE_TYPES = {
    "docket_create_task": {
        "execute": execute_docket_create_task,
        "kind": "map",
    },
    "docket_update_status": {
        "execute": execute_docket_update_status,
        "kind": "map",
    },
    "docket_list_tasks": {
        "execute": execute_docket_list_tasks,
        "kind": "array",
    },
    "docket_get_task": {
        "execute": execute_docket_get_task,
        "kind": "map",
    },
    "docket_parse_seek_email": {
        "execute": execute_docket_parse_seek_email,
        "kind": "array",
    },
}
