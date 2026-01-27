"""Tests for AI brain module."""

from src.ai_brain import (
    AISession,
    _extract_workflow_from_response,
    clear_session,
    estimate_tokens,
    load_session,
    parse_cli_command,
    save_session,
)


# ##################################################################
# test AISession
def test_ai_session_to_dict():
    """AISession converts to dict correctly."""
    session = AISession(
        session_id="test-123",
        message_count=5,
        token_estimate=1000,
        created_at="2025-01-01T00:00:00",
        last_activity="2025-01-01T01:00:00",
        conversation_history=[{"role": "user", "content": "hello"}],
    )
    d = session.to_dict()
    assert d["session_id"] == "test-123"
    assert d["message_count"] == 5
    assert d["token_estimate"] == 1000
    assert len(d["conversation_history"]) == 1


def test_ai_session_from_dict():
    """AISession loads from dict correctly."""
    data = {
        "session_id": "test-456",
        "message_count": 10,
        "token_estimate": 2000,
        "created_at": "2025-01-01T00:00:00",
        "last_activity": "2025-01-01T02:00:00",
        "conversation_history": [{"role": "assistant", "content": "hi"}],
    }
    session = AISession.from_dict(data)
    assert session.session_id == "test-456"
    assert session.message_count == 10
    assert session.token_estimate == 2000
    assert len(session.conversation_history) == 1


def test_ai_session_from_dict_defaults():
    """AISession handles missing fields with defaults."""
    session = AISession.from_dict({})
    assert session.session_id is None
    assert session.message_count == 0
    assert session.token_estimate == 0
    assert session.conversation_history == []


# ##################################################################
# test session persistence
def test_save_and_load_session(tmp_path, monkeypatch):
    """Session can be saved and loaded."""
    # Mock get_config to return a config with tmp_path as data_dir
    from src.config import ServerConfig

    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.ai_brain.get_config", lambda: mock_config)

    session = AISession(
        session_id="persist-test",
        message_count=3,
        token_estimate=500,
        created_at="2025-01-01T00:00:00",
        conversation_history=[{"role": "user", "content": "test"}],
    )

    save_session(session)

    # Verify file exists
    session_path = tmp_path / "ai" / "session.json"
    assert session_path.exists()

    # Load and verify
    loaded = load_session()
    assert loaded.session_id == "persist-test"
    assert loaded.message_count == 3
    assert len(loaded.conversation_history) == 1


def test_load_session_creates_new_if_missing(tmp_path, monkeypatch):
    """load_session returns new session if file missing."""
    from src.config import ServerConfig

    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.ai_brain.get_config", lambda: mock_config)

    session = load_session()
    assert session.session_id is None
    assert session.message_count == 0
    assert session.created_at != ""


def test_clear_session(tmp_path, monkeypatch):
    """clear_session removes the session file."""
    from src.config import ServerConfig

    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.ai_brain.get_config", lambda: mock_config)

    # Create a session
    session = AISession(session_id="to-delete")
    save_session(session)

    session_path = tmp_path / "ai" / "session.json"
    assert session_path.exists()

    # Clear it
    clear_session()
    assert not session_path.exists()


def test_clear_session_no_file(tmp_path, monkeypatch):
    """clear_session handles missing file gracefully."""
    from src.config import ServerConfig

    mock_config = ServerConfig(data_dir=str(tmp_path))
    monkeypatch.setattr("src.ai_brain.get_config", lambda: mock_config)
    clear_session()  # Should not raise


# ##################################################################
# test estimate_tokens
def test_estimate_tokens():
    """Token estimation works correctly."""
    assert estimate_tokens("") == 0
    assert estimate_tokens("test") == 1  # 4 chars
    assert estimate_tokens("hello world") == 2  # 11 chars / 4 = 2


def test_estimate_tokens_long_text():
    """Token estimation scales with text length."""
    text = "a" * 1000
    assert estimate_tokens(text) == 250  # 1000 / 4


# ##################################################################
# test parse_cli_command
def test_parse_cli_command_list():
    """parse_cli_command recognizes 'list'."""
    cmd, args = parse_cli_command("list")
    assert cmd == "list"
    assert args == []


def test_parse_cli_command_list_with_path():
    """parse_cli_command handles 'list' with path argument."""
    cmd, args = parse_cli_command("list news/")
    assert cmd == "list"
    assert args == ["news/"]


def test_parse_cli_command_enable():
    """parse_cli_command recognizes 'enable'."""
    cmd, args = parse_cli_command("enable my-workflow.json")
    assert cmd == "enable"
    assert args == ["my-workflow.json"]


