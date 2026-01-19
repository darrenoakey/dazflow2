"""Tests for the dazflow2 agent."""

import sys
from pathlib import Path

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
