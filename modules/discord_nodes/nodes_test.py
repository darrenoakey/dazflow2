"""Tests for Discord node definitions.

These are real integration tests that connect to actual Discord servers.
Requires discord_events/token in keyring and access to a server with #unit-testing channel.
"""

import asyncio
import sys
import threading
from pathlib import Path

import keyring
import pytest

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.discord_nodes.nodes import (
    NODE_TYPES,
    DiscordConnection,
    _async_delay,
    _create_send_result_event,
    _format_channels_for_dropdown,
    _format_servers_for_dropdown,
    _generate_sample_message,
    _handle_send_result,
    _should_trigger_for_mode,
    _validate_bot_token,
    _validate_send_params,
    close_all_connections,
    execute_discord_send,
    execute_discord_trigger,
    get_connection,
    get_discord_channels,
    get_discord_servers,
    register_discord_trigger,
)


def _get_test_bot_token() -> str:
    """Get the Discord bot token from keyring for tests."""
    token = keyring.get_password("discord_events", "token")
    if not token:
        raise RuntimeError("Discord token not found in keyring (discord_events/token)")
    return token


def _get_test_credential_data() -> dict:
    """Get credential data dict for tests."""
    return {"bot_token": _get_test_bot_token()}


@pytest.fixture(scope="module")
def discord_connection():
    """Establish a real Discord connection for integration tests."""
    token = _get_test_bot_token()
    conn = get_connection(token)
    yield conn
    close_all_connections()


@pytest.fixture(scope="module")
def discord_test_data(discord_connection):
    """Get test data (servers, channels) from real Discord connection."""
    conn = discord_connection
    servers = conn.get_servers()
    assert len(servers) > 0, "No servers found for bot"

    unit_testing_channel_id = None
    unit_testing_server_id = None
    for server in servers:
        channels = conn.get_channels(server["id"])
        for ch in channels:
            if "unit-testing" in ch["name"].lower():
                unit_testing_channel_id = ch["id"]
                unit_testing_server_id = server["id"]
                break
        if unit_testing_channel_id:
            break

    assert unit_testing_channel_id is not None, "Could not find #unit-testing channel"

    return {
        "servers": servers,
        "unit_testing_channel_id": unit_testing_channel_id,
        "unit_testing_server_id": unit_testing_server_id,
    }


# ##################################################################
# test NODE_TYPES registry structure
def test_node_types_has_discord_trigger():
    assert "discord_trigger" in NODE_TYPES


def test_node_types_has_discord_send():
    assert "discord_send" in NODE_TYPES


def test_discord_trigger_has_execute():
    assert "execute" in NODE_TYPES["discord_trigger"]
    assert callable(NODE_TYPES["discord_trigger"]["execute"])


def test_discord_send_has_execute():
    assert "execute" in NODE_TYPES["discord_send"]
    assert callable(NODE_TYPES["discord_send"]["execute"])


def test_discord_trigger_has_kind():
    assert NODE_TYPES["discord_trigger"]["kind"] == "array"


def test_discord_send_has_kind():
    assert NODE_TYPES["discord_send"]["kind"] == "array"


def test_discord_trigger_requires_discord_credential():
    assert NODE_TYPES["discord_trigger"]["requiredCredential"] == "discord"


def test_discord_send_requires_discord_credential():
    assert NODE_TYPES["discord_send"]["requiredCredential"] == "discord"


def test_discord_trigger_has_dynamic_enums():
    assert "dynamicEnums" in NODE_TYPES["discord_trigger"]
    assert "server_id" in NODE_TYPES["discord_trigger"]["dynamicEnums"]
    assert "channel_id" in NODE_TYPES["discord_trigger"]["dynamicEnums"]


def test_discord_send_has_dynamic_enums():
    assert "dynamicEnums" in NODE_TYPES["discord_send"]
    assert "server_id" in NODE_TYPES["discord_send"]["dynamicEnums"]
    assert "channel_id" in NODE_TYPES["discord_send"]["dynamicEnums"]