def test_parse_cli_command_disable():
    """parse_cli_command recognizes 'disable'."""
    cmd, args = parse_cli_command("disable my-workflow.json")
    assert cmd == "disable"
    assert args == ["my-workflow.json"]


def test_parse_cli_command_run():
    """parse_cli_command recognizes 'run'."""
    cmd, args = parse_cli_command("run sample.json")
    assert cmd == "run"
    assert args == ["sample.json"]


def test_parse_cli_command_status():
    """parse_cli_command recognizes 'status'."""
    cmd, args = parse_cli_command("status")
    assert cmd == "status"
    assert args == []


def test_parse_cli_command_aliases():
    """parse_cli_command handles command aliases."""
    # ls -> list
    cmd, args = parse_cli_command("ls")
    assert cmd == "list"

    # workflows -> list
    cmd, args = parse_cli_command("workflows")
    assert cmd == "list"

    # exec -> run
    cmd, args = parse_cli_command("exec sample.json")
    assert cmd == "run"

    # execute -> run
    cmd, args = parse_cli_command("execute sample.json")
    assert cmd == "run"


def test_parse_cli_command_unknown():
    """parse_cli_command returns None for unknown commands."""
    cmd, args = parse_cli_command("create a workflow that does something")
    assert cmd is None
    assert args == []


def test_parse_cli_command_empty():
    """parse_cli_command handles empty input."""
    cmd, args = parse_cli_command("")
    assert cmd is None
    assert args == []


def test_parse_cli_command_tags():
    """parse_cli_command recognizes 'tags'."""
    cmd, args = parse_cli_command("tags")
    assert cmd == "tags"


def test_parse_cli_command_groups():
    """parse_cli_command recognizes 'groups'."""
    cmd, args = parse_cli_command("groups")
    assert cmd == "groups"


def test_parse_cli_command_concurrency_alias():
    """parse_cli_command handles 'concurrency' -> 'groups'."""
    cmd, args = parse_cli_command("concurrency")
    assert cmd == "groups"


# ##################################################################
# test _extract_workflow_from_response
def test_extract_workflow_from_response_json_block():
    """Extracts workflow from JSON code block."""
    response = """Here is the workflow:

```json
{
  "nodes": [
    {"id": "node-1", "typeId": "start", "name": "trigger", "position": {"x": 0, "y": 0}, "data": {}}
  ],
  "connections": []
}
```

This workflow does nothing."""

    workflow = _extract_workflow_from_response(response)
    assert workflow is not None
    assert "nodes" in workflow
    assert len(workflow["nodes"]) == 1


def test_extract_workflow_from_response_no_json():
    """Returns None when no workflow JSON in response."""
    response = "I cannot help with that request."
    workflow = _extract_workflow_from_response(response)
    assert workflow is None


def test_extract_workflow_from_response_invalid_json():
    """Returns None for invalid JSON."""
    response = """```json
{invalid json here}
```"""
    workflow = _extract_workflow_from_response(response)
    assert workflow is None


def test_extract_workflow_from_response_non_workflow_json():
    """Returns None for valid JSON that isn't a workflow."""
    response = """```json
{"name": "test", "value": 42}
```"""
    workflow = _extract_workflow_from_response(response)
    assert workflow is None


def test_extract_workflow_from_response_code_block_without_json_marker():
    """Extracts workflow from code block without json marker."""
    response = """```
{
  "nodes": [],
  "connections": []
}
```"""
    workflow = _extract_workflow_from_response(response)
    assert workflow is not None
    assert workflow["nodes"] == []


def test_extract_workflow_from_response_multiple_blocks():
    """Extracts first valid workflow from multiple blocks."""
    response = """First some config:
```json
{"setting": "value"}
```

Then the workflow:
```json
{
  "nodes": [{"id": "n1", "typeId": "start", "name": "a", "position": {"x": 0, "y": 0}, "data": {}}],
  "connections": []
}
```"""
    workflow = _extract_workflow_from_response(response)
    assert workflow is not None
    assert len(workflow["nodes"]) == 1


# ##################################################################
# test get_system_prompt (basic)
def test_get_system_prompt_returns_string():
    """get_system_prompt returns a non-empty string."""
    from src.ai_brain import get_system_prompt

    prompt = get_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 100
    assert "dazflow2" in prompt


def test_get_system_prompt_with_workflow_context():
    """get_system_prompt includes workflow context when provided."""
    from src.ai_brain import get_system_prompt

    workflow = {"nodes": [{"id": "test"}], "connections": []}
    prompt = get_system_prompt(workflow_context=workflow)
    assert "Current Workflow Context" in prompt
    assert '"id": "test"' in prompt
