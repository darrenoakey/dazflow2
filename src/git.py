"""Git operations module for workflow version control.

Provides synchronous git operations using subprocess calls.
All functions are designed to be fast and non-blocking for typical git operations.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.config import get_config


@dataclass
class GitCommit:
    """Represents a git commit."""

    hash: str
    short_hash: str
    message: str
    author: str
    timestamp: int  # Unix timestamp
    timestamp_iso: str


def _run_git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    if cwd is None:
        cwd = get_config().data_dir
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def is_git_repo(path: str | None = None) -> bool:
    """Check if the directory is the root of its own git repository.

    Returns False if the directory is merely inside a parent git repo
    (e.g. a data dir nested inside a source repo).
    """
    if path is None:
        path = get_config().data_dir
    result = _run_git(["rev-parse", "--show-toplevel"], cwd=path)
    if result.returncode != 0:
        return False
    return Path(result.stdout.strip()).resolve() == Path(path).resolve()


def git_init(path: str | None = None) -> bool:
    """Initialize a git repository."""
    result = _run_git(["init"], cwd=path)
    return result.returncode == 0


def git_add(file_path: str, cwd: str | None = None) -> bool:
    """Stage a file for commit."""
    result = _run_git(["add", file_path], cwd=cwd)
    return result.returncode == 0


def git_commit(message: str, cwd: str | None = None) -> bool:
    """Create a commit with the given message."""
    result = _run_git(["commit", "-m", message], cwd=cwd)
    return result.returncode == 0


def git_diff(file_path: str | None = None, staged: bool = False, cwd: str | None = None) -> str:
    """Get the diff for a file or all files."""
    args = ["diff"]
    if staged:
        args.append("--staged")
    if file_path:
        args.extend(["--", file_path])
    result = _run_git(args, cwd=cwd)
    return result.stdout


def git_log(file_path: str | None = None, limit: int = 50, cwd: str | None = None) -> list[GitCommit]:
    """Get commit history for a file or the entire repo."""
    # Format: hash|short_hash|message|author|timestamp|timestamp_iso
    format_str = "%H|%h|%s|%an|%ct|%ci"
    args = ["log", f"--format={format_str}", f"-n{limit}"]
    if file_path:
        args.extend(["--follow", "--", file_path])

    result = _run_git(args, cwd=cwd)
    if result.returncode != 0:
        return []

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 5)
        if len(parts) >= 6:
            commits.append(
                GitCommit(
                    hash=parts[0],
                    short_hash=parts[1],
                    message=parts[2],
                    author=parts[3],
                    timestamp=int(parts[4]),
                    timestamp_iso=parts[5],
                )
            )
    return commits


def git_show(commit_hash: str, file_path: str, cwd: str | None = None) -> str | None:
    """Get file contents at a specific commit."""
    result = _run_git(["show", f"{commit_hash}:{file_path}"], cwd=cwd)
    if result.returncode != 0:
        return None
    return result.stdout


def ensure_gitignore(cwd: str | None = None) -> None:
    """Ensure .gitignore exists with proper exclusions for the data directory."""
    if cwd is None:
        cwd = get_config().data_dir

    gitignore_path = Path(cwd) / ".gitignore"
    required_entries = [
        "local/",
        "agents.json",
        "builtin_agent_secret",
        "tags.json",
        "concurrency_groups.json",
    ]

    existing = set()
    if gitignore_path.exists():
        existing = set(gitignore_path.read_text().strip().split("\n"))

    missing = [e for e in required_entries if e not in existing]
    if missing:
        with gitignore_path.open("a") as f:
            if existing and list(existing) != [""]:
                f.write("\n")
            f.write("\n".join(missing) + "\n")


def git_has_changes(file_path: str | None = None, cwd: str | None = None) -> bool:
    """Check if there are staged changes to commit."""
    args = ["diff", "--staged", "--quiet"]
    if file_path:
        args.extend(["--", file_path])
    result = _run_git(args, cwd=cwd)
    # Exit code 1 means there are changes, 0 means no changes
    return result.returncode == 1