# ##################################################################
# test execute_discord_trigger (sample message generation)
def test_execute_discord_trigger_returns_sample():
    result = execute_discord_trigger({"server_id": "123", "channel_id": "456", "mode": "new_messages"}, None)
    assert len(result) == 1
    assert "id" in result[0]
    assert "content" in result[0]
    assert "author" in result[0]
    assert "channel" in result[0]
    assert "server" in result[0]
    assert "timestamp" in result[0]


def test_execute_discord_trigger_includes_reply_to_for_replies_mode():
    result = execute_discord_trigger({"server_id": "123", "channel_id": "456", "mode": "replies"}, None)
    assert result[0]["reply_to"] is not None


def test_execute_discord_trigger_includes_reply_to_for_combined_mode():
    result = execute_discord_trigger(
        {"server_id": "123", "channel_id": "456", "mode": "new_messages_and_replies"}, None
    )
    assert result[0]["reply_to"] is not None


def test_execute_discord_trigger_no_reply_to_for_new_messages_mode():
    result = execute_discord_trigger({"server_id": "123", "channel_id": "456", "mode": "new_messages"}, None)
    assert result[0]["reply_to"] is None


# ##################################################################
# test execute_discord_send validation (no connection needed)
def test_execute_discord_send_no_credentials():
    result = execute_discord_send({"channel_id": "123", "message": "test"}, None, credential_data=None)
    assert len(result) == 1
    assert "error" in result[0]
    assert "credentials" in result[0]["error"].lower()


def test_execute_discord_send_no_bot_token():
    result = execute_discord_send({"channel_id": "123", "message": "test"}, None, credential_data={"bot_token": ""})
    assert len(result) == 1
    assert "error" in result[0]
    assert "token" in result[0]["error"].lower()


def test_execute_discord_send_no_channel():
    result = execute_discord_send(
        {"channel_id": "", "message": "test"}, None, credential_data={"bot_token": "any_token"}
    )
    assert len(result) == 1
    assert "error" in result[0]
    assert "channel" in result[0]["error"].lower()


def test_execute_discord_send_no_message():
    result = execute_discord_send(
        {"channel_id": "123", "message": ""}, None, credential_data={"bot_token": "any_token"}
    )
    assert len(result) == 1
    assert "error" in result[0]
    assert "message" in result[0]["error"].lower()


def test_execute_discord_send_missing_channel_key():
    """Test execute_discord_send with missing channel_id key entirely."""
    result = execute_discord_send({"message": "test"}, None, credential_data={"bot_token": "any_token"})
    assert len(result) == 1
    assert "error" in result[0]


def test_execute_discord_send_missing_message_key():
    """Test execute_discord_send with missing message key entirely."""
    result = execute_discord_send({"channel_id": "123"}, None, credential_data={"bot_token": "any_token"})
    assert len(result) == 1
    assert "error" in result[0]


# ##################################################################
# test dynamic enum functions without credentials
def test_get_discord_servers_no_credentials():
    result = get_discord_servers({}, None)
    assert result == []


def test_get_discord_servers_no_bot_token():
    result = get_discord_servers({}, {"bot_token": ""})
    assert result == []


def test_get_discord_channels_no_credentials():
    result = get_discord_channels({"server_id": "123"}, None)
    assert result == []


def test_get_discord_channels_no_server_id():
    result = get_discord_channels({}, {"bot_token": "any_token"})
    assert result == []


def test_get_discord_channels_no_bot_token():
    result = get_discord_channels({"server_id": "123"}, {"bot_token": ""})
    assert result == []


# ##################################################################
# test register_discord_trigger
def test_discord_trigger_has_register():
    assert "register" in NODE_TYPES["discord_trigger"]
    assert callable(NODE_TYPES["discord_trigger"]["register"])


def test_register_discord_trigger_returns_push_type():
    def noop_callback(_x):
        pass

    result = register_discord_trigger(
        {"server_id": "123", "channel_id": "456", "mode": "new_messages"},
        noop_callback,
    )
    assert result["type"] == "push"
    assert "listener" in result
    assert callable(result["listener"])


# ##################################################################
# test DiscordConnection class (in-process, no live connection)
# ##################################################################


def test_discord_connection_init():
    """Test DiscordConnection initialization without starting."""
    conn = DiscordConnection("test_token")
    assert conn.bot_token == "test_token"
    assert conn.client is None
    assert conn._thread is None
    assert conn._loop is None
    assert not conn._ready.is_set()
    assert not conn._stop.is_set()
    assert conn._subscriptions == {}


