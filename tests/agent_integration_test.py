"""Integration tests for agent-server communication.

These tests spawn real server and agent processes to verify
the full communication flow works correctly.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

# Test configuration
TEST_PORT = 5099
TEST_SERVER_URL = f"http://localhost:{TEST_PORT}"


@pytest.fixture(scope="module")
def test_server(tmp_path_factory):
    """Start a test server on a separate port with isolated data."""
    data_dir = tmp_path_factory.mktemp("dazflow_test")

    # Create workflows directory (required by server)
    (data_dir / "workflows").mkdir()

    # Get project root (parent of tests directory)
    project_root = Path(__file__).parent.parent

    # Start server process
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", str(TEST_PORT)],
        cwd=str(project_root),
        env={
            **dict(os.environ),
            "DAZFLOW_DATA_DIR": str(data_dir),
            "DAZFLOW_PORT": str(TEST_PORT),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to be ready
    max_wait = 30
    for _ in range(max_wait):
        try:
            response = requests.get(f"{TEST_SERVER_URL}/health", timeout=1)
            if response.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    else:
        server_proc.kill()
        raise RuntimeError("Server failed to start")

    yield {
        "url": TEST_SERVER_URL,
        "data_dir": data_dir,
        "process": server_proc,
    }

    # Cleanup
    server_proc.terminate()
    server_proc.wait(timeout=5)


@pytest.fixture
def test_agent(test_server):
    """Create a test agent and return its credentials."""
    # Create agent via API
    response = requests.post(f"{test_server['url']}/api/agents", json={"name": f"test-agent-{time.time_ns()}"})
    assert response.status_code == 200
    data = response.json()

    return {
        "name": data["name"],
        "secret": data["secret"],
        "server_url": test_server["url"],
    }


def test_agent_connects_to_server(test_server, test_agent):
    """Test that an agent can connect to the server."""
    # Get project root for agent script path
    project_root = Path(__file__).parent.parent

    # Start agent process (use -u for unbuffered output for debugging)
    agent_proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            str(project_root / "agent" / "agent.py"),
            "--server",
            test_agent["server_url"],
            "--name",
            test_agent["name"],
            "--secret",
            test_agent["secret"],
        ],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        # Wait for agent to connect
        max_wait = 15
        agent_data = None
        for i in range(max_wait):
            response = requests.get(f"{test_server['url']}/api/agents/{test_agent['name']}")
            if response.status_code == 200:
                agent_data = response.json()
                if agent_data.get("status") == "online":
                    break
            # For first few iterations, sleep less to catch fast connections
            time.sleep(0.5 if i < 5 else 1)
        else:
            # If agent didn't come online, get its output for debugging
            agent_proc.terminate()
            output, _ = agent_proc.communicate(timeout=5)
            pytest.fail(
                f"Agent did not come online after {max_wait} seconds. Agent output:\n{output.decode()}\n\nLast agent data: {agent_data}"
            )

        # Verify agent is online
        assert agent_data["status"] == "online"
        assert agent_data["name"] == test_agent["name"]

    finally:
        if agent_proc.poll() is None:
            agent_proc.terminate()
            agent_proc.wait(timeout=5)


def test_agent_goes_offline_on_disconnect(test_server, test_agent):
    """Test that agent status changes to offline when it disconnects."""
    # Get project root for agent script path
    project_root = Path(__file__).parent.parent

    # Start agent (use -u for unbuffered output for debugging)
    agent_proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            str(project_root / "agent" / "agent.py"),
            "--server",
            test_agent["server_url"],
            "--name",
            test_agent["name"],
            "--secret",
            test_agent["secret"],
        ],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        # Wait for agent to come online
        max_wait = 10
        for _ in range(max_wait):
            response = requests.get(f"{test_server['url']}/api/agents/{test_agent['name']}")
            if response.status_code == 200:
                if response.json().get("status") == "online":
                    break
            time.sleep(1)

        # Kill the agent
        agent_proc.terminate()
        agent_proc.wait(timeout=5)

        # Wait for status to change to offline
        max_wait = 10
        for _ in range(max_wait):
            response = requests.get(f"{test_server['url']}/api/agents/{test_agent['name']}")
            if response.status_code == 200:
                if response.json().get("status") == "offline":
                    break
            time.sleep(1)
        else:
            pytest.fail("Agent did not go offline")

        assert response.json()["status"] == "offline"

    finally:
        if agent_proc.poll() is None:
            agent_proc.kill()


def test_agent_invalid_secret_rejected(test_server, test_agent):
    """Test that an agent with invalid secret is rejected."""
    # Get project root for agent script path
    project_root = Path(__file__).parent.parent

    # Start agent with wrong secret (use -u for unbuffered output for debugging)
    agent_proc = subprocess.Popen(
        [
            sys.executable,
            "-u",
            str(project_root / "agent" / "agent.py"),
            "--server",
            test_agent["server_url"],
            "--name",
            test_agent["name"],
            "--secret",
            "wrong-secret",
        ],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        # Wait a bit and check agent is NOT online
        time.sleep(3)

        response = requests.get(f"{test_server['url']}/api/agents/{test_agent['name']}")
        assert response.status_code == 200
        assert response.json().get("status") == "offline"

    finally:
        agent_proc.terminate()
        agent_proc.wait(timeout=5)


def test_builtin_agent_connects_on_startup(test_server):
    """Test that the built-in agent is created and connects when server starts."""
    # Wait a moment for built-in agent to start
    time.sleep(2)

    # Check that built-in agent exists and is online
    response = requests.get(f"{test_server['url']}/api/agents/built-in")
    assert response.status_code == 200

    agent_data = response.json()
    assert agent_data["name"] == "built-in"
    assert agent_data["enabled"] is True

    # Built-in agent should eventually come online (give it some time)
    max_wait = 10
    for _ in range(max_wait):
        response = requests.get(f"{test_server['url']}/api/agents/built-in")
        if response.status_code == 200:
            agent_data = response.json()
            if agent_data.get("status") == "online":
                break
        time.sleep(1)

    # Verify it came online
    assert agent_data["status"] == "online"


def test_builtin_agent_persists_across_restarts(tmp_path_factory):
    """Test that built-in agent secret persists across server restarts."""
    # Use a different port than the module-scoped test_server fixture
    # to avoid port conflicts when both are alive simultaneously
    restart_port = TEST_PORT + 1
    restart_url = f"http://localhost:{restart_port}"

    data_dir = tmp_path_factory.mktemp("dazflow_test_restart")
    (data_dir / "workflows").mkdir()
    project_root = Path(__file__).parent.parent

    # Start server first time
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", str(restart_port)],
        cwd=str(project_root),
        env={
            **dict(os.environ),
            "DAZFLOW_DATA_DIR": str(data_dir),
            "DAZFLOW_PORT": str(restart_port),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for server to be ready
        for _ in range(30):
            try:
                response = requests.get(f"{restart_url}/health", timeout=1)
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)

        # Wait for built-in agent to come online
        time.sleep(2)

        # Verify built-in agent exists
        response = requests.get(f"{restart_url}/api/agents/built-in")
        assert response.status_code == 200

        # Verify secret file was created
        secret_file = data_dir / "builtin_agent_secret"
        assert secret_file.exists()
        original_secret = secret_file.read_text()

    finally:
        server_proc.terminate()
        server_proc.wait(timeout=5)

    # Start server second time with same data directory
    server_proc2 = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", str(restart_port)],
        cwd=str(project_root),
        env={
            **dict(os.environ),
            "DAZFLOW_DATA_DIR": str(data_dir),
            "DAZFLOW_PORT": str(restart_port),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for server to be ready
        for _ in range(30):
            try:
                response = requests.get(f"{restart_url}/health", timeout=1)
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(1)

        # Wait for built-in agent
        time.sleep(2)

        # Verify built-in agent still exists and secret hasn't changed
        response = requests.get(f"{restart_url}/api/agents/built-in")
        assert response.status_code == 200

        # Verify secret is the same
        assert secret_file.exists()
        new_secret = secret_file.read_text()
        assert new_secret == original_secret

    finally:
        server_proc2.terminate()
        server_proc2.wait(timeout=5)


# ##################################################################
# integration tests for agent-server communication
# tests verify real processes communicate correctly with proper authentication
# and status tracking
