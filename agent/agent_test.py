"""Tests for the dazflow2 agent."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from agent import DazflowAgent


# ##################################################################
# test agent initialization
# verifies agent constructor sets correct attributes
def test_agent_init():
    agent = DazflowAgent("http://localhost:5000", "test-agent", "test-secret")
    assert agent.server_url == "http://localhost:5000"
    assert agent.name == "test-agent"
    assert agent.secret == "test-secret"
    assert agent.running is True
    assert agent.connected is False
    assert agent.ws is None
    assert agent._reconnect_delay == DazflowAgent.RECONNECT_DELAY


# ##################################################################
# test websocket url generation from http url
# converts http to ws protocol
def test_agent_get_ws_url_http():
    agent = DazflowAgent("http://localhost:5000", "test-agent", "secret")
    assert agent._get_ws_url() == "ws://localhost:5000/ws/agent/test-agent/secret"


# ##################################################################
# test websocket url generation from https url
# converts https to wss protocol
def test_agent_get_ws_url_https():
    agent = DazflowAgent("https://example.com:8000", "test-agent", "secret")
    assert agent._get_ws_url() == "wss://example.com:8000/ws/agent/test-agent/secret"


# ##################################################################
# test websocket url generation from ws url
# preserves ws protocol
def test_agent_get_ws_url_ws():
    agent = DazflowAgent("ws://localhost:5000", "test-agent", "secret")
    assert agent._get_ws_url() == "ws://localhost:5000/ws/agent/test-agent/secret"


# ##################################################################
# test websocket url generation from bare url
# adds ws protocol to bare url
def test_agent_get_ws_url_bare():
    agent = DazflowAgent("localhost:5000", "test-agent", "secret")
    assert agent._get_ws_url() == "ws://localhost:5000/ws/agent/test-agent/secret"


# ##################################################################
# test websocket url generation with spaces in name
# verifies name is url-encoded
def test_agent_get_ws_url_with_spaces():
    agent = DazflowAgent("http://localhost:5000", "mac mini", "secret")
    assert agent._get_ws_url() == "ws://localhost:5000/ws/agent/mac%20mini/secret"


# ##################################################################
# test timestamp format
# verifies timestamp includes date and time in utc
def test_agent_timestamp_format():
    agent = DazflowAgent("http://localhost:5000", "test-agent", "secret")
    timestamp = agent._timestamp()
    # Should match format: YYYY-MM-DD HH:MM:SS
    assert len(timestamp) == 19
    assert timestamp[4] == "-"
    assert timestamp[7] == "-"
    assert timestamp[10] == " "
    assert timestamp[13] == ":"
    assert timestamp[16] == ":"


# ##################################################################
# test agent version constant
# verifies version string is defined
def test_agent_version():
    assert hasattr(DazflowAgent, "VERSION")
    assert isinstance(DazflowAgent.VERSION, str)
    assert len(DazflowAgent.VERSION) > 0


# ##################################################################
# test upgrade exit code constant
# verifies upgrade exit code is defined
def test_upgrade_exit_code():
    assert hasattr(DazflowAgent, "UPGRADE_EXIT_CODE")
    assert DazflowAgent.UPGRADE_EXIT_CODE == 42


# ##################################################################
# LogBuffer Tests
# ##################################################################


# ##################################################################
# test log buffer initialization
# verifies buffer initializes with correct defaults
def test_log_buffer_init():
    from agent import LogBuffer

    buffer = LogBuffer(max_lines=50, flush_interval=1.0)
    assert buffer._max_lines == 50
    assert buffer._flush_interval == 1.0
    assert isinstance(buffer._buffer, list)
    assert len(buffer._buffer) == 0


# ##################################################################
# test adding log line to buffer
# adds single log line and verifies it's stored
@pytest.mark.asyncio
async def test_log_buffer_add():
    from agent import LogBuffer

    buffer = LogBuffer()
    await buffer.add("task-123", "Test log line")

    assert len(buffer._buffer) == 1
    log_entry = buffer._buffer[0]
    assert log_entry["task_id"] == "task-123"
    assert log_entry["line"] == "Test log line"
    assert "timestamp" in log_entry
    # Verify timestamp is ISO format
    dt = datetime.fromisoformat(log_entry["timestamp"].replace("Z", "+00:00"))
    assert dt is not None


# ##################################################################
# test adding multiple log lines
# adds several lines and verifies order
@pytest.mark.asyncio
async def test_log_buffer_add_multiple():
    from agent import LogBuffer

    buffer = LogBuffer()
    await buffer.add("task-1", "Line 1")
    await buffer.add("task-1", "Line 2")
    await buffer.add("task-2", "Line 3")

    assert len(buffer._buffer) == 3
    assert buffer._buffer[0]["line"] == "Line 1"
    assert buffer._buffer[1]["line"] == "Line 2"
    assert buffer._buffer[2]["line"] == "Line 3"
    assert buffer._buffer[2]["task_id"] == "task-2"


# ##################################################################
# test flushing logs to websocket
# sends buffered logs and clears buffer
@pytest.mark.asyncio
async def test_log_buffer_flush():
    from agent import LogBuffer

    buffer = LogBuffer()
    await buffer.add("task-123", "Log 1")
    await buffer.add("task-123", "Log 2")

    # Mock websocket
    sent_messages = []

    class MockWebSocket:
        async def send(self, message):
            sent_messages.append(message)

    ws = MockWebSocket()
    await buffer.flush(ws)

    # Verify message was sent
    assert len(sent_messages) == 1
    msg = json.loads(sent_messages[0])
    assert msg["type"] == "task_progress"
    assert msg["task_id"] == "task-123"
    assert len(msg["logs"]) == 2
    assert msg["logs"][0]["line"] == "Log 1"
    assert msg["logs"][1]["line"] == "Log 2"

    # Buffer should be empty
    assert len(buffer._buffer) == 0


# ##################################################################
# test flush with empty buffer
# flushing empty buffer should not send anything
@pytest.mark.asyncio
async def test_log_buffer_flush_empty():
    from agent import LogBuffer

    buffer = LogBuffer()

    sent_messages = []

    class MockWebSocket:
        async def send(self, message):
            sent_messages.append(message)

    ws = MockWebSocket()
    await buffer.flush(ws)

    # Should not send anything
    assert len(sent_messages) == 0


# ##################################################################
# test shipping loop flushes periodically
# background task should flush logs at intervals
@pytest.mark.asyncio
async def test_log_buffer_shipping_loop():
    from agent import LogBuffer

    buffer = LogBuffer(flush_interval=0.1)  # 100ms

    sent_messages = []

    class MockWebSocket:
        async def send(self, message):
            sent_messages.append(message)

    ws = MockWebSocket()

    # Start shipping loop
    shipping_task = asyncio.create_task(buffer.run_shipping_loop(ws))

    # Add some logs
    await buffer.add("task-123", "Test log")

    # Wait for flush
    await asyncio.sleep(0.15)

    # Should have flushed
    assert len(sent_messages) >= 1

    # Clean up
    shipping_task.cancel()
    try:
        await shipping_task
    except asyncio.CancelledError:
        pass


# ##################################################################
# test buffer flushes when max lines reached
# automatic flush when buffer is full
@pytest.mark.asyncio
async def test_log_buffer_auto_flush_on_max_lines():
    from agent import LogBuffer

    buffer = LogBuffer(max_lines=3, flush_interval=10.0)  # Long interval

    sent_messages = []

    class MockWebSocket:
        async def send(self, message):
            sent_messages.append(message)

    ws = MockWebSocket()

    # Add logs up to max
    await buffer.add("task-1", "Line 1")
    await buffer.add("task-1", "Line 2")
    # Buffer should not flush yet
    assert len(buffer._buffer) == 2

    # Add one more - should trigger flush via add_and_maybe_flush
    await buffer.add_and_maybe_flush("task-1", "Line 3", ws)

    # Should have flushed
    assert len(sent_messages) == 1
    msg = json.loads(sent_messages[0])
    assert len(msg["logs"]) == 3
    assert len(buffer._buffer) == 0


# ##################################################################
# test buffer handles multiple tasks
# logs from different tasks should all be buffered
@pytest.mark.asyncio
async def test_log_buffer_multiple_tasks():
    from agent import LogBuffer

    buffer = LogBuffer()
    await buffer.add("task-1", "Task 1 log")
    await buffer.add("task-2", "Task 2 log")
    await buffer.add("task-1", "Task 1 again")

    assert len(buffer._buffer) == 3
    assert buffer._buffer[0]["task_id"] == "task-1"
    assert buffer._buffer[1]["task_id"] == "task-2"
    assert buffer._buffer[2]["task_id"] == "task-1"


# ##################################################################
# test concurrent log additions are safe
# multiple async tasks adding logs should work
@pytest.mark.asyncio
async def test_log_buffer_concurrent_adds():
    from agent import LogBuffer

    buffer = LogBuffer()

    async def add_logs(task_id, count):
        for i in range(count):
            await buffer.add(task_id, f"Log {i}")

    # Add logs concurrently
    await asyncio.gather(add_logs("task-1", 10), add_logs("task-2", 10), add_logs("task-3", 10))

    # Should have all 30 logs
    assert len(buffer._buffer) == 30
