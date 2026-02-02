"""Server configuration system."""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Project root is the parent directory of this file's parent (src/)
_PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())


def _default_data_dir() -> str:
    """Get default data directory (project root)."""
    return _PROJECT_ROOT


@dataclass
class ServerConfig:
    """Configuration for the dazflow2 server.

    Attributes:
        port: TCP port to listen on (default 5000, can be overridden with DAZFLOW_PORT env var)
        data_dir: Directory for all persistent data (default is project root, can be overridden with DAZFLOW_DATA_DIR env var)
    """

    port: int = 5000
    data_dir: str = field(default_factory=_default_data_dir)

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
        """Get current agent version based on code hash.

        This changes whenever any code file changes, triggering agent updates.
        """
        from src.code_version import get_cached_code_version

        return get_cached_code_version()


# Global config instance
_config: ServerConfig | None = None


# ##################################################################
# get global config instance
# creates default config if none exists, reading from environment variables
def get_config() -> ServerConfig:
    global _config
    if _config is None:
        port = int(os.environ.get("DAZFLOW_PORT", "5000"))
        data_dir = os.environ.get("DAZFLOW_DATA_DIR", _PROJECT_ROOT)
        _config = ServerConfig(port=port, data_dir=data_dir)
    return _config


# ##################################################################
# set global config instance
# replaces the current config with a new one
def set_config(config: ServerConfig) -> None:
    global _config
    _config = config