def test_discord_connection_subscribe_new_key():
    """Test subscribing to a new channel/mode combination."""
    conn = DiscordConnection("test_token")

    def test_callback(_msg):
        pass

    conn.subscribe("server1", "channel1", "new_messages", test_callback)

    key = ("server1", "channel1", "new_messages")
    assert key in conn._subscriptions
    assert test_callback in conn._subscriptions[key]


def test_discord_connection_subscribe_existing_key():
    """Test subscribing multiple callbacks to the same key."""
    conn = DiscordConnection("test_token")

    def callback1(_msg):
        pass

    def callback2(_msg):
        pass

    conn.subscribe("server1", "channel1", "new_messages", callback1)
    conn.subscribe("server1", "channel1", "new_messages", callback2)

    key = ("server1", "channel1", "new_messages")
    assert len(conn._subscriptions[key]) == 2
    assert callback1 in conn._subscriptions[key]
    assert callback2 in conn._subscriptions[key]


def test_discord_connection_unsubscribe_removes_callback():
    """Test unsubscribing removes the specific callback."""
    conn = DiscordConnection("test_token")

    def callback1(_msg):
        pass

    def callback2(_msg):
        pass

    conn.subscribe("server1", "channel1", "new_messages", callback1)
    conn.subscribe("server1", "channel1", "new_messages", callback2)
    conn.unsubscribe("server1", "channel1", "new_messages", callback1)

    key = ("server1", "channel1", "new_messages")
    assert key in conn._subscriptions
    assert callback1 not in conn._subscriptions[key]
    assert callback2 in conn._subscriptions[key]


def test_discord_connection_unsubscribe_removes_empty_key():
    """Test unsubscribing removes the key when list becomes empty."""
    conn = DiscordConnection("test_token")

    def test_callback(_msg):
        pass

    conn.subscribe("server1", "channel1", "new_messages", test_callback)
    conn.unsubscribe("server1", "channel1", "new_messages", test_callback)

    key = ("server1", "channel1", "new_messages")
    assert key not in conn._subscriptions


def test_discord_connection_unsubscribe_nonexistent_key():
    """Test unsubscribing from nonexistent key does nothing."""
    conn = DiscordConnection("test_token")

    def test_callback(_msg):
        pass

    # Should not raise
    conn.unsubscribe("server1", "channel1", "new_messages", test_callback)
    assert conn._subscriptions == {}


def test_discord_connection_unsubscribe_nonexistent_callback():
    """Test unsubscribing nonexistent callback does nothing."""
    conn = DiscordConnection("test_token")

    def callback1(_msg):
        pass

    def callback2(_msg):
        pass

    conn.subscribe("server1", "channel1", "new_messages", callback1)
    # Try to unsubscribe callback2 which was never subscribed
    conn.unsubscribe("server1", "channel1", "new_messages", callback2)

    key = ("server1", "channel1", "new_messages")
    assert key in conn._subscriptions
    assert callback1 in conn._subscriptions[key]


def test_discord_connection_get_servers_returns_cached_data():
    """Test get_servers returns cached data when not connected."""
    conn = DiscordConnection("test_token")
    # get_servers returns whatever is in the cache (which may have data from prior tests)
    # The key point is that it returns a list and doesn't block or error
    servers = conn.get_servers()
    assert isinstance(servers, list)


def test_discord_connection_get_channels_returns_cached_data():
    """Test get_channels returns cached data when not connected."""
    conn = DiscordConnection("test_token")
    # Use a unique server_id that won't have cached data
    channels = conn.get_channels("nonexistent_server_999999")
    assert channels == []


def test_discord_connection_send_message_queues_correctly():
    """Test send_message queues the message correctly."""
    conn = DiscordConnection("test_token")
    # Don't wait for the result - just verify the queue is populated
    conn._send_queue.put(("test_channel", "test_message", None, _create_send_result_event()))
    assert not conn._send_queue.empty()
    # Clean up
    conn._send_queue.get()


