"""Agent-link integration nodes for dazflow2.

Provides triggers and actions for all agent-link service categories:
- Mail: email_trigger, email_list, email_search, email_get, email_send,
        email_move, email_mark_read, email_delete, email_list_folders
- Calendar: calendar_list, calendar_list_events, calendar_create_event
- Contacts: contacts_list
- Tasks: tasks_list_lists, tasks_list, tasks_create
- Generic: agent_link_call

The email_trigger uses SSE (Server-Sent Events) from agent-link to fire
workflows in real-time when emails are received.

All other nodes make synchronous HTTP calls to agent-link.

Configuration (via environment variables or defaults):
  AGENT_LINK_URL   Base URL (default: https://localhost:8900)
  AGENT_LINK_CA    CA cert path (default: ~/.agent-link/certs/ca.crt)
  AGENT_LINK_CERT  Client cert path (default: ~/.agent-link/certs/client/client.crt)
  AGENT_LINK_KEY   Client key path (default: ~/.agent-link/certs/client/client.key)
"""

import json
import os
import ssl
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENT_LINK_URL = os.environ.get("AGENT_LINK_URL", "https://localhost:8900")
_CA = os.path.expanduser(os.environ.get("AGENT_LINK_CA", "~/.agent-link/certs/ca.crt"))
_CERT = os.path.expanduser(os.environ.get("AGENT_LINK_CERT", "~/.agent-link/certs/client/client.crt"))
_KEY = os.path.expanduser(os.environ.get("AGENT_LINK_KEY", "~/.agent-link/certs/client/client.key"))


def _ssl_ctx() -> ssl.SSLContext:
    """Create SSL context with mTLS for agent-link."""
    ctx = ssl.create_default_context(cafile=_CA)
    ctx.load_cert_chain(_CERT, _KEY)
    return ctx


def _call(category: str, function: str, params: dict | None = None, source: str | None = None) -> list:
    """Call an agent-link function and return list of normalized result dicts.

    agent-link response formats:
      - Multi-source: {"results": [{"Data": ..., "Error": ..., "Source": ...}, ...]}
      - Single-source: {"Data": ..., "Error": ..., "Source": ...}

    Returns a list where each element is the unwrapped "Data" dict from each source.

    Args:
        category: Service category (e.g. "mail", "calendar", "tasks")
        function: Function name (e.g. "list-messages", "send")
        params: Request parameters dict
        source: Optional source name to target a specific source

    Returns:
        List of result dicts (Data payloads), one per source that responded
    """
    url = f"{AGENT_LINK_URL}/api/v1/call/{category}/{function}"
    if source:
        url += f"/{source}"

    with httpx.Client(verify=_ssl_ctx(), timeout=30) as client:
        resp = client.post(url, json=params or {})
        resp.raise_for_status()
        data = resp.json()

    # Normalize response format
    if "results" in data:
        raw = data["results"]
    elif isinstance(data, list):
        raw = data
    else:
        raw = [data]

    # Extract Data payload from each source result
    normalized: list = []
    for r in raw:
        if "Data" in r:
            if r.get("Error"):
                raise RuntimeError(f"agent-link error from {r.get('Source', '?')}: {r['Error']}")
            normalized.append(r["Data"])
        else:
            normalized.append(r)

    return normalized


# ---------------------------------------------------------------------------
# Email Trigger
# ---------------------------------------------------------------------------


