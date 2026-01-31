"""State store for pipeline workflows.

Manages state files and manifests for tracking what has been produced,
when, and with what code version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from .patterns import (
    PatternMatch,
    extract_variables_from_entity_id,
    resolve_pattern,
    scan_pattern,
)

# Directory name for metadata within state root
METADATA_DIR = ".dazflow"


@dataclass
class StateInfo:
    """Information about a produced state."""

    path: str
    code_hash: str
    content_hash: str
    produced_at: str
    produced_by: str
    input_hashes: dict[str, str] = field(default_factory=dict)
    is_source: bool = False


@dataclass
class FailureInfo:
    """Information about a failed state production attempt."""

    error: str
    error_details: str | None
    attempts: int
    first_failed_at: str
    last_failed_at: str
    next_retry_at: str


@dataclass
class EntityManifest:
    """Complete manifest for an entity."""

    entity_id: str
    states: dict[str, StateInfo] = field(default_factory=dict)


@dataclass
class EntityFailures:
    """Failure records for an entity."""

    entity_id: str
    failures: dict[str, FailureInfo] = field(default_factory=dict)


class StateStore:
    """Filesystem-based state store for pipeline workflows."""

    def __init__(self, root: Path | str):
        """Initialize state store.

        Args:
            root: Root directory for state storage
        """
        self.root = Path(root)
        self.metadata_dir = self.root / METADATA_DIR
        self.manifests_dir = self.metadata_dir / "manifests"
        self.failures_dir = self.metadata_dir / "failures"

    def init(self) -> None:
        """Initialize state store directories."""
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(exist_ok=True)
        self.failures_dir.mkdir(exist_ok=True)

    # -------------------------------------------------------------------------
    # State existence and content
    # -------------------------------------------------------------------------

    def exists(self, pattern: str, entity_id: str) -> bool:
        """Check if a state exists.

        Args:
            pattern: State pattern (e.g., "summaries/{date}.txt")
            entity_id: Entity identifier

        Returns:
            True if state file exists
        """
        path = self._resolve_path(pattern, entity_id)
        return path.exists()

    def read(self, pattern: str, entity_id: str) -> str | None:
        """Read state content.

        Args:
            pattern: State pattern
            entity_id: Entity identifier

        Returns:
            File content as string, or None if doesn't exist
        """
        path = self._resolve_path(pattern, entity_id)
        if not path.exists():
            return None
        return path.read_text()

    def read_bytes(self, pattern: str, entity_id: str) -> bytes | None:
        """Read state content as bytes.

        Args:
            pattern: State pattern
            entity_id: Entity identifier

        Returns:
            File content as bytes, or None if doesn't exist
        """
        path = self._resolve_path(pattern, entity_id)
        if not path.exists():
            return None
        return path.read_bytes()

    def write(
        self,
        pattern: str,
        entity_id: str,
        content: str | bytes,
        code_hash: str,
        produced_by: str,
        input_hashes: dict[str, str] | None = None,
    ) -> str:
        """Write state content and update manifest.

        Args:
            pattern: State pattern
            entity_id: Entity identifier
            content: Content to write
            code_hash: Hash of the code that produced this
            produced_by: Identifier of the producing workflow/stage
            input_hashes: Hashes of input states

        Returns:
            Path where state was written (relative to root)
        """
        path = self._resolve_path(pattern, entity_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, str):
            path.write_text(content)
        else:
            path.write_bytes(content)

        # Calculate content hash
        content_bytes = content if isinstance(content, bytes) else content.encode()
        content_hash = hashlib.md5(content_bytes).hexdigest()[:8]

        # Update manifest
        rel_path = str(path.relative_to(self.root))
        self._update_manifest(
            entity_id,
            pattern,
            StateInfo(
                path=rel_path,
                code_hash=code_hash,
                content_hash=content_hash,
                produced_at=datetime.now().isoformat(),
                produced_by=produced_by,
                input_hashes=input_hashes or {},
            ),
        )

        # Clear any failure record
        self.clear_failure(entity_id, pattern)

        return rel_path

    def delete(self, pattern: str, entity_id: str) -> bool:
        """Delete a state file.

        Args:
            pattern: State pattern
            entity_id: Entity identifier

        Returns:
            True if file was deleted, False if didn't exist
        """
        path = self._resolve_path(pattern, entity_id)
        if not path.exists():
            return False

        path.unlink()

        # Remove from manifest
        manifest = self.get_manifest(entity_id)
        if manifest and pattern in manifest.states:
            del manifest.states[pattern]
            self._write_manifest(manifest)

        return True

    # -------------------------------------------------------------------------
    # Entity and pattern scanning
    # -------------------------------------------------------------------------

    def list_entities(self, pattern: str) -> list[str]:
        """List all entities matching a pattern.

        Args:
            pattern: State pattern to scan

        Returns:
            List of entity IDs found
        """
        matches = scan_pattern(self.root, pattern)
        return [m.entity_id for m in matches]

    def scan(self, pattern: str) -> list[PatternMatch]:
        """Scan for paths matching a pattern.

        Args:
            pattern: State pattern

        Returns:
            List of PatternMatch objects
        """
        return scan_pattern(self.root, pattern)

    # -------------------------------------------------------------------------
    # Manifests
    # -------------------------------------------------------------------------

    def get_manifest(self, entity_id: str) -> EntityManifest | None:
        """Get manifest for an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            EntityManifest or None if doesn't exist
        """
        path = self._manifest_path(entity_id)
        if not path.exists():
            return None

        data = json.loads(path.read_text())
        states = {k: StateInfo(**v) for k, v in data.get("states", {}).items()}
        return EntityManifest(entity_id=entity_id, states=states)

    def get_state_info(self, entity_id: str, stage_pattern: str) -> StateInfo | None:
        """Get state info for a specific stage.

        Args:
            entity_id: Entity identifier
            stage_pattern: State pattern for the stage

        Returns:
            StateInfo or None if not in manifest
        """
        manifest = self.get_manifest(entity_id)
        if not manifest:
            return None
        return manifest.states.get(stage_pattern)

    def get_content_hash(self, entity_id: str, stage_pattern: str) -> str | None:
        """Get content hash for a state.

        Args:
            entity_id: Entity identifier
            stage_pattern: State pattern for the stage

        Returns:
            Content hash or None if not in manifest
        """
        info = self.get_state_info(entity_id, stage_pattern)
        return info.content_hash if info else None

    def register_source(self, pattern: str, entity_id: str, discovered_at: str | None = None) -> None:
        """Register a source state (external data that arrived).

        Args:
            pattern: State pattern
            entity_id: Entity identifier
            discovered_at: When the source was discovered
        """
        path = self._resolve_path(pattern, entity_id)
        if not path.exists():
            return

        # Calculate content hash
        if path.is_dir():
            # For directories, hash the list of files and their sizes
            files = sorted(path.rglob("*"))
            content_list = [f"{f.relative_to(path)}:{f.stat().st_size if f.is_file() else 0}" for f in files]
            content_str = "\n".join(content_list)
            content_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
        else:
            content = path.read_bytes()
            content_hash = hashlib.md5(content).hexdigest()[:8]

        self._update_manifest(
            entity_id,
            pattern,
            StateInfo(
                path=str(path.relative_to(self.root)),
                code_hash="source00",  # Sources don't have code
                content_hash=content_hash,
                produced_at=discovered_at or datetime.now().isoformat(),
                produced_by="external",
                is_source=True,
            ),
        )

    def _update_manifest(self, entity_id: str, stage_pattern: str, state_info: StateInfo) -> None:
        """Update manifest with new state info."""
        manifest = self.get_manifest(entity_id) or EntityManifest(entity_id=entity_id)
        manifest.states[stage_pattern] = state_info
        self._write_manifest(manifest)

    def _write_manifest(self, manifest: EntityManifest) -> None:
        """Write manifest to disk."""
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        path = self._manifest_path(manifest.entity_id)

        data = {
            "entity_id": manifest.entity_id,
            "states": {
                k: {
                    "path": v.path,
                    "code_hash": v.code_hash,
                    "content_hash": v.content_hash,
                    "produced_at": v.produced_at,
                    "produced_by": v.produced_by,
                    "input_hashes": v.input_hashes,
                    "is_source": v.is_source,
                }
                for k, v in manifest.states.items()
            },
        }
        path.write_text(json.dumps(data, indent=2))

    def _manifest_path(self, entity_id: str) -> Path:
        """Get path to manifest file for an entity."""
        # Replace / with _ for composite entity IDs
        safe_id = entity_id.replace("/", "_")
        return self.manifests_dir / f"{safe_id}.json"

    # -------------------------------------------------------------------------
    # Failures
    # -------------------------------------------------------------------------

    def record_failure(
        self,
        entity_id: str,
        stage_pattern: str,
        error: str,
        error_details: str | None = None,
        backoff_schedule: list[int] | None = None,
    ) -> None:
        """Record a failure for a stage.

        Args:
            entity_id: Entity identifier
            stage_pattern: State pattern for the stage
            error: Error message
            error_details: Additional error details
            backoff_schedule: List of retry delays in seconds
        """
        if backoff_schedule is None:
            backoff_schedule = [60, 300, 900, 3600, 14400, 86400]

        failures = self.get_failures(entity_id) or EntityFailures(entity_id=entity_id)
        existing = failures.failures.get(stage_pattern)

        now = datetime.now()
        if existing:
            attempts = existing.attempts + 1
            first_failed_at = existing.first_failed_at
        else:
            attempts = 1
            first_failed_at = now.isoformat()

        # Calculate next retry time
        if attempts - 1 < len(backoff_schedule):
            delay = backoff_schedule[attempts - 1]
        else:
            delay = backoff_schedule[-1] * 2  # Double last delay

        from datetime import timedelta

        next_retry = now + timedelta(seconds=delay)

        failures.failures[stage_pattern] = FailureInfo(
            error=error,
            error_details=error_details,
            attempts=attempts,
            first_failed_at=first_failed_at,
            last_failed_at=now.isoformat(),
            next_retry_at=next_retry.isoformat(),
        )
        self._write_failures(failures)

    def clear_failure(self, entity_id: str, stage_pattern: str) -> None:
        """Clear failure record for a stage.

        Args:
            entity_id: Entity identifier
            stage_pattern: State pattern for the stage
        """
        failures = self.get_failures(entity_id)
        if not failures:
            return

        if stage_pattern in failures.failures:
            del failures.failures[stage_pattern]
            if failures.failures:
                self._write_failures(failures)
            else:
                # No more failures, delete file
                self._failures_path(entity_id).unlink(missing_ok=True)

    def get_failures(self, entity_id: str) -> EntityFailures | None:
        """Get failure records for an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            EntityFailures or None if no failures
        """
        path = self._failures_path(entity_id)
        if not path.exists():
            return None

        data = json.loads(path.read_text())
        failures_dict = {k: FailureInfo(**v) for k, v in data.get("failures", {}).items()}
        return EntityFailures(entity_id=entity_id, failures=failures_dict)

    def get_failure(self, entity_id: str, stage_pattern: str) -> FailureInfo | None:
        """Get failure info for a specific stage.

        Args:
            entity_id: Entity identifier
            stage_pattern: State pattern for the stage

        Returns:
            FailureInfo or None if no failure recorded
        """
        failures = self.get_failures(entity_id)
        if not failures:
            return None
        return failures.failures.get(stage_pattern)

    def should_retry(self, entity_id: str, stage_pattern: str) -> bool:
        """Check if a failed stage should be retried.

        Args:
            entity_id: Entity identifier
            stage_pattern: State pattern for the stage

        Returns:
            True if retry time has passed
        """
        failure = self.get_failure(entity_id, stage_pattern)
        if not failure:
            return True  # No failure = can try

        next_retry = datetime.fromisoformat(failure.next_retry_at)
        return datetime.now() >= next_retry

    def _write_failures(self, failures: EntityFailures) -> None:
        """Write failures to disk."""
        self.failures_dir.mkdir(parents=True, exist_ok=True)
        path = self._failures_path(failures.entity_id)

        data = {
            "entity_id": failures.entity_id,
            "failures": {
                k: {
                    "error": v.error,
                    "error_details": v.error_details,
                    "attempts": v.attempts,
                    "first_failed_at": v.first_failed_at,
                    "last_failed_at": v.last_failed_at,
                    "next_retry_at": v.next_retry_at,
                }
                for k, v in failures.failures.items()
            },
        }
        path.write_text(json.dumps(data, indent=2))

    def _failures_path(self, entity_id: str) -> Path:
        """Get path to failures file for an entity."""
        safe_id = entity_id.replace("/", "_")
        return self.failures_dir / f"{safe_id}.json"

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _resolve_path(self, pattern: str, entity_id: str) -> Path:
        """Resolve a pattern to a full path.

        Args:
            pattern: State pattern
            entity_id: Entity identifier

        Returns:
            Full path to the state file
        """
        variables = extract_variables_from_entity_id(pattern, entity_id)
        rel_path = resolve_pattern(pattern, variables)
        return self.root / rel_path
