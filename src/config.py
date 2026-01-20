"""Server configuration system."""

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServerConfig:
    """Configuration for the dazflow2 server.

    Attributes:
        port: TCP port to listen on (default 5000, can be overridden with DAZFLOW_PORT env var)
        data_dir: Directory for all persistent data (default ".", can be overridden with DAZFLOW_DATA_DIR env var)
    """

    port: int = 5000
    data_dir: str = "."

    @property
    def workflows_dir(self) -> str:
        """Path to workflows directory."""
        return str(Path(self.data_dir) / "workflows")

    @property
    def agents_file(self) -> str:
        """Path to agents.json file."""
        return str(Path(self.data_dir) / "agents.json")

    @property
    def tags_file(self) -> str:
        """Path to tags.json file."""
        return str(Path(self.data_dir) / "tags.json")

    @property
    def concurrency_groups_file(self) -> str:
        """Path to concurrency_groups.json file."""
        return str(Path(self.data_dir) / "concurrency_groups.json")

    @property
    def agent_version(self) -> str:
        """Get current agent version from agent.py file."""
        agent_file = Path(__file__).parent.parent / "agent" / "agent.py"
        if agent_file.exists():
            content = agent_file.read_text()
            match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
        return "1.0.0"  # Default fallback


# Global config instance
_config: ServerConfig | None = None


# ##################################################################
# get global config instance
# creates default config if none exists, reading from environment variables
def get_config() -> ServerConfig:
    global _config
    if _config is None:
        port = int(os.environ.get("DAZFLOW_PORT", "5000"))
        data_dir = os.environ.get("DAZFLOW_DATA_DIR", ".")
        _config = ServerConfig(port=port, data_dir=data_dir)
    return _config


# ##################################################################
# set global config instance
# replaces the current config with a new one
def set_config(config: ServerConfig) -> None:
    global _config
    _config = config
