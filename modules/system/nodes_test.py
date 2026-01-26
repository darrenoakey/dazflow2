"""Tests for system module nodes."""

import subprocess
import sys
from unittest.mock import patch, MagicMock

from modules.system.nodes import (
    execute_dialog,
    execute_prompt,
    execute_notification,
    execute_run_command,
    NODE_TYPES,
)


# ##################################################################
# test dialog node type exists
def test_dialog_node_type_registered():
    assert "dialog" in NODE_TYPES
    assert NODE_TYPES["dialog"]["execute"] == execute_dialog
    assert NODE_TYPES["dialog"]["kind"] == "array"


# ##################################################################
# test prompt node type exists
def test_prompt_node_type_registered():
    assert "prompt" in NODE_TYPES
    assert NODE_TYPES["prompt"]["execute"] == execute_prompt
    assert NODE_TYPES["prompt"]["kind"] == "array"


# ##################################################################
# test notification node type exists
def test_notification_node_type_registered():
    assert "notification" in NODE_TYPES
    assert NODE_TYPES["notification"]["execute"] == execute_notification
    assert NODE_TYPES["notification"]["kind"] == "array"


# ##################################################################
# test dialog execution on macos
@patch("subprocess.run")
def test_execute_dialog_macos(mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(sys, "platform", "darwin"):
        result = execute_dialog({"message": "Test message", "title": "Test"}, None)

    assert result == [{"clicked": "OK", "platform": "darwin"}]
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert "osascript" in call_args[0][0]


# ##################################################################
# test dialog with default title
@patch("subprocess.run")
def test_execute_dialog_default_title(mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(sys, "platform", "darwin"):
        result = execute_dialog({"message": "Hello"}, None)

    assert result == [{"clicked": "OK", "platform": "darwin"}]
    # Verify the script includes default title
    call_args = mock_run.call_args
    script = call_args[0][0][2]  # osascript -e <script>
    assert 'with title "Dazflow"' in script


# ##################################################################
# test dialog on unsupported platform
def test_execute_dialog_unsupported_platform():
    with patch.object(sys, "platform", "linux"):
        result = execute_dialog({"message": "Test"}, None)

    assert len(result) == 1
    assert "error" in result[0]
    assert "not supported" in result[0]["error"]


# ##################################################################
# test prompt execution on macos with button click
@patch("modules.system.nodes.subprocess.run")
def test_execute_prompt_macos(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="button returned:OK")

    with patch.object(sys, "platform", "darwin"):
        result = execute_prompt(
            {"message": "Continue?", "title": "Confirm", "buttons": "Yes,No"},
            None,
        )

    assert len(result) == 1
    assert result[0]["platform"] == "darwin"
    assert result[0]["button"] == "OK"
    assert result[0]["cancelled"] is False


# ##################################################################
# test prompt execution on macos with text input
@patch("modules.system.nodes.subprocess.run")
def test_execute_prompt_macos_with_input(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="button returned:OK, text returned:Hello World")

    with patch.object(sys, "platform", "darwin"):
        result = execute_prompt(
            {
                "message": "Enter name:",
                "showInput": True,
                "defaultInput": "default",
            },
            None,
        )

    assert len(result) == 1
    assert result[0]["button"] == "OK"
    assert result[0]["text"] == "Hello World"


# ##################################################################
# test prompt execution cancelled
@patch("modules.system.nodes.subprocess.run")
def test_execute_prompt_macos_cancelled(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(1, "osascript")

    with patch.object(sys, "platform", "darwin"):
        result = execute_prompt({"message": "Continue?"}, None)

    assert len(result) == 1
    assert result[0]["cancelled"] is True
    assert result[0]["button"] is None


# ##################################################################
# test notification execution on macos
@patch("modules.system.nodes.subprocess.run")
def test_execute_notification_macos(mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(sys, "platform", "darwin"):
        result = execute_notification({"message": "Task complete", "title": "Done"}, None)

    assert result == [{"sent": True, "platform": "darwin"}]
    call_args = mock_run.call_args
    assert "osascript" in call_args[0][0]
    script = call_args[0][0][2]
    assert "display notification" in script


# ##################################################################
# test notification execution on linux
@patch("modules.system.nodes.subprocess.run")
def test_execute_notification_linux(mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    with patch.object(sys, "platform", "linux"):
        result = execute_notification({"message": "Hello", "title": "Test"}, None)

    assert result == [{"sent": True, "platform": "linux"}]
    call_args = mock_run.call_args
    assert "notify-send" in call_args[0][0]


# ##################################################################
# test notification on unsupported platform
def test_execute_notification_unsupported_platform():
    with patch.object(sys, "platform", "win32"):
        result = execute_notification({"message": "Test"}, None)

    assert len(result) == 1
    assert "error" in result[0]
    assert "not supported" in result[0]["error"]


# ##################################################################
# test run_command node type exists
def test_run_command_node_type_registered():
    assert "run_command" in NODE_TYPES
    assert NODE_TYPES["run_command"]["execute"] == execute_run_command
    assert NODE_TYPES["run_command"]["kind"] == "array"


# ##################################################################
# test run_command executes echo successfully
def test_execute_run_command_echo():
    result = execute_run_command({"command": "echo hello"}, None)

    assert len(result) == 1
    assert result[0]["success"] is True
    assert result[0]["exitCode"] == 0
    assert "hello" in result[0]["stdout"]
    assert result[0]["stderr"] == ""


# ##################################################################
# test run_command with working directory
def test_execute_run_command_with_working_directory():
    result = execute_run_command({"command": "pwd", "workingDirectory": "/tmp"}, None)

    assert len(result) == 1
    assert result[0]["success"] is True
    assert result[0]["exitCode"] == 0
    # /tmp might be a symlink to /private/tmp on macOS
    assert "tmp" in result[0]["stdout"]


# ##################################################################
# test run_command with missing command
def test_execute_run_command_missing_command():
    result = execute_run_command({"command": ""}, None)

    assert len(result) == 1
    assert result[0]["success"] is False
    assert result[0]["exitCode"] == -1
    assert "Command is required" in result[0]["error"]


# ##################################################################
# test run_command with nonexistent working directory
def test_execute_run_command_invalid_working_directory():
    result = execute_run_command(
        {"command": "echo test", "workingDirectory": "/nonexistent/path/that/does/not/exist"},
        None,
    )

    assert len(result) == 1
    assert result[0]["success"] is False
    assert result[0]["exitCode"] == -1
    assert "error" in result[0]


# ##################################################################
# test run_command with failing command
def test_execute_run_command_failing_command():
    result = execute_run_command({"command": "exit 1"}, None)

    assert len(result) == 1
    assert result[0]["success"] is False
    assert result[0]["exitCode"] == 1


# ##################################################################
# test run_command captures stderr
def test_execute_run_command_captures_stderr():
    result = execute_run_command({"command": "echo error >&2"}, None)

    assert len(result) == 1
    assert result[0]["exitCode"] == 0
    assert "error" in result[0]["stderr"]


# ##################################################################
# test run_command expands tilde in working directory
def test_execute_run_command_tilde_expansion():
    import os

    result = execute_run_command({"command": "pwd", "workingDirectory": "~"}, None)

    assert len(result) == 1
    assert result[0]["success"] is True
    assert result[0]["exitCode"] == 0
    # Should expand ~ to actual home directory
    assert os.path.expanduser("~") in result[0]["stdout"]


# ##################################################################
# test run_command with custom timeout (passes timeout to subprocess)
@patch("modules.system.nodes.subprocess.run")
def test_execute_run_command_custom_timeout(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")

    execute_run_command({"command": "sleep 1", "timeout": "600"}, None)

    # Verify timeout was passed to subprocess.run
    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs["timeout"] == 600


# ##################################################################
# test run_command with default timeout when not specified
@patch("modules.system.nodes.subprocess.run")
def test_execute_run_command_default_timeout(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")

    execute_run_command({"command": "echo test"}, None)

    # Verify default timeout of 300 seconds
    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs["timeout"] == 300


# ##################################################################
# test run_command with invalid timeout falls back to default
@patch("modules.system.nodes.subprocess.run")
def test_execute_run_command_invalid_timeout_fallback(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")

    execute_run_command({"command": "echo test", "timeout": "invalid"}, None)

    # Verify fallback to default timeout of 300 seconds
    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs["timeout"] == 300


# ##################################################################
# test run_command timeout error message includes actual timeout value
@patch("modules.system.nodes.subprocess.run")
def test_execute_run_command_timeout_error_message(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired("cmd", 600)

    result = execute_run_command({"command": "sleep 1000", "timeout": "600"}, None)

    assert len(result) == 1
    assert result[0]["success"] is False
    assert result[0]["exitCode"] == -1
    assert "600 seconds" in result[0]["error"]