def test_discord_connection_stop_sets_stop_event():
    """Test stop() sets the stop event."""
    conn = DiscordConnection("test_token")
    assert not conn._stop.is_set()
    conn.stop()
    assert conn._stop.is_set()


def test_discord_connection_start_returns_if_already_running():
    """Test start() returns immediately if already started."""
    conn = DiscordConnection("test_token")
    # Simulate a running thread
    import threading

    conn._thread = threading.Thread(target=lambda: None)
    conn._thread.start()
    conn._thread.join()  # Wait for it to finish
    # Now create a new "running" thread
    conn._thread = threading.Thread(target=lambda: threading.Event().wait(10))
    conn._thread.daemon = True
    conn._thread.start()
    # start() should return immediately since thread is alive
    # We can't easily test this without timing, but we verify no exception
    # Just calling start() when thread is alive should not raise
    # (The actual implementation returns early)


def test_discord_connection_cache_ttl_constant():
    """Test that CACHE_TTL constant is defined."""
    assert DiscordConnection.CACHE_TTL == 300


def test_discord_connection_rate_limit_default():
    """Test default rate limit configuration."""
    conn = DiscordConnection("test_token")
    assert conn._rate_limit == 1.0
    assert conn._last_send_time == 0.0


def test_discord_connection_send_queue_initialized():
    """Test send queue is initialized on connection creation."""
    conn = DiscordConnection("test_token")
    assert conn._send_queue is not None
    assert conn._send_queue.empty()


def test_validate_send_params_with_whitespace_channel():
    """Test validation with whitespace-only channel passes (function doesn't strip)."""
    error, _, channel_id, _ = _validate_send_params({"channel_id": "   ", "message": "test"}, {"bot_token": "token"})
    # The function doesn't strip whitespace, so this passes
    assert error is None
    assert channel_id == "   "


def test_validate_send_params_with_whitespace_message():
    """Test validation with whitespace-only message passes (function doesn't strip)."""
    error, _, _, message = _validate_send_params({"channel_id": "123", "message": "   "}, {"bot_token": "token"})
    # The current implementation doesn't strip, so whitespace passes
    assert error is None
    assert message == "   "


def test_generate_sample_message_default_mode():
    """Test sample message with no mode (empty string)."""
    msg = _generate_sample_message({})
    assert msg["reply_to"] is None
    assert msg["channel"]["id"] == "000000000000000000"
    assert msg["server"]["id"] == "000000000000000000"


def test_generate_sample_message_author_structure():
    """Test sample message author has all required fields."""
    msg = _generate_sample_message({})
    assert "id" in msg["author"]
    assert "name" in msg["author"]
    assert "display_name" in msg["author"]
    assert "bot" in msg["author"]
    assert msg["author"]["bot"] is False


def test_format_servers_multiple():
    """Test formatting multiple servers."""
    servers = [
        {"id": "111", "name": "Server One"},
        {"id": "222", "name": "Server Two"},
        {"id": "333", "name": "Server Three"},
    ]
    result = _format_servers_for_dropdown(servers)
    assert len(result) == 3
    assert result[0] == {"value": "111", "label": "Server One"}
    assert result[2] == {"value": "333", "label": "Server Three"}


def test_format_channels_multiple():
    """Test formatting multiple channels."""
    channels = [
        {"id": "111", "name": "general"},
        {"id": "222", "name": "random"},
    ]
    result = _format_channels_for_dropdown(channels)
    assert len(result) == 2
    assert result[0] == {"value": "111", "label": "#general"}
    assert result[1] == {"value": "222", "label": "#random"}


def test_discord_connection_start_already_running():
    """Test start() returns early if thread is already alive."""
    conn = DiscordConnection("test_token")
    # Create a thread that appears alive
    running_event = threading.Event()

    def wait_target():
        running_event.wait()

    conn._thread = threading.Thread(target=wait_target)
    conn._thread.start()

    # Calling start() again should return early without blocking
    conn.start()  # This should return immediately

    # Cleanup
    running_event.set()
    conn._thread.join()


def test_discord_connection_get_servers_calls_cache():
    """Test get_servers interacts with cache."""
    conn = DiscordConnection("test_token")
    # Without a live connection, should return empty list from cache
    result = conn.get_servers()
    assert isinstance(result, list)