def execute_email_trigger(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Sample output for the email trigger node (used for preview/testing)."""
    return [
        {
            "id": "sample-email-id",
            "from": "sender@example.com",
            "to": ["you@example.com"],
            "subject": "Sample Email Subject",
            "snippet": "This is a sample email message snippet...",
            "date": "2026-02-20T12:00:00Z",
        }
    ]


def register_email_trigger(node_data: dict, callback, last_execution_time=None):
    """Register the email trigger - subscribes to mail.received events via SSE.

    The trigger fires whenever a new email arrives via agent-link.
    Optional filters:
      from_filter    - partial match on sender address (case-insensitive)
      subject_filter - partial match on subject (case-insensitive)
      source         - exact agent-link source name to listen to
    """

    async def email_listener(node_data: dict, callback):
        """Async SSE listener. Runs until cancelled by the trigger system."""
        from_filter = node_data.get("from_filter", "").strip().lower()
        subject_filter = node_data.get("subject_filter", "").strip().lower()
        source_filter = node_data.get("source", "").strip()

        params = {"type": "mail.received"}
        if source_filter:
            params["source"] = source_filter

        ssl_ctx = _ssl_ctx()
        url = f"{AGENT_LINK_URL}/api/v1/events/subscribe"

        async with httpx.AsyncClient(verify=ssl_ctx) as client:
            async with client.stream("GET", url, params=params, timeout=None) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                        payload = event.get("payload", {})

                        # Apply from filter
                        if from_filter and from_filter not in payload.get("from", "").lower():
                            continue

                        # Apply subject filter
                        if subject_filter and subject_filter not in payload.get("subject", "").lower():
                            continue

                        callback(payload)
                    except json.JSONDecodeError:
                        pass

    return {"type": "push", "listener": email_listener}


# ---------------------------------------------------------------------------
# Mail Action Nodes
# ---------------------------------------------------------------------------


def execute_email_list(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List emails from a mailbox folder."""
    folder = node_data.get("folder", "INBOX") or "INBOX"
    query = node_data.get("query", "")
    max_results = int(node_data.get("max_results", 10) or 10)
    source = node_data.get("source", "") or None

    params: dict = {"folder": folder, "max_results": max_results}
    if query:
        params["query"] = query

    results = _call("mail", "list-messages", params, source)
    messages: list = []
    for r in results:
        messages.extend(r.get("messages", []))
    return [{"messages": messages, "count": len(messages)}]


def execute_email_search(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Search emails with a query string."""
    query = node_data.get("query", "")
    max_results = int(node_data.get("max_results", 10) or 10)
    source = node_data.get("source", "") or None

    results = _call("mail", "search", {"query": query, "max_results": max_results}, source)
    messages: list = []
    for r in results:
        messages.extend(r.get("messages", []))
    return [{"messages": messages, "count": len(messages)}]


def execute_email_get(node_data: dict, item: dict, _credential_data: dict | None = None) -> dict:
    """Get a full email by ID (includes body). Map node - one call per item."""
    msg_id = node_data.get("id", "")
    source = node_data.get("source", "") or None

    results = _call("mail", "get-message", {"id": msg_id}, source)
    if results:
        return results[0]
    return {"error": "Message not found"}


def execute_email_send(node_data: dict, item: dict, _credential_data: dict | None = None) -> dict:
    """Send an email. Map node - one send per item."""
    params: dict = {
        "to": node_data.get("to", ""),
        "subject": node_data.get("subject", ""),
        "body": node_data.get("body", ""),
    }
    if node_data.get("cc"):
        params["cc"] = node_data["cc"]
    if node_data.get("bcc"):
        params["bcc"] = node_data["bcc"]
    if node_data.get("html"):
        params["html"] = True

    source = node_data.get("source", "") or None
    results = _call("mail", "send", params, source)
    return results[0] if results else {"error": "Send failed"}


def execute_email_move(node_data: dict, item: dict, _credential_data: dict | None = None) -> dict:
    """Move an email to a folder. Map node."""
    params = {
        "id": node_data.get("id", ""),
        "folder": node_data.get("folder", ""),
    }
    source = node_data.get("source", "") or None
    results = _call("mail", "move-message", params, source)
    return results[0] if results else {"error": "Move failed"}


def execute_email_mark_read(node_data: dict, item: dict, _credential_data: dict | None = None) -> dict:
    """Mark an email as read. Map node."""
    msg_id = node_data.get("id", "")
    source = node_data.get("source", "") or None
    results = _call("mail", "mark-read", {"id": msg_id}, source)
    return results[0] if results else {"error": "Mark read failed"}


def execute_email_delete(node_data: dict, item: dict, _credential_data: dict | None = None) -> dict:
    """Delete an email. Map node."""
    msg_id = node_data.get("id", "")
    source = node_data.get("source", "") or None
    results = _call("mail", "delete-message", {"id": msg_id}, source)
    return results[0] if results else {"error": "Delete failed"}


def execute_email_list_folders(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List available mail folders."""
    source = node_data.get("source", "") or None
    results = _call("mail", "list-folders", {}, source)
    folders: list = []
    for r in results:
        folders.extend(r.get("folders", []))
    return [{"folders": folders, "count": len(folders)}]


# ---------------------------------------------------------------------------
# Calendar Action Nodes
# ---------------------------------------------------------------------------


def execute_calendar_list(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List available calendars."""
    source = node_data.get("source", "") or None
    results = _call("calendar", "list-calendars", {}, source)
    calendars: list = []
    for r in results:
        calendars.extend(r.get("calendars", []))
    return [{"calendars": calendars, "count": len(calendars)}]


def execute_calendar_list_events(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List events from a calendar."""
    params: dict = {"calendar_id": node_data.get("calendar_id", "primary") or "primary"}
    if node_data.get("time_min"):
        params["time_min"] = node_data["time_min"]
    if node_data.get("time_max"):
        params["time_max"] = node_data["time_max"]
    if node_data.get("max_results"):
        params["max_results"] = int(node_data["max_results"])

    source = node_data.get("source", "") or None
    results = _call("calendar", "list-events", params, source)
    events: list = []
    for r in results:
        events.extend(r.get("events", []))
    return [{"events": events, "count": len(events)}]


def execute_calendar_create_event(node_data: dict, item: dict, _credential_data: dict | None = None) -> dict:
    """Create a calendar event. Map node - one event per item."""
    params: dict = {
        "calendar_id": node_data.get("calendar_id", "primary") or "primary",
        "summary": node_data.get("summary", ""),
        "start": node_data.get("start", ""),
        "end": node_data.get("end", ""),
    }
    if node_data.get("description"):
        params["description"] = node_data["description"]
    if node_data.get("location"):
        params["location"] = node_data["location"]
    if node_data.get("attendees"):
        params["attendees"] = node_data["attendees"]

    source = node_data.get("source", "") or None
    results = _call("calendar", "create-event", params, source)
    if results:
        return results[0].get("event", results[0])
    return {"error": "Create event failed"}


# ---------------------------------------------------------------------------
# Contacts Action Nodes
# ---------------------------------------------------------------------------


def execute_contacts_list(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List or search contacts."""
    params: dict = {}
    if node_data.get("query"):
        params["query"] = node_data["query"]
    if node_data.get("max_results"):
        params["max_results"] = int(node_data["max_results"])

    source = node_data.get("source", "") or None
    results = _call("contacts", "list-contacts", params, source)
    contacts: list = []
    for r in results:
        contacts.extend(r.get("contacts", []))
    return [{"contacts": contacts, "count": len(contacts)}]


# ---------------------------------------------------------------------------
# Tasks Action Nodes
# ---------------------------------------------------------------------------


def execute_tasks_list_lists(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List task lists (e.g. Google Task lists)."""
    source = node_data.get("source", "") or None
    results = _call("tasks", "list-task-lists", {}, source)
    lists: list = []
    for r in results:
        lists.extend(r.get("lists", []))
    return [{"lists": lists, "count": len(lists)}]


def execute_tasks_list(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """List tasks from a task list."""
    params: dict = {}
    if node_data.get("list_id"):
        params["list_id"] = node_data["list_id"]
    if node_data.get("status_filter"):
        params["status_filter"] = node_data["status_filter"]

    source = node_data.get("source", "") or None
    results = _call("tasks", "list-tasks", params, source)
    tasks: list = []
    for r in results:
        tasks.extend(r.get("tasks", []))
    return [{"tasks": tasks, "count": len(tasks)}]


def execute_tasks_create(node_data: dict, item: dict, _credential_data: dict | None = None) -> dict:
    """Create a task. Map node - one task per item."""
    params: dict = {
        "list_id": node_data.get("list_id", ""),
        "title": node_data.get("title", ""),
    }
    if node_data.get("notes"):
        params["notes"] = node_data["notes"]
    if node_data.get("due_date"):
        params["due_date"] = node_data["due_date"]

    source = node_data.get("source", "") or None
    results = _call("tasks", "create-task", params, source)
    if results:
        return results[0].get("task", results[0])
    return {"error": "Create task failed"}


# ---------------------------------------------------------------------------
# Generic Agent-Link Call Node
# ---------------------------------------------------------------------------


def execute_agent_link_call(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Make an arbitrary agent-link call. Useful for any category/function."""
    category = node_data.get("category", "")
    function = node_data.get("function", "")
    source = node_data.get("source", "") or None

    if not category or not function:
        return [{"error": "Category and function are required"}]

    params_raw = node_data.get("params", "{}")
    if isinstance(params_raw, dict):
        params = params_raw
    else:
        try:
            params = json.loads(params_raw) if params_raw else {}
        except json.JSONDecodeError:
            return [{"error": f"Invalid JSON in params: {params_raw}"}]

    return _call(category, function, params, source)


# ---------------------------------------------------------------------------
# Node Type Registry
# ---------------------------------------------------------------------------

NODE_TYPES = {
    # ---- Email Trigger ----
    "email_trigger": {
        "execute": execute_email_trigger,
        "register": register_email_trigger,
        "kind": "array",
    },
    # ---- Mail Actions ----
    "email_list": {
        "execute": execute_email_list,
        "kind": "array",
    },
    "email_search": {
        "execute": execute_email_search,
        "kind": "array",
    },
    "email_get": {
        "execute": execute_email_get,
        "kind": "map",
    },
    "email_send": {
        "execute": execute_email_send,
        "kind": "map",
    },
    "email_move": {
        "execute": execute_email_move,
        "kind": "map",
    },
    "email_mark_read": {
        "execute": execute_email_mark_read,
        "kind": "map",
    },
    "email_delete": {
        "execute": execute_email_delete,
        "kind": "map",
    },
    "email_list_folders": {
        "execute": execute_email_list_folders,
        "kind": "array",
    },
    # ---- Calendar Actions ----
    "calendar_list": {
        "execute": execute_calendar_list,
        "kind": "array",
    },
    "calendar_list_events": {
        "execute": execute_calendar_list_events,
        "kind": "array",
    },
    "calendar_create_event": {
        "execute": execute_calendar_create_event,
        "kind": "map",
    },
    # ---- Contacts Actions ----
    "contacts_list": {
        "execute": execute_contacts_list,
        "kind": "array",
    },
    # ---- Tasks Actions ----
    "tasks_list_lists": {
        "execute": execute_tasks_list_lists,
        "kind": "array",
    },
    "tasks_list": {
        "execute": execute_tasks_list,
        "kind": "array",
    },
    "tasks_create": {
        "execute": execute_tasks_create,
        "kind": "map",
    },
    # ---- Generic ----
    "agent_link_call": {
        "execute": execute_agent_link_call,
        "kind": "array",
    },
}
