"""Code versioning for agent updates.

Computes a version hash based on all code files that agents need.
When this hash changes, agents should update.
"""

import hashlib
from pathlib import Path

# Root of the project
PROJECT_ROOT = Path(__file__).parent.parent

# Directories containing code that agents need
CODE_DIRS = [
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "modules",
    PROJECT_ROOT / "agent",
]

# File extensions to include
CODE_EXTENSIONS = {".py"}


def get_code_files() -> list[Path]:
    """Get all code files that contribute to the version hash."""
    files = []
    for code_dir in CODE_DIRS:
        if code_dir.exists():
            for ext in CODE_EXTENSIONS:
                files.extend(code_dir.rglob(f"*{ext}"))
    # Sort for deterministic ordering
    return sorted(files)


def compute_code_hash() -> str:
    """Compute a hash of all code files.

    Returns a short hash string that changes when any code file changes.
    """
    hasher = hashlib.sha256()

    for file_path in get_code_files():
        # Skip test files - they don't affect execution
        if "_test.py" in file_path.name or file_path.name.startswith("test_"):
            continue
        # Skip __pycache__
        if "__pycache__" in str(file_path):
            continue

        try:
            content = file_path.read_bytes()
            # Include file path (relative) to detect renames/moves
            rel_path = file_path.relative_to(PROJECT_ROOT)
            hasher.update(str(rel_path).encode())
            hasher.update(content)
        except (OSError, ValueError):
            # Skip files we can't read
            continue

    # Return first 12 chars of hex digest (enough to be unique)
    return hasher.hexdigest()[:12]


def get_code_version() -> str:
    """Get the current code version string.

    Format: {hash}
    """
    return compute_code_hash()


# Cache the version at module load time for performance
_cached_version: str | None = None


def get_cached_code_version() -> str:
    """Get cached code version (computed once at startup)."""
    global _cached_version
    if _cached_version is None:
        _cached_version = get_code_version()
    return _cached_version


def clear_version_cache() -> None:
    """Clear the cached version (for testing)."""
    global _cached_version
    _cached_version = None
