"""Tests for pipeline workflow system."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from .patterns import (
    extract_variables_from_entity_id,
    match_pattern,
    pattern_to_regex,
    resolve_pattern,
    scan_pattern,
)
from .state_store import StateStore


class TestPatterns:
    """Tests for pattern matching."""

    def test_pattern_to_regex_single_var(self):
        regex, vars = pattern_to_regex("logs/{date}/")
        assert vars == ["date"]
        assert regex.match("logs/2026-01-15/")
        assert not regex.match("logs/2026-01-15")  # Missing trailing /
        assert not regex.match("other/2026-01-15/")

    def test_pattern_to_regex_multi_var(self):
        regex, vars = pattern_to_regex("feeds/{feed}/{guid}.json")
        assert vars == ["feed", "guid"]
        m = regex.match("feeds/hackernews/12345.json")
        assert m
        assert m.group("feed") == "hackernews"
        assert m.group("guid") == "12345"

    def test_pattern_to_regex_special_chars(self):
        regex, _ = pattern_to_regex("data/{date}.txt")
        assert regex.match("data/2026-01-15.txt")
        # Should escape the dot
        assert not regex.match("data/2026-01-15Xtxt")

    def test_match_pattern_single_var(self):
        match = match_pattern("logs/{date}/", "logs/2026-01-15/")
        assert match is not None
        assert match.variables == {"date": "2026-01-15"}
        assert match.entity_id == "2026-01-15"

    def test_match_pattern_multi_var(self):
        match = match_pattern("feeds/{feed}/{guid}", "feeds/hn/12345")
        assert match is not None
        assert match.variables == {"feed": "hn", "guid": "12345"}
        assert match.entity_id == "hn/12345"

    def test_match_pattern_no_match(self):
        match = match_pattern("logs/{date}/", "other/2026-01-15/")
        assert match is None

    def test_resolve_pattern_single_var(self):
        result = resolve_pattern("logs/{date}/", {"date": "2026-01-15"})
        assert result == "logs/2026-01-15/"

    def test_resolve_pattern_multi_var(self):
        result = resolve_pattern("feeds/{feed}/{guid}.json", {"feed": "hn", "guid": "12345"})
        assert result == "feeds/hn/12345.json"

    def test_resolve_pattern_missing_var(self):
        with pytest.raises(KeyError):
            resolve_pattern("logs/{date}/", {})

    def test_extract_variables_single(self):
        vars = extract_variables_from_entity_id("logs/{date}/", "2026-01-15")
        assert vars == {"date": "2026-01-15"}

    def test_extract_variables_multi(self):
        vars = extract_variables_from_entity_id("feeds/{feed}/{guid}", "hn/12345")
        assert vars == {"feed": "hn", "guid": "12345"}

    def test_scan_pattern_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create some directories
            (root / "logs" / "2026-01-15").mkdir(parents=True)
            (root / "logs" / "2026-01-16").mkdir(parents=True)
            (root / "other").mkdir()

            matches = scan_pattern(root, "logs/{date}/")
            assert len(matches) == 2
            entity_ids = [m.entity_id for m in matches]
            assert "2026-01-15" in entity_ids
            assert "2026-01-16" in entity_ids

    def test_scan_pattern_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create some files
            (root / "summaries").mkdir()
            (root / "summaries" / "2026-01-15.txt").write_text("content")
            (root / "summaries" / "2026-01-16.txt").write_text("content")
            (root / "summaries" / "other.md").write_text("content")

            matches = scan_pattern(root, "summaries/{date}.txt")
            assert len(matches) == 2


class TestStateStore:
    """Tests for state store."""

    def test_init_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            assert (Path(tmpdir) / ".dazflow").exists()
            assert (Path(tmpdir) / ".dazflow" / "manifests").exists()
            assert (Path(tmpdir) / ".dazflow" / "failures").exists()

    def test_exists_false_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            assert not store.exists("summaries/{date}.txt", "2026-01-15")

    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Write state
            path = store.write(
                pattern="summaries/{date}.txt",
                entity_id="2026-01-15",
                content="Test content",
                code_hash="abc12345",
                produced_by="test#summary",
            )

            assert path == "summaries/2026-01-15.txt"
            assert store.exists("summaries/{date}.txt", "2026-01-15")

            # Read state
            content = store.read("summaries/{date}.txt", "2026-01-15")
            assert content == "Test content"

    def test_write_updates_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            store.write(
                pattern="summaries/{date}.txt",
                entity_id="2026-01-15",
                content="Test content",
                code_hash="abc12345",
                produced_by="test#summary",
                input_hashes={"logs": "def67890"},
            )

            manifest = store.get_manifest("2026-01-15")
            assert manifest is not None
            assert "summaries/{date}.txt" in manifest.states

            state_info = manifest.states["summaries/{date}.txt"]
            assert state_info.code_hash == "abc12345"
            assert state_info.produced_by == "test#summary"
            assert state_info.input_hashes == {"logs": "def67890"}

    def test_list_entities(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Create some states
            (Path(tmpdir) / "logs" / "2026-01-15").mkdir(parents=True)
            (Path(tmpdir) / "logs" / "2026-01-16").mkdir(parents=True)

            entities = store.list_entities("logs/{date}/")
            assert len(entities) == 2
            assert "2026-01-15" in entities
            assert "2026-01-16" in entities

    def test_delete_removes_file_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Write state
            store.write(
                pattern="summaries/{date}.txt",
                entity_id="2026-01-15",
                content="Test content",
                code_hash="abc12345",
                produced_by="test#summary",
            )

            # Delete
            result = store.delete("summaries/{date}.txt", "2026-01-15")
            assert result is True
            assert not store.exists("summaries/{date}.txt", "2026-01-15")

            # Manifest should be updated
            manifest = store.get_manifest("2026-01-15")
            assert manifest is None or "summaries/{date}.txt" not in manifest.states

    def test_record_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            store.record_failure(
                entity_id="2026-01-15",
                stage_pattern="summaries/{date}.txt",
                error="Test error",
                backoff_schedule=[60, 300],
            )

            failure = store.get_failure("2026-01-15", "summaries/{date}.txt")
            assert failure is not None
            assert failure.error == "Test error"
            assert failure.attempts == 1

    def test_failure_backoff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Record failure with immediate backoff
            store.record_failure(
                entity_id="2026-01-15",
                stage_pattern="summaries/{date}.txt",
                error="Test error",
                backoff_schedule=[0],  # No delay
            )

            # Should be ready to retry immediately
            assert store.should_retry("2026-01-15", "summaries/{date}.txt")

    def test_failure_backoff_not_ready(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Record failure with long backoff
            store.record_failure(
                entity_id="2026-01-15",
                stage_pattern="summaries/{date}.txt",
                error="Test error",
                backoff_schedule=[3600],  # 1 hour
            )

            # Should not be ready yet
            assert not store.should_retry("2026-01-15", "summaries/{date}.txt")

    def test_clear_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            store.record_failure(
                entity_id="2026-01-15",
                stage_pattern="summaries/{date}.txt",
                error="Test error",
            )

            store.clear_failure("2026-01-15", "summaries/{date}.txt")

            failure = store.get_failure("2026-01-15", "summaries/{date}.txt")
            assert failure is None

    def test_register_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Create source file
            (Path(tmpdir) / "logs" / "2026-01-15").mkdir(parents=True)
            (Path(tmpdir) / "logs" / "2026-01-15" / "data.txt").write_text("source data")

            store.register_source("logs/{date}/", "2026-01-15")

            manifest = store.get_manifest("2026-01-15")
            assert manifest is not None
            state_info = manifest.states.get("logs/{date}/")
            assert state_info is not None
            assert state_info.is_source is True


class TestStaleness:
    """Tests for staleness detection."""

    def test_missing_state_is_stale(self):
        from .staleness import is_stale

        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            result = is_stale(
                store,
                entity_id="2026-01-15",
                stage_id="summary",
                stage_pattern="summaries/{date}.txt",
                current_code_hash="abc12345",
            )

            assert result.is_stale
            assert result.reason.value == "missing"

    def test_existing_state_not_stale(self):
        from .staleness import is_stale

        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            store.write(
                pattern="summaries/{date}.txt",
                entity_id="2026-01-15",
                content="Test content",
                code_hash="abc12345",
                produced_by="test#summary",
            )

            result = is_stale(
                store,
                entity_id="2026-01-15",
                stage_id="summary",
                stage_pattern="summaries/{date}.txt",
                current_code_hash="abc12345",  # Same hash
            )

            assert not result.is_stale

    def test_code_change_makes_stale(self):
        from .staleness import is_stale

        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            store.write(
                pattern="summaries/{date}.txt",
                entity_id="2026-01-15",
                content="Test content",
                code_hash="abc12345",
                produced_by="test#summary",
            )

            result = is_stale(
                store,
                entity_id="2026-01-15",
                stage_id="summary",
                stage_pattern="summaries/{date}.txt",
                current_code_hash="xyz99999",  # Different hash!
            )

            assert result.is_stale
            assert result.reason.value == "code_changed"

    def test_input_change_makes_stale(self):
        from .staleness import is_stale

        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Create source and register it
            (Path(tmpdir) / "logs" / "2026-01-15").mkdir(parents=True)
            (Path(tmpdir) / "logs" / "2026-01-15" / "data.txt").write_text("v1")
            store.register_source("logs/{date}/", "2026-01-15")

            # Create summary referencing old input hash
            store.write(
                pattern="summaries/{date}.txt",
                entity_id="2026-01-15",
                content="Test content",
                code_hash="abc12345",
                produced_by="test#summary",
                input_hashes={"logs": "oldhash1"},  # Old hash
            )

            # Now update the source
            (Path(tmpdir) / "logs" / "2026-01-15" / "data.txt").write_text("v2 new content")
            store.register_source("logs/{date}/", "2026-01-15")

            result = is_stale(
                store,
                entity_id="2026-01-15",
                stage_id="summary",
                stage_pattern="summaries/{date}.txt",
                current_code_hash="abc12345",
                input_stage_id="logs",
                input_pattern="logs/{date}/",
            )

            assert result.is_stale
            assert result.reason.value == "input_changed"


class TestScanner:
    """Tests for work scanner."""

    def test_scan_finds_missing_transforms(self):
        from .scanner import scan_for_work

        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Create source
            (Path(tmpdir) / "logs" / "2026-01-15").mkdir(parents=True)
            (Path(tmpdir) / "logs" / "2026-01-15" / "data.txt").write_text("content")
            store.register_source("logs/{date}/", "2026-01-15")

            workflow = {
                "stages": [
                    {"id": "logs", "type": "source", "pattern": "logs/{date}/"},
                    {
                        "id": "summary",
                        "type": "transform",
                        "pattern": "summaries/{date}.txt",
                        "input": "logs",
                        "node": {"typeId": "test_node"},
                    },
                ]
            }

            # Mock the code hash lookup
            from . import code_hash as ch

            ch._code_hash_cache["test_node"] = "abc12345"

            work = scan_for_work(store, workflow)

            assert len(work) == 1
            assert work[0].entity_id == "2026-01-15"
            assert work[0].stage_id == "summary"

    def test_scan_skips_complete_entities(self):
        from .scanner import scan_for_work

        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(tmpdir)
            store.init()

            # Create source
            (Path(tmpdir) / "logs" / "2026-01-15").mkdir(parents=True)
            (Path(tmpdir) / "logs" / "2026-01-15" / "data.txt").write_text("content")
            store.register_source("logs/{date}/", "2026-01-15")

            # Get the source content hash for reference
            source_hash = store.get_content_hash("2026-01-15", "logs/{date}/")

            # Create summary (complete) - with correct input hash reference
            store.write(
                pattern="summaries/{date}.txt",
                entity_id="2026-01-15",
                content="Summary content",
                code_hash="abc12345",
                produced_by="test#summary",
                input_hashes={"logs": source_hash},
            )

            workflow = {
                "stages": [
                    {"id": "logs", "type": "source", "pattern": "logs/{date}/"},
                    {
                        "id": "summary",
                        "type": "transform",
                        "pattern": "summaries/{date}.txt",
                        "input": "logs",
                        "node": {"typeId": "test_node"},
                    },
                ]
            }

            from . import code_hash as ch

            ch._code_hash_cache["test_node"] = "abc12345"

            work = scan_for_work(store, workflow)

            assert len(work) == 0  # No work needed


class TestCodeHash:
    """Tests for code hash calculation."""

    def test_calculate_function_hash(self):
        from .code_hash import calculate_function_hash

        def my_func():
            return 42

        hash1 = calculate_function_hash(my_func)
        assert len(hash1) == 8

        # Same function should give same hash
        hash2 = calculate_function_hash(my_func)
        assert hash1 == hash2

    def test_different_functions_different_hashes(self):
        from .code_hash import calculate_function_hash

        def func_a():
            return 1

        def func_b():
            return 2

        hash_a = calculate_function_hash(func_a)
        hash_b = calculate_function_hash(func_b)

        assert hash_a != hash_b
