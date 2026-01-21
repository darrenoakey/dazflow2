"""System node types for OS-level interactions."""

import subprocess
import sys
from typing import Any


def execute_dialog(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Show a dialog with a message and wait for user to click OK.

    Uses AppleScript on macOS, could be extended for other platforms.
    """
    message = node_data.get("message", "")
    title = node_data.get("title", "Dazflow")

    if sys.platform == "darwin":
        # macOS - use osascript
        script = f'display dialog "{message}" with title "{title}" buttons {{"OK"}} default button "OK"'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=True,
            )
            return [{"clicked": "OK", "platform": "darwin"}]
        except subprocess.CalledProcessError as e:
            # User might have cancelled
            return [{"error": "Dialog cancelled or failed", "stderr": e.stderr}]
    else:
        # Unsupported platform - just log and continue
        return [{"error": f"Dialog not supported on platform: {sys.platform}"}]


def execute_prompt(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Show a prompt dialog with customizable buttons and optional text input.

    Uses AppleScript on macOS with native dialogs.
    Uses tkinter on other platforms for cross-platform support.

    Properties:
        message: The message to display
        title: Dialog title (default: "Dazflow")
        buttons: Comma-separated list of button labels (default: "OK,Cancel")
        showInput: Whether to show a text input field
        defaultInput: Default text for input field
    """
    message = node_data.get("message", "")
    title = node_data.get("title", "Dazflow")
    buttons_str = node_data.get("buttons", "OK,Cancel")
    show_input = node_data.get("showInput", False)
    default_input = node_data.get("defaultInput", "")

    # Parse buttons
    buttons = [b.strip() for b in buttons_str.split(",") if b.strip()]
    if not buttons:
        buttons = ["OK"]

    if sys.platform == "darwin":
        return _prompt_macos(message, title, buttons, show_input, default_input)
    else:
        return _prompt_tkinter(message, title, buttons, show_input, default_input)


def _prompt_macos(message: str, title: str, buttons: list, show_input: bool, default_input: str) -> list:
    """Show prompt using macOS AppleScript."""
    # Format buttons for AppleScript (reversed for proper display order)
    buttons_applescript = ", ".join(f'"{b}"' for b in reversed(buttons))
    default_button = f'"{buttons[0]}"'

    if show_input:
        # Dialog with text input
        script = f'''
        display dialog "{message}" with title "{title}" \
            buttons {{{buttons_applescript}}} default button {default_button} \
            default answer "{default_input}"
        '''
    else:
        # Dialog without text input
        script = f'''
        display dialog "{message}" with title "{title}" \
            buttons {{{buttons_applescript}}} default button {default_button}
        '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse the result: "button returned:OK, text returned:some text"
        output = result.stdout.strip()
        response = {"platform": "darwin", "cancelled": False}

        for part in output.split(", "):
            if ":" in part:
                key, value = part.split(":", 1)
                if key == "button returned":
                    response["button"] = value
                elif key == "text returned":
                    response["text"] = value

        return [response]

    except subprocess.CalledProcessError:
        # User cancelled
        return [{"platform": "darwin", "cancelled": True, "button": None, "text": None}]


def _prompt_tkinter(message: str, title: str, buttons: list, show_input: bool, default_input: str) -> list:
    """Show prompt using tkinter for cross-platform support."""
    try:
        import tkinter as tk
    except ImportError:
        return [{"error": "tkinter not available", "platform": sys.platform}]

    result = {"platform": sys.platform, "cancelled": False, "button": None, "text": None}

    def on_button(button_text):
        result["button"] = button_text
        if show_input and entry is not None:
            result["text"] = entry.get()
        root.quit()
        root.destroy()

    def on_close():
        result["cancelled"] = True
        root.quit()
        root.destroy()

    # Create the dialog
    root = tk.Tk()
    root.title(title)
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Center on screen
    root.update_idletasks()
    width = 400
    height = 150 if show_input else 100
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    # Message label
    label = tk.Label(root, text=message, wraplength=380, padx=10, pady=10)
    label.pack()

    # Optional text input
    entry = None
    if show_input:
        entry = tk.Entry(root, width=50)
        entry.insert(0, default_input)
        entry.pack(padx=10, pady=5)

    # Buttons frame
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    for btn_text in buttons:
        btn = tk.Button(btn_frame, text=btn_text, width=10, command=lambda t=btn_text: on_button(t))
        btn.pack(side=tk.LEFT, padx=5)

    # Focus the first button or entry
    if show_input and entry:
        entry.focus_set()
    root.lift()
    root.attributes("-topmost", True)

    root.mainloop()

    return [result]


def execute_notification(node_data: dict, _input_data: Any, _credential_data: dict | None = None) -> list:
    """Show a system notification (non-blocking).

    Uses osascript on macOS, notify-send on Linux.
    """
    message = node_data.get("message", "")
    title = node_data.get("title", "Dazflow")

    if sys.platform == "darwin":
        script = f'display notification "{message}" with title "{title}"'
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, check=True)
            return [{"sent": True, "platform": "darwin"}]
        except subprocess.CalledProcessError as e:
            return [{"error": str(e), "platform": "darwin"}]
    elif sys.platform == "linux":
        try:
            subprocess.run(["notify-send", title, message], capture_output=True, check=True)
            return [{"sent": True, "platform": "linux"}]
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            return [{"error": str(e), "platform": "linux"}]
    else:
        return [{"error": f"Notifications not supported on platform: {sys.platform}"}]


NODE_TYPES = {
    "dialog": {
        "execute": execute_dialog,
        "kind": "array",
    },
    "prompt": {
        "execute": execute_prompt,
        "kind": "array",
    },
    "notification": {
        "execute": execute_notification,
        "kind": "array",
    },
}
