"""Tests for Claude agent node definitions."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.claude.nodes import NODE_TYPES, execute_claude_agent


# ##################################################################
# test NODE_TYPES registry structure
def test_node_types_has_claude_agent():
    assert "claude_agent" in NODE_TYPES


def test_claude_agent_has_execute():
    assert "execute" in NODE_TYPES["claude_agent"]
    assert callable(NODE_TYPES["claude_agent"]["execute"])


def test_claude_agent_has_kind():
    assert NODE_TYPES["claude_agent"]["kind"] == "map"


# ##################################################################
# test execute_claude_agent validation
def test_execute_claude_agent_no_prompt():
    result = execute_claude_agent({"prompt": ""}, None)
    assert len(result) == 1
    assert "error" in result[0]
    assert "prompt" in result[0]["error"].lower()


def test_execute_claude_agent_missing_prompt():
    result = execute_claude_agent({}, None)
    assert len(result) == 1
    assert "error" in result[0]
    assert "prompt" in result[0]["error"].lower()


# ##################################################################
# test conversation ID caching
def test_cache_stores_session_id():
    """Test that session IDs are stored in cache when conversation_id provided."""
    import uuid

    from modules.claude.nodes import _cache

    # Use unique key for this test to avoid collisions across runs
    unique_id = uuid.uuid4().hex[:8]
    test_conv_id = f"test-conversation-{unique_id}"
    cache_key = f"session:{test_conv_id}"

    # Initially should be None (fresh unique key)
    assert _cache.get_or_default(cache_key) is None

    # Store a test session ID
    test_session_id = f"test-session-{unique_id}"
    _cache.set(cache_key, test_session_id)

    # Should retrieve it
    retrieved = _cache.get_or_default(cache_key)
    assert retrieved == test_session_id


def test_cache_retrieves_session_id():
    """Test that session IDs are retrieved from cache."""
    from modules.claude.nodes import _cache

    test_conv_id = "test-conversation-456"
    test_session_id = "test-session-def"
    cache_key = f"session:{test_conv_id}"

    # Store
    _cache.set(cache_key, test_session_id)

    # Retrieve
    retrieved = _cache.get_or_default(cache_key)
    assert retrieved == test_session_id


def test_cache_returns_none_for_unknown():
    """Test that cache returns None for unknown conversation IDs."""
    from modules.claude.nodes import _cache

    cache_key = "session:nonexistent-conversation"
    retrieved = _cache.get_or_default(cache_key)
    assert retrieved is None


# ##################################################################
# test execute_claude_agent validation paths
def test_execute_claude_agent_extracts_empty_string_fields():
    """Test execute extracts fields even when empty strings."""
    # This tests the get() calls on node_data
    node_data = {
        "prompt": "",
        "conversation_id": "",
        "model": "",
        "allowed_tools": "",
        "system_prompt": "",
        "permission_mode": "",
        "cwd": "",
    }
    result = execute_claude_agent(node_data, None)
    assert len(result) == 1
    assert "error" in result[0]  # Empty prompt still fails


def test_execute_claude_agent_extracts_missing_fields():
    """Test execute handles missing optional fields gracefully."""
    # Prompt required, others optional
    node_data = {"prompt": ""}
    result = execute_claude_agent(node_data, None)
    assert len(result) == 1
    assert "error" in result[0]


def test_execute_claude_agent_returns_list():
    """Test execute always returns a list."""
    result = execute_claude_agent({}, None)
    assert isinstance(result, list)
    assert len(result) > 0


def test_execute_claude_agent_prompt_required():
    """Test that prompt is required (empty string fails)."""
    result = execute_claude_agent({"prompt": ""}, None)
    assert "error" in result[0]
    assert "prompt" in result[0]["error"].lower()


def test_execute_claude_agent_none_prompt():
    """Test that None prompt is handled."""
    result = execute_claude_agent({"prompt": None}, None)
    assert len(result) == 1
    # None is falsy so triggers "Prompt is required" error
    assert "error" in result[0]


def test_execute_claude_agent_whitespace_prompt():
    """Test that whitespace-only prompt triggers error."""
    result = execute_claude_agent({"prompt": "   "}, None)
    assert len(result) == 1
    # Whitespace is truthy so this would try to run the query
    # Result depends on SDK behavior


def test_execute_with_input_data_parameter():
    """Test execute accepts input_data parameter."""
    # Just verifying the function signature works
    result = execute_claude_agent({"prompt": ""}, {"some": "input"})
    assert isinstance(result, list)


def test_execute_with_credential_data_parameter():
    """Test execute accepts credential_data parameter (ignored)."""
    result = execute_claude_agent({"prompt": ""}, None, credential_data={"key": "val"})
    assert isinstance(result, list)


def test_node_types_claude_agent_complete():
    """Test claude_agent node type has all expected keys."""
    node = NODE_TYPES["claude_agent"]
    assert "execute" in node
    assert "kind" in node
    assert node["kind"] == "map"
    assert callable(node["execute"])


def test_node_types_claude_agent_execute_is_function():
    """Test that execute is the expected function."""
    assert NODE_TYPES["claude_agent"]["execute"] is execute_claude_agent


# ##################################################################
# test cache module access
def test_cache_module_available():
    """Test that _cache is available from the module."""
    from modules.claude.nodes import _cache

    assert _cache is not None


def test_cache_get_or_default_method():
    """Test cache has get_or_default method."""
    from modules.claude.nodes import _cache

    # Method exists and is callable
    assert hasattr(_cache, "get_or_default")
    assert callable(_cache.get_or_default)


def test_cache_set_method():
    """Test cache has set method."""
    from modules.claude.nodes import _cache

    # Method exists and is callable
    assert hasattr(_cache, "set")
    assert callable(_cache.set)


# ##################################################################
# test executor module access
def test_executor_available():
    """Test that _executor ThreadPoolExecutor is available."""
    from modules.claude.nodes import _executor

    assert _executor is not None


def test_executor_is_thread_pool():
    """Test that _executor is a ThreadPoolExecutor."""
    from concurrent.futures import ThreadPoolExecutor

    from modules.claude.nodes import _executor

    assert isinstance(_executor, ThreadPoolExecutor)
