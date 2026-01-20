"""Tests for the agent updater shim."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from agent_updater import UPGRADE_EXIT_CODE, download_new_agent, parse_args


# ##################################################################
# test download new agent
# verifies download_new_agent fetches file from correct url
def test_download_new_agent():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent_dir = Path(tmpdir)

        # Mock urllib.request.urlretrieve
        with patch("agent_updater.urllib.request.urlretrieve") as mock_retrieve:
            with patch("agent_updater.Path") as mock_path:
                # Make Path(__file__).parent return our temp dir
                mock_path.return_value.parent = agent_dir

                download_new_agent("http://localhost:5000")

                # Verify urlretrieve was called with correct args
                mock_retrieve.assert_called_once()
                call_args = mock_retrieve.call_args[0]
                assert call_args[0] == "http://localhost:5000/api/agent-files/agent.py"


# ##################################################################
# test parse args with command line
# verifies parse_args extracts server name and secret from args
def test_parse_args_command_line():
    test_args = ["prog", "--server", "http://test:5000", "--name", "test-agent", "--secret", "test-secret"]

    with patch("sys.argv", test_args):
        config = parse_args()
        assert config["server"] == "http://test:5000"
        assert config["name"] == "test-agent"
        assert config["secret"] == "test-secret"


# ##################################################################
# test parse args with config file
# verifies parse_args loads from config.json when args not provided
def test_parse_args_config_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "config.json"
        config_data = {
            "server": "http://localhost:5000",
            "name": "my-agent",
            "secret": "my-secret",
        }
        config_file.write_text(json.dumps(config_data))

        test_args = ["prog", "--config", str(config_file)]
        with patch("sys.argv", test_args):
            config = parse_args()
            assert config["server"] == "http://localhost:5000"
            assert config["name"] == "my-agent"
            assert config["secret"] == "my-secret"


# ##################################################################
# test parse args with default config location
# verifies parse_args looks for config.json in agent directory
def test_parse_args_default_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent_dir = Path(tmpdir)
        config_file = agent_dir / "config.json"
        config_data = {
            "server": "http://localhost:5000",
            "name": "default-agent",
            "secret": "default-secret",
        }
        config_file.write_text(json.dumps(config_data))

        test_args = ["prog"]
        with patch("sys.argv", test_args):
            with patch("agent_updater.Path") as mock_path:
                # Make Path(__file__).parent return our temp dir
                mock_path.return_value.parent = agent_dir

                config = parse_args()
                assert config["server"] == "http://localhost:5000"
                assert config["name"] == "default-agent"
                assert config["secret"] == "default-secret"


# ##################################################################
# test upgrade exit code constant
# verifies upgrade exit code is defined
def test_upgrade_exit_code():
    assert UPGRADE_EXIT_CODE == 42