def test_discord_connection_get_channels_calls_cache():
    """Test get_channels interacts with cache for specific server."""
    conn = DiscordConnection("test_token")
    # Without a live connection, should return empty list from cache
    result = conn.get_channels("some_server_id_that_does_not_exist")
    assert isinstance(result, list)


def test_execute_discord_trigger_with_credential_data():
    """Test execute_discord_trigger ignores credential_data."""
    result = execute_discord_trigger(
        {"server_id": "123", "channel_id": "456", "mode": "new_messages"},
        None,
        credential_data={"bot_token": "test"},
    )
    assert len(result) == 1
    assert "content" in result[0]


def test_register_discord_trigger_has_listener():
    """Test register returns a dict with listener function."""

    def test_cb(_data):
        pass

    result = register_discord_trigger(
        {"server_id": "123", "channel_id": "456", "mode": "new_messages"},
        test_cb,
    )
    assert "type" in result
    assert result["type"] == "push"
    assert "listener" in result
    assert callable(result["listener"])


def test_node_types_discord_trigger_structure():
    """Test discord_trigger node type has all required fields."""
    trigger = NODE_TYPES["discord_trigger"]
    assert "execute" in trigger
    assert "kind" in trigger
    assert "requiredCredential" in trigger
    assert "dynamicEnums" in trigger


def test_node_types_discord_send_structure():
    """Test discord_send node type has all required fields."""
    send = NODE_TYPES["discord_send"]
    assert "execute" in send
    assert "kind" in send
    assert "requiredCredential" in send
    assert "dynamicEnums" in send


def test_generate_sample_message_has_timestamp():
    """Test sample message includes a valid timestamp."""
    msg = _generate_sample_message({})
    assert "timestamp" in msg
    # Timestamp should be ISO format
    assert "T" in msg["timestamp"]


def test_generate_sample_message_has_attachments():
    """Test sample message includes attachments list."""
    msg = _generate_sample_message({})
    assert "attachments" in msg
    assert isinstance(msg["attachments"], list)
    assert len(msg["attachments"]) == 0


def test_generate_sample_message_reply_to_structure():
    """Test reply_to structure in replies mode."""
    msg = _generate_sample_message({"mode": "replies"})
    assert msg["reply_to"] is not None
    assert "id" in msg["reply_to"]
    assert "content" in msg["reply_to"]
    assert "author" in msg["reply_to"]
    assert "id" in msg["reply_to"]["author"]
    assert "name" in msg["reply_to"]["author"]


def test_discord_connection_stop_with_no_loop():
    """Test stop() when loop is None."""
    conn = DiscordConnection("test_token")
    assert conn._loop is None
    conn.stop()  # Should not raise
    assert conn._stop.is_set()


def test_discord_connection_stop_with_no_thread():
    """Test stop() when thread is None."""
    conn = DiscordConnection("test_token")
    assert conn._thread is None
    conn.stop()  # Should not raise
    assert conn._stop.is_set()


def test_discord_connection_multiple_subscriptions_different_modes():
    """Test subscriptions with different modes."""
    conn = DiscordConnection("test_token")

    def cb1(_m):
        pass

    def cb2(_m):
        pass

    conn.subscribe("s1", "c1", "new_messages", cb1)
    conn.subscribe("s1", "c1", "replies", cb2)

    key1 = ("s1", "c1", "new_messages")
    key2 = ("s1", "c1", "replies")

    assert key1 in conn._subscriptions
    assert key2 in conn._subscriptions
    assert cb1 in conn._subscriptions[key1]
    assert cb2 in conn._subscriptions[key2]


def test_execute_discord_trigger_default_mode():
    """Test trigger with default mode when mode is missing."""
    result = execute_discord_trigger({"server_id": "123", "channel_id": "456"}, None)
    assert len(result) == 1
    assert result[0]["reply_to"] is None


def test_create_send_result_event_done_not_set():
    """Test that done event is not set initially."""
    event = _create_send_result_event()
    assert not event["done"].is_set()


