"""Tests for system module nodes."""

import subprocess
import sys
from unittest.mock import patch, MagicMock

from modules.system.nodes import (
    execute_dialog,
    execute_prompt,
    execute_notification,
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
