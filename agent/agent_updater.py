#!/usr/bin/env python3
"""Agent updater shim - handles self-upgrade."""

import argparse
import io
import json
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

UPGRADE_EXIT_CODE = 42


def get_local_version() -> str | None:
    """Get the locally installed code version."""
    version_file = Path(__file__).parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return None


def get_server_version(server_url: str) -> str | None:
    """Get the code version from the server."""
    url = f"{server_url}/api/agent-files/version"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("version")
    except Exception as e:
        print(f"Failed to get server version: {e}")
        return None


def install_dependencies(agent_dir: Path) -> None:
    """Install Python dependencies from requirements.txt if it exists."""
    requirements_file = agent_dir / "requirements.txt"
    if not requirements_file.exists():
        print("No requirements.txt found, skipping dependency installation")
        return

    print("Installing dependencies from requirements.txt...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Warning: pip install failed: {result.stderr}")
        else:
            print("Dependencies installed successfully")
    except Exception as e:
        print(f"Warning: Failed to install dependencies: {e}")
        # Don't raise - continue even if pip install fails


def download_code_package(server_url: str) -> None:
    """Download and extract the full code package from server."""
    url = f"{server_url}/api/agent-files/code.zip"
    agent_dir = Path(__file__).parent

    print(f"Downloading code package from {url}...")
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            package_data = response.read()

        # Extract to agent directory
        print("Extracting code package...")
        with zipfile.ZipFile(io.BytesIO(package_data), "r") as zf:
            for member in zf.namelist():
                # Files in agent/ subdirectory should go to the agent dir root
                if member.startswith("agent/"):
                    # Extract agent files directly to agent_dir
                    target_name = member[6:]  # Remove "agent/" prefix
                    if target_name:  # Skip the directory entry itself
                        target_path = agent_dir / target_name
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())
                else:
                    # Extract other files normally
                    zf.extract(member, agent_dir)

        print("Code package updated successfully")

        # Install dependencies after extracting code
        install_dependencies(agent_dir)

    except Exception as e:
        print(f"Failed to download code package: {e}")
        raise


def check_and_update(server_url: str) -> bool:
    """Check if update is needed and download if so.

    Returns True if update was performed.
    """
    local_version = get_local_version()
    server_version = get_server_version(server_url)

    if server_version is None:
        print("Could not get server version, skipping update check")
        return False

    if local_version != server_version:
        print(f"Version mismatch: local={local_version}, server={server_version}")
        download_code_package(server_url)
        return True

    return False


# ##################################################################
# download agent bootstrap files directly
# fetches agent.py and agent_updater.py separately
def download_agent_bootstrap_files(server_url: str) -> None:
    """Download agent.py and agent_updater.py directly."""
    agent_dir = Path(__file__).parent

    for filename in ["agent.py", "agent_updater.py"]:
        url = f"{server_url}/api/agent-files/{filename}"
        target_path = agent_dir / filename
        print(f"Downloading {filename}...")
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read()
            with open(target_path, "wb") as f:
                f.write(content)
        except Exception as e:
            print(f"Failed to download {filename}: {e}")
            raise


# ##################################################################
# download new agent from server
# downloads bootstrap files first, then full code package
def download_new_agent(server_url: str) -> None:
    """Download agent files (called on upgrade signal).

    Downloads bootstrap files first to fix any extraction issues,
    then downloads the full code package.
    """
    download_agent_bootstrap_files(server_url)
    download_code_package(server_url)


# ##################################################################
# parse command line arguments
# returns dict with server, name, and secret
def parse_args() -> dict:
    parser = argparse.ArgumentParser(description="Dazflow2 Agent Updater")
    parser.add_argument("--server", help="Server URL (e.g., http://localhost:5000)")
    parser.add_argument("--name", help="Agent name")
    parser.add_argument("--secret", help="Agent secret")
    parser.add_argument("--config", help="Config file path (default: config.json)")
    args = parser.parse_args()

    if args.server and args.name and args.secret:
        return {
            "server": args.server,
            "name": args.name,
            "secret": args.secret,
        }

    # If not all args provided, try loading from config
    config_path = Path(args.config) if args.config else Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)

    parser.error("Must provide --server, --name, and --secret or use --config with a config file")


# ##################################################################
# main updater loop
# runs agent and handles upgrade requests
def main():
    config = parse_args()

    # Check for updates on startup
    print("Checking for code updates...")
    try:
        check_and_update(config["server"])
    except Exception as e:
        print(f"Update check failed: {e}, continuing with existing code")

    while True:
        # Run agent
        agent_path = Path(__file__).parent / "agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(agent_path),
                "--server",
                config["server"],
                "--name",
                config["name"],
                "--secret",
                config["secret"],
            ]
        )

        if result.returncode == UPGRADE_EXIT_CODE:
            # Download new version and restart
            download_new_agent(config["server"])
            continue
        else:
            # Agent exited for other reason, propagate exit code
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
