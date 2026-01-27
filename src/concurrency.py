"""Concurrency groups for limiting concurrent task execution."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import get_config


@dataclass
class ConcurrencyGroup:
    """Represents a concurrency group with a task limit."""

    name: str
    limit: int


class ConcurrencyRegistry:
    """Manages concurrency groups - stored in concurrency_groups.json."""

    def __init__(self, groups_file: str | None = None):
        self._groups_file = groups_file or get_config().concurrency_groups_file
        self._groups: dict[str, ConcurrencyGroup] = {}
        self._load()

    def _load(self) -> None:
        """Load groups from JSON file (called once on startup)."""
        path = Path(self._groups_file)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                for name, group_data in data.items():
                    self._groups[name] = ConcurrencyGroup(**group_data)

    def _save(self) -> None:
        """Save groups to JSON file (called on any change)."""
        path = Path(self._groups_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {name: asdict(group) for name, group in self._groups.items()}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def list_groups(self) -> list[ConcurrencyGroup]:
        """Return all groups."""
        return list(self._groups.values())

    def get_group(self, name: str) -> ConcurrencyGroup | None:
        """Get group by name."""
        return self._groups.get(name)

    def create_group(self, name: str, limit: int) -> ConcurrencyGroup:
        """Create a new concurrency group."""
        if name in self._groups:
            raise ValueError(f"Group '{name}' already exists")

        group = ConcurrencyGroup(name=name, limit=limit)
        self._groups[name] = group
        self._save()
        return group

    def update_group(self, name: str, limit: int) -> ConcurrencyGroup:
        """Update a group's limit."""
        group = self._groups.get(name)
        if not group:
            raise ValueError(f"Group '{name}' not found")

        group.limit = limit
        self._save()
        return group

    def delete_group(self, name: str) -> None:
        """Delete a concurrency group."""
        if name not in self._groups:
            raise ValueError(f"Group '{name}' not found")

        del self._groups[name]
        self._save()


class ConcurrencyTracker:
    """In-memory tracking of active task counts per group."""

    def __init__(self, registry: ConcurrencyRegistry | None = None):
        self._registry = registry or get_registry()
        self._counts: dict[str, int] = {}

    def can_start(self, group: str) -> bool:
        """Check if starting a task in this group is allowed."""
        group_def = self._registry.get_group(group)
        if not group_def:
            return True  # Unknown group = no limit

        current_count = self._counts.get(group, 0)
        return current_count < group_def.limit

    def increment(self, group: str) -> None:
        """Called when task starts."""
        self._counts[group] = self._counts.get(group, 0) + 1

    def decrement(self, group: str) -> None:
        """Called when task completes/fails/times out."""
        current = self._counts.get(group, 0)
        if current > 0:
            self._counts[group] = current - 1

    def get_count(self, group: str) -> int:
        """Get current active count for group."""
        return self._counts.get(group, 0)


# Global registry instance
_registry: ConcurrencyRegistry | None = None


# ##################################################################
# get global concurrency registry instance
# creates instance on first call
def get_registry() -> ConcurrencyRegistry:
    global _registry
    if _registry is None:
        _registry = ConcurrencyRegistry()
    return _registry


# ##################################################################
# set global concurrency registry instance
# replaces current registry with new one for testing
def set_registry(registry: ConcurrencyRegistry | None) -> None:
    global _registry
    _registry = registry


# Global tracker instance
_tracker: ConcurrencyTracker | None = None


# ##################################################################
# get global concurrency tracker instance
# creates instance on first call
def get_tracker() -> ConcurrencyTracker:
    global _tracker
    if _tracker is None:
        _tracker = ConcurrencyTracker()
    return _tracker


# ##################################################################
# set global concurrency tracker instance
# replaces current tracker with new one for testing
def set_tracker(tracker: ConcurrencyTracker | None) -> None:
    global _tracker
    _tracker = tracker
