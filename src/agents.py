"""Agent registry for managing distributed agents."""

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import get_config


@dataclass
class Agent:
    """Represents a distributed agent that can execute workflow nodes."""

    name: str
    enabled: bool = True
    priority: int = 0
    tags: list[str] = field(default_factory=list)
    status: str = "offline"  # "online" or "offline"
    last_seen: str | None = None
    ip_address: str | None = None
    version: str | None = None
    total_tasks: int = 0
    current_task: str | None = None  # execution_id if working
    secret_hash: str = ""  # For authentication


class AgentRegistry:
    """Manages agent storage and retrieval."""

    def __init__(self, agents_file: str | None = None):
        self._agents_file = agents_file or get_config().agents_file
        self._agents: dict[str, Agent] = {}
        self._load()

    def _load(self) -> None:
        """Load agents from JSON file (called once on startup)."""
        path = Path(self._agents_file)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                for name, agent_data in data.items():
                    self._agents[name] = Agent(**agent_data)

    def _save(self) -> None:
        """Save agents to JSON file (called on any change)."""
        path = Path(self._agents_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {name: asdict(agent) for name, agent in self._agents.items()}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def list_agents(self) -> list[Agent]:
        """Return all agents."""
        return list(self._agents.values())

    def get_agent(self, name: str) -> Agent | None:
        """Get agent by name."""
        return self._agents.get(name)

    def create_agent(self, name: str) -> tuple[Agent, str]:
        """Create a new agent with a generated secret."""
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already exists")

        # Generate a secure secret
        secret = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()

        agent = Agent(name=name, secret_hash=secret_hash)
        self._agents[name] = agent
        self._save()

        # Return agent with the actual secret (only available at creation time)
        # Caller needs to store/display this secret
        return agent, secret

    def update_agent(self, name: str, **kwargs) -> Agent:
        """Update agent fields."""
        agent = self._agents.get(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found")

        # Only allow updating certain fields
        allowed_fields = {
            "enabled",
            "priority",
            "tags",
            "status",
            "last_seen",
            "ip_address",
            "version",
            "total_tasks",
            "current_task",
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(agent, key, value)

        self._save()
        return agent

    def delete_agent(self, name: str) -> None:
        """Delete an agent."""
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not found")
        del self._agents[name]
        self._save()

    def verify_secret(self, name: str, secret: str) -> bool:
        """Verify an agent's secret."""
        agent = self._agents.get(name)
        if not agent:
            return False
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        return secrets.compare_digest(agent.secret_hash, secret_hash)


# Global registry instance
_registry: AgentRegistry | None = None


# ##################################################################
# get global registry instance
# creates instance on first call
def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


# ##################################################################
# set global registry instance
# replaces current registry with new one for testing
def set_registry(registry: AgentRegistry) -> None:
    global _registry
    _registry = registry
