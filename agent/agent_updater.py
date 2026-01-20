#!/usr/bin/env python3
"""Agent updater shim - handles self-upgrade."""

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

UPGRADE_EXIT_CODE = 42


# ##################################################################
# download new agent from server
# fetches latest agent.py from server and saves to local file
def download_new_agent(server_url: str) -> None:
    url = f"{server_url}/api/agent-files/agent.py"
    agent_path = Path(__file__).parent / "agent.py"

    print(f"Downloading new agent from {url}...")
    urllib.request.urlretrieve(url, agent_path)
    print("Agent updated successfully")


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
