"""Tests for the agent updater shim."""

import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from agent_updater import (
    UPGRADE_EXIT_CODE,
    check_and_update,
    download_agent_bootstrap_files,
    download_code_package,
    download_new_agent,
    get_local_version,
    get_server_version,
    parse_args,
)


# ##################################################################
# test get_local_version
def test_get_local_version_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        version_file = Path(tmpdir) / "VERSION"
        version_file.write_text("abc123def456")

        with patch("agent_updater.Path") as mock_path:
            mock_path.return_value.parent = Path(tmpdir)
            version = get_local_version()
            assert version == "abc123def456"


def test_get_local_version_not_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("agent_updater.Path") as mock_path:
            mock_path.return_value.parent = Path(tmpdir)
            version = get_local_version()
            assert version is None


# ##################################################################
# test get_server_version
def test_get_server_version_success():
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"version": "abc123def456"}'
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("agent_updater.urllib.request.urlopen", return_value=mock_response):
        version = get_server_version("http://localhost:5000")
        assert version == "abc123def456"


def test_get_server_version_failure():
    with patch("agent_updater.urllib.request.urlopen", side_effect=Exception("Network error")):
        version = get_server_version("http://localhost:5000")
        assert version is None


# ##################################################################
# test download_code_package
def test_download_code_package():
    # Create a mock zip file
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("VERSION", "abc123def456")
        zf.writestr("agent/agent.py", "# agent code")

    mock_response = MagicMock()
    mock_response.read.return_value = buffer.getvalue()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("agent_updater.urllib.request.urlopen", return_value=mock_response):
            with patch("agent_updater.Path") as mock_path:
                mock_path.return_value.parent = Path(tmpdir)
                download_code_package("http://localhost:5000")

                # Verify files were extracted
                assert (Path(tmpdir) / "VERSION").exists()


# ##################################################################
# test download_agent_bootstrap_files
def test_download_agent_bootstrap_files():
    mock_response = MagicMock()
    mock_response.read.return_value = b"# agent code"
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("agent_updater.urllib.request.urlopen", return_value=mock_response):
            with patch("agent_updater.Path") as mock_path:
                mock_path.return_value.parent = Path(tmpdir)
                download_agent_bootstrap_files("http://localhost:5000")

                # Verify files were downloaded
                assert (Path(tmpdir) / "agent.py").exists()
                assert (Path(tmpdir) / "agent_updater.py").exists()


# ##################################################################
# test check_and_update
def test_check_and_update_needs_update():
    with patch("agent_updater.get_local_version", return_value="old_version"):
        with patch("agent_updater.get_server_version", return_value="new_version"):
            with patch("agent_updater.download_code_package") as mock_download:
                result = check_and_update("http://localhost:5000")
                assert result is True
                mock_download.assert_called_once()


def test_check_and_update_no_update_needed():
    with patch("agent_updater.get_local_version", return_value="same_version"):
        with patch("agent_updater.get_server_version", return_value="same_version"):
            with patch("agent_updater.download_code_package") as mock_download:
                result = check_and_update("http://localhost:5000")
                assert result is False
                mock_download.assert_not_called()


def test_check_and_update_server_unavailable():
    with patch("agent_updater.get_local_version", return_value="some_version"):
        with patch("agent_updater.get_server_version", return_value=None):
            with patch("agent_updater.download_code_package") as mock_download:
                result = check_and_update("http://localhost:5000")
                assert result is False
                mock_download.assert_not_called()


# ##################################################################
# test download_new_agent calls both bootstrap and code package download
def test_download_new_agent():
    with (
        patch("agent_updater.download_agent_bootstrap_files") as mock_bootstrap,
        patch("agent_updater.download_code_package") as mock_download,
    ):
        download_new_agent("http://localhost:5000")
        mock_bootstrap.assert_called_once_with("http://localhost:5000")
        mock_download.assert_called_once_with("http://localhost:5000")


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
