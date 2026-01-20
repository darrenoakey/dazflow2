"""Tests for concurrency groups and tracking."""

import json
from pathlib import Path

import pytest

from src.concurrency import (
    ConcurrencyGroup,
    ConcurrencyRegistry,
    ConcurrencyTracker,
    get_registry,
    get_tracker,
    set_registry,
    set_tracker,
)
from src.config import ServerConfig, set_config


# ##################################################################
# test concurrency group dataclass
# verifies dataclass stores name and limit
def test_concurrency_group_creation():
    group = ConcurrencyGroup(name="heavy-compute", limit=5)
    assert group.name == "heavy-compute"
    assert group.limit == 5


# ##################################################################
# test concurrency group with different limits
# verifies different limit values are stored correctly
def test_concurrency_group_with_different_limits():
    group1 = ConcurrencyGroup(name="fast", limit=10)
    group2 = ConcurrencyGroup(name="slow", limit=1)

    assert group1.limit == 10
    assert group2.limit == 1


# ##################################################################
# test registry creation with temp file
# verifies registry initializes with empty state
def test_registry_creates_with_empty_state(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    groups = registry.list_groups()
    assert groups == []


# ##################################################################
# test registry create group
# verifies creating a new group
def test_registry_create_group(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    group = registry.create_group("heavy-compute", 5)
    assert group.name == "heavy-compute"
    assert group.limit == 5


# ##################################################################
# test registry create group persists to file
# verifies group is saved to JSON file
def test_registry_create_group_persists(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    registry.create_group("heavy-compute", 5)

    # Verify file was created and contains data
    assert Path(groups_file).exists()
    data = json.loads(Path(groups_file).read_text())
    assert "heavy-compute" in data
    assert data["heavy-compute"]["name"] == "heavy-compute"
    assert data["heavy-compute"]["limit"] == 5


# ##################################################################
# test registry loads existing groups
# verifies registry reads groups from file on init
def test_registry_loads_existing_groups(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")

    # Create first registry and add groups
    registry1 = ConcurrencyRegistry(groups_file)
    registry1.create_group("heavy-compute", 5)
    registry1.create_group("fast-api", 10)

    # Create new registry to test loading
    registry2 = ConcurrencyRegistry(groups_file)
    groups = registry2.list_groups()

    assert len(groups) == 2
    names = {g.name for g in groups}
    assert "heavy-compute" in names
    assert "fast-api" in names


# ##################################################################
# test registry get group by name
# verifies getting a specific group
def test_registry_get_group(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    registry.create_group("heavy-compute", 5)
    registry.create_group("fast-api", 10)

    group = registry.get_group("heavy-compute")
    assert group is not None
    assert group.name == "heavy-compute"
    assert group.limit == 5


# ##################################################################
# test registry get nonexistent group
# verifies getting a group that doesn't exist returns None
def test_registry_get_nonexistent_group(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    group = registry.get_group("nonexistent")
    assert group is None


# ##################################################################
# test registry update group
# verifies updating a group's limit
def test_registry_update_group(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    registry.create_group("heavy-compute", 5)
    updated = registry.update_group("heavy-compute", 10)

    assert updated.name == "heavy-compute"
    assert updated.limit == 10


# ##################################################################
# test registry update group persists
# verifies update is saved to file
def test_registry_update_group_persists(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    registry.create_group("heavy-compute", 5)
    registry.update_group("heavy-compute", 10)

    # Load fresh registry to verify persistence
    registry2 = ConcurrencyRegistry(groups_file)
    group = registry2.get_group("heavy-compute")
    assert group is not None
    assert group.limit == 10


# ##################################################################
# test registry update nonexistent group raises error
# verifies updating a group that doesn't exist raises ValueError
def test_registry_update_nonexistent_group_raises(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    with pytest.raises(ValueError, match="Group 'nonexistent' not found"):
        registry.update_group("nonexistent", 10)


# ##################################################################
# test registry delete group
# verifies deleting a group
def test_registry_delete_group(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    registry.create_group("heavy-compute", 5)
    registry.delete_group("heavy-compute")

    groups = registry.list_groups()
    assert len(groups) == 0


# ##################################################################
# test registry delete group persists
# verifies deletion is saved to file
def test_registry_delete_group_persists(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    registry.create_group("heavy-compute", 5)
    registry.delete_group("heavy-compute")

    # Load fresh registry to verify persistence
    registry2 = ConcurrencyRegistry(groups_file)
    groups = registry2.list_groups()
    assert len(groups) == 0


# ##################################################################
# test registry delete nonexistent group raises error
# verifies deleting a group that doesn't exist raises ValueError
def test_registry_delete_nonexistent_group_raises(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    with pytest.raises(ValueError, match="Group 'nonexistent' not found"):
        registry.delete_group("nonexistent")


# ##################################################################
# test registry create duplicate group raises error
# verifies creating a group that already exists raises ValueError
def test_registry_create_duplicate_group_raises(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)

    registry.create_group("heavy-compute", 5)

    with pytest.raises(ValueError, match="Group 'heavy-compute' already exists"):
        registry.create_group("heavy-compute", 10)


# ##################################################################
# test tracker starts with zero counts
# verifies tracker initializes with empty counts
def test_tracker_starts_empty():
    tracker = ConcurrencyTracker()

    count = tracker.get_count("any-group")
    assert count == 0


# ##################################################################
# test tracker increment increases count
# verifies incrementing a group increases its count
def test_tracker_increment(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 5)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")

    count = tracker.get_count("heavy-compute")
    assert count == 1


# ##################################################################
# test tracker multiple increments
# verifies multiple increments accumulate
def test_tracker_multiple_increments(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 5)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")

    count = tracker.get_count("heavy-compute")
    assert count == 3


# ##################################################################
# test tracker decrement decreases count
# verifies decrementing a group decreases its count
def test_tracker_decrement(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 5)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")
    tracker.decrement("heavy-compute")

    count = tracker.get_count("heavy-compute")
    assert count == 1


# ##################################################################
# test tracker decrement below zero stops at zero
# verifies count doesn't go negative
def test_tracker_decrement_stops_at_zero(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 5)

    tracker = ConcurrencyTracker(registry)
    tracker.decrement("heavy-compute")
    tracker.decrement("heavy-compute")

    count = tracker.get_count("heavy-compute")
    assert count == 0


# ##################################################################
# test tracker can_start with no limit
# verifies unknown group has no limit
def test_tracker_can_start_unknown_group():
    tracker = ConcurrencyTracker()

    can_start = tracker.can_start("unknown-group")
    assert can_start is True


# ##################################################################
# test tracker can_start under limit
# verifies can start when under limit
def test_tracker_can_start_under_limit(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 5)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")

    can_start = tracker.can_start("heavy-compute")
    assert can_start is True


# ##################################################################
# test tracker can_start at limit
# verifies cannot start when at limit
def test_tracker_can_start_at_limit(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 3)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")

    can_start = tracker.can_start("heavy-compute")
    assert can_start is False


# ##################################################################
# test tracker can_start above limit
# verifies cannot start when over limit
def test_tracker_can_start_above_limit(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 2)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")

    can_start = tracker.can_start("heavy-compute")
    assert can_start is False


# ##################################################################
# test tracker can_start after decrement
# verifies can start again after decrement frees up slot
def test_tracker_can_start_after_decrement(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 2)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")

    assert tracker.can_start("heavy-compute") is False

    tracker.decrement("heavy-compute")

    assert tracker.can_start("heavy-compute") is True


# ##################################################################
# test tracker multiple groups independent
# verifies different groups have independent counts
def test_tracker_multiple_groups_independent(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 2)
    registry.create_group("fast-api", 10)

    tracker = ConcurrencyTracker(registry)
    tracker.increment("heavy-compute")
    tracker.increment("heavy-compute")
    tracker.increment("fast-api")

    assert tracker.get_count("heavy-compute") == 2
    assert tracker.get_count("fast-api") == 1
    assert tracker.can_start("heavy-compute") is False
    assert tracker.can_start("fast-api") is True


# ##################################################################
# test global get_registry
# verifies get_registry returns default instance
def test_get_registry_returns_default(tmp_path):
    set_config(ServerConfig(data_dir=str(tmp_path)))

    # Reset global registry
    set_registry(None)

    registry = get_registry()
    assert registry is not None
    assert isinstance(registry, ConcurrencyRegistry)


# ##################################################################
# test global set_registry
# verifies set_registry changes the global instance
def test_set_registry_changes_global(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    custom_registry = ConcurrencyRegistry(groups_file)
    custom_registry.create_group("test-group", 5)

    set_registry(custom_registry)

    registry = get_registry()
    groups = registry.list_groups()
    assert len(groups) == 1
    assert groups[0].name == "test-group"


# ##################################################################
# test global get_tracker
# verifies get_tracker returns default instance
def test_get_tracker_returns_default(tmp_path):
    set_config(ServerConfig(data_dir=str(tmp_path)))

    # Reset global tracker
    set_tracker(None)

    tracker = get_tracker()
    assert tracker is not None
    assert isinstance(tracker, ConcurrencyTracker)


# ##################################################################
# test global set_tracker
# verifies set_tracker changes the global instance
def test_set_tracker_changes_global(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("test-group", 5)

    custom_tracker = ConcurrencyTracker(registry)
    custom_tracker.increment("test-group")

    set_tracker(custom_tracker)

    tracker = get_tracker()
    count = tracker.get_count("test-group")
    assert count == 1


# ##################################################################
# test tracker persistence not required
# verifies tracker counts are in-memory only and don't persist
def test_tracker_counts_not_persisted(tmp_path):
    groups_file = str(tmp_path / "concurrency_groups.json")
    registry = ConcurrencyRegistry(groups_file)
    registry.create_group("heavy-compute", 5)

    tracker1 = ConcurrencyTracker(registry)
    tracker1.increment("heavy-compute")
    tracker1.increment("heavy-compute")

    assert tracker1.get_count("heavy-compute") == 2

    # Create new tracker - should start fresh
    tracker2 = ConcurrencyTracker(registry)
    assert tracker2.get_count("heavy-compute") == 0
