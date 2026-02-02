"""Filesystem operations for directory browsing."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DirectoryEntry:
    """A directory entry (file or directory)."""

    name: str
    path: str
    is_directory: bool
    size: int | None = None  # Only for files


@dataclass
class DirectoryListing:
    """Result of listing a directory."""

    path: str
    directories: list[DirectoryEntry]
    files: list[DirectoryEntry]
    error: str | None = None


@dataclass
class PathInfo:
    """Information about a path."""

    path: str
    exists: bool
    is_directory: bool | None = None  # None if doesn't exist


def expand_path(path: str) -> str:
    """Expand ~ and environment variables in a path."""
    return os.path.expanduser(os.path.expandvars(path))


def list_directory(
    path: str,
    show_hidden: bool = False,
    directories_only: bool = False,
    root_path: str | None = None,
) -> DirectoryListing:
    """List contents of a directory.

    Args:
        path: Directory path to list (~ is expanded)
        show_hidden: Include hidden files (dotfiles)
        directories_only: Only return directories, not files
        root_path: If specified, path must be within this root (~ is expanded)

    Returns:
        DirectoryListing with directories and files
    """
    expanded_path = expand_path(path)

    # Validate root restriction
    if root_path:
        expanded_root = expand_path(root_path)
        try:
            # Resolve both to handle symlinks and relative paths
            resolved_path = Path(expanded_path).resolve()
            resolved_root = Path(expanded_root).resolve()

            # Check that path is within root
            try:
                resolved_path.relative_to(resolved_root)
            except ValueError:
                return DirectoryListing(
                    path=expanded_path,
                    directories=[],
                    files=[],
                    error=f"Path must be within {expanded_root}",
                )
        except (OSError, ValueError):
            return DirectoryListing(
                path=expanded_path,
                directories=[],
                files=[],
                error="Invalid path",
            )

    # Check if path exists and is a directory
    dir_path = Path(expanded_path)
    if not dir_path.exists():
        return DirectoryListing(
            path=expanded_path,
            directories=[],
            files=[],
            error="Directory not found",
        )

    if not dir_path.is_dir():
        return DirectoryListing(
            path=expanded_path,
            directories=[],
            files=[],
            error="Path is not a directory",
        )

    directories: list[DirectoryEntry] = []
    files: list[DirectoryEntry] = []

    try:
        for entry in sorted(dir_path.iterdir(), key=lambda e: e.name.lower()):
            name = entry.name

            # Skip hidden files unless requested
            if not show_hidden and name.startswith("."):
                continue

            if entry.is_dir():
                directories.append(
                    DirectoryEntry(
                        name=name,
                        path=str(entry),
                        is_directory=True,
                    )
                )
            elif not directories_only:
                # Get file size
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = None

                files.append(
                    DirectoryEntry(
                        name=name,
                        path=str(entry),
                        is_directory=False,
                        size=size,
                    )
                )
    except PermissionError:
        return DirectoryListing(
            path=expanded_path,
            directories=[],
            files=[],
            error="Permission denied",
        )
    except OSError as e:
        return DirectoryListing(
            path=expanded_path,
            directories=[],
            files=[],
            error=str(e),
        )

    return DirectoryListing(
        path=expanded_path,
        directories=directories,
        files=files,
    )


def check_path(path: str) -> PathInfo:
    """Check if a path exists and get its type.

    Args:
        path: Path to check (~ is expanded)

    Returns:
        PathInfo with exists and is_directory fields
    """
    expanded_path = expand_path(path)
    p = Path(expanded_path)

    if not p.exists():
        return PathInfo(path=expanded_path, exists=False)

    return PathInfo(
        path=expanded_path,
        exists=True,
        is_directory=p.is_dir(),
    )


def get_home_directory() -> str:
    """Get the user's home directory."""
    return str(Path.home())