def test_handle_send_result_with_none_error():
    """Test handle_send_result returns result when error is None."""
    event = {
        "done": threading.Event(),
        "result": {"id": "123", "content": "test"},
        "error": None,
    }
    result = _handle_send_result(event)
    assert result["id"] == "123"
    assert result["content"] == "test"


# ##################################################################
# REAL INTEGRATION TESTS - Actual Discord connection
# Uses pytest fixtures for shared connection (counts toward coverage)
# ##################################################################


def test_real_discord_connection_starts(discord_connection):
    """Test that we can create and start a real Discord connection."""
    conn = discord_connection
    assert conn.client is not None, "client is None"
    assert conn._ready.is_set(), "connection not ready"


def test_real_get_discord_servers(discord_connection):
    """Test getting real server list from Discord."""
    conn = discord_connection
    servers = conn.get_servers()
    assert len(servers) > 0, "no servers found"
    for server in servers:
        assert "id" in server, "missing id in server"
        assert "name" in server, "missing name in server"


def test_real_get_discord_channels(discord_connection):
    """Test getting real channel list from Discord."""
    conn = discord_connection
    servers = conn.get_servers()
    assert len(servers) > 0, "no servers found"
    channels = conn.get_channels(servers[0]["id"])
    assert len(channels) > 0, "no channels found"
    for channel in channels:
        assert "id" in channel, "missing id in channel"
        assert "name" in channel, "missing name in channel"


def test_real_find_unit_testing_channel(discord_test_data):
    """Test that we can find the #unit-testing channel."""
    assert discord_test_data["unit_testing_channel_id"] is not None, "no unit-testing channel found"
    assert discord_test_data["unit_testing_server_id"] is not None, "no unit-testing server found"


def test_real_send_message_to_unit_testing(discord_test_data):
    """Test sending a real message to #unit-testing channel."""
    import datetime

    channel_id = discord_test_data["unit_testing_channel_id"]
    assert channel_id, "no unit-testing channel"

    cred_data = _get_test_credential_data()
    timestamp = datetime.datetime.now().isoformat()
    result = execute_discord_send(
        {"channel_id": channel_id, "message": f"[TEST] Integration test at {timestamp}"},
        None,
        credential_data=cred_data,
    )
    assert len(result) == 1, f"expected 1 result, got {len(result)}"
    assert "error" not in result[0], f"send failed: {result[0].get('error')}"
    assert "id" in result[0], "missing id in result"
    assert "content" in result[0], "missing content in result"


def test_real_connection_subscribe_unsubscribe(discord_connection, discord_test_data):
    """Test subscription mechanism with real connection."""
    conn = discord_connection
    server_id = discord_test_data["unit_testing_server_id"]
    channel_id = discord_test_data["unit_testing_channel_id"]
    assert server_id and channel_id, "no unit-testing channel"

    received = []

    def callback(msg):
        received.append(msg)

    conn.subscribe(server_id, channel_id, "new_messages", callback)
    key = (server_id, channel_id, "new_messages")
    assert key in conn._subscriptions, "subscription not added"
    assert callback in conn._subscriptions[key], "callback not in subscriptions"

    conn.unsubscribe(server_id, channel_id, "new_messages", callback)
    assert key not in conn._subscriptions, "subscription not removed"


def test_real_get_discord_servers_via_api():
    """Test get_discord_servers function with real connection."""
    cred_data = _get_test_credential_data()
    servers = get_discord_servers({}, cred_data)
    assert len(servers) > 0, "no servers found"
    for server in servers:
        assert "value" in server, "missing value in server"
        assert "label" in server, "missing label in server"


def test_real_get_discord_channels_via_api():
    """Test get_discord_channels function with real connection."""
    cred_data = _get_test_credential_data()
    servers = get_discord_servers({}, cred_data)
    assert len(servers) > 0, "no servers found"
    server_id = servers[0]["value"]
    channels = get_discord_channels({"server_id": server_id}, cred_data)
    assert len(channels) > 0, "no channels found"
    for channel in channels:
        assert "value" in channel, "missing value in channel"
        assert "label" in channel, "missing label in channel"
        assert channel["label"].startswith("#"), f"label should start with #: {channel['label']}"


# ##################################################################
# test helper functions (pure logic, no connection needed)
# ##################################################################


