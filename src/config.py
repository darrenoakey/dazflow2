"""Server configuration system."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServerConfig:
    """Configuration for the dazflow2 server.

    Attributes:
        port: TCP port to listen on (default 5000)
        data_dir: Directory for all persistent data (default ".")
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


# Global config instance
_config: ServerConfig | None = None


# ##################################################################
# get global config instance
# creates default config if none exists
def get_config() -> ServerConfig:
    global _config
    if _config is None:
        _config = ServerConfig()
    return _config


# ##################################################################
# set global config instance
# replaces the current config with a new one
def set_config(config: ServerConfig) -> None:
    global _config
    _config = config