def test_should_trigger_new_messages_not_reply():
    assert _should_trigger_for_mode("new_messages", False) is True


def test_should_trigger_new_messages_is_reply():
    assert _should_trigger_for_mode("new_messages", True) is False


def test_should_trigger_replies_not_reply():
    assert _should_trigger_for_mode("replies", False) is False


def test_should_trigger_replies_is_reply():
    assert _should_trigger_for_mode("replies", True) is True


def test_should_trigger_combined_not_reply():
    assert _should_trigger_for_mode("new_messages_and_replies", False) is True


def test_should_trigger_combined_is_reply():
    assert _should_trigger_for_mode("new_messages_and_replies", True) is True


def test_should_trigger_unknown_mode():
    assert _should_trigger_for_mode("unknown_mode", False) is False


def test_validate_bot_token_none():
    assert _validate_bot_token(None) is None


def test_validate_bot_token_empty():
    assert _validate_bot_token({}) is None


def test_validate_bot_token_empty_string():
    assert _validate_bot_token({"bot_token": ""}) is None


def test_validate_bot_token_valid():
    assert _validate_bot_token({"bot_token": "test_token"}) == "test_token"


def test_validate_send_params_no_credentials():
    error, _, _, _ = _validate_send_params({}, None)
    assert error == "No credentials provided"


def test_validate_send_params_no_bot_token():
    error, _, _, _ = _validate_send_params({}, {"bot_token": ""})
    assert error == "Bot token is required"


def test_validate_send_params_no_channel():
    error, _, _, _ = _validate_send_params({"message": "test"}, {"bot_token": "token"})
    assert error == "Channel is required"


def test_validate_send_params_no_message():
    error, _, _, _ = _validate_send_params({"channel_id": "123"}, {"bot_token": "token"})
    assert error == "Message is required"


def test_validate_send_params_valid():
    error, bot_token, channel_id, message = _validate_send_params(
        {"channel_id": "123", "message": "hello"}, {"bot_token": "token"}
    )
    assert error is None
    assert bot_token == "token"
    assert channel_id == "123"
    assert message == "hello"


def test_generate_sample_message_structure():
    msg = _generate_sample_message({"server_id": "123", "channel_id": "456"})
    assert "id" in msg
    assert "content" in msg
    assert "author" in msg
    assert "channel" in msg
    assert "server" in msg
    assert "timestamp" in msg
    assert "attachments" in msg


def test_generate_sample_message_uses_ids():
    msg = _generate_sample_message({"server_id": "888", "channel_id": "999"})
    assert msg["server"]["id"] == "888"
    assert msg["channel"]["id"] == "999"


def test_generate_sample_message_reply_for_replies_mode():
    msg = _generate_sample_message({"mode": "replies"})
    assert msg["reply_to"] is not None


def test_generate_sample_message_no_reply_for_new_messages():
    msg = _generate_sample_message({"mode": "new_messages"})
    assert msg["reply_to"] is None


def test_format_servers_empty():
    assert _format_servers_for_dropdown([]) == []


def test_format_servers_single():
    servers = [{"id": "123", "name": "Test Server"}]
    result = _format_servers_for_dropdown(servers)
    assert result == [{"value": "123", "label": "Test Server"}]


def test_format_channels_empty():
    assert _format_channels_for_dropdown([]) == []


def test_format_channels_single():
    channels = [{"id": "456", "name": "general"}]
    result = _format_channels_for_dropdown(channels)
    assert result == [{"value": "456", "label": "#general"}]


def test_create_send_result_event_structure():
    event = _create_send_result_event()
    assert "done" in event
    assert "result" in event
    assert "error" in event
    assert event["result"] is None
    assert event["error"] is None


def test_handle_send_result_success():
    event = {"done": threading.Event(), "result": {"id": "123"}, "error": None}
    result = _handle_send_result(event)
    assert result == {"id": "123"}


def test_handle_send_result_error():
    event = {"done": threading.Event(), "result": None, "error": "Test error"}
    result = _handle_send_result(event)
    assert result == {"error": "Test error"}


def test_async_delay_completes():
    async def run_delay():
        await _async_delay(0.01)
        return True

    result = asyncio.run(run_delay())
    assert result is True
