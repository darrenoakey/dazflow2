"""Tests for git operations module."""

import subprocess


from src.git import (
    GitCommit,
    ensure_gitignore,
    git_add,
    git_commit,
    git_diff,
    git_has_changes,
    git_init,
    git_log,
    git_show,
    is_git_repo,
)


# ##################################################################
# test is_git_repo
def test_is_git_repo_false(tmp_path):
    """Non-git directory returns False."""
    assert not is_git_repo(str(tmp_path))


def test_is_git_repo_true(tmp_path):
    """Git repository returns True."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    assert is_git_repo(str(tmp_path))


# ##################################################################
# test git_init
def test_git_init_creates_repo(tmp_path):
    """git_init creates a git repository."""
    assert git_init(str(tmp_path))
    assert is_git_repo(str(tmp_path))


def test_git_init_idempotent(tmp_path):
    """git_init can be called on existing repo."""
    git_init(str(tmp_path))
    assert git_init(str(tmp_path))  # Should not fail


# ##################################################################
# test git_add
def test_git_add_file(tmp_path):
    """git_add stages a file."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello")
    assert git_add("test.txt", str(tmp_path))


def test_git_add_nonexistent_file(tmp_path):
    """git_add returns False for nonexistent file."""
    git_init(str(tmp_path))
    assert not git_add("nonexistent.txt", str(tmp_path))


# ##################################################################
# test git_commit
def test_git_commit_with_staged_changes(tmp_path):
    """git_commit creates a commit when there are staged changes."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello")
    git_add("test.txt", str(tmp_path))
    assert git_commit("Test commit", str(tmp_path))


def test_git_commit_without_changes(tmp_path):
    """git_commit returns False when there are no staged changes."""
    git_init(str(tmp_path))
    # Need at least one commit for git to work properly
    (tmp_path / "initial.txt").write_text("init")
    git_add("initial.txt", str(tmp_path))
    git_commit("Initial", str(tmp_path))
    # Now try to commit with no changes
    assert not git_commit("Empty commit", str(tmp_path))


# ##################################################################
# test git_diff
def test_git_diff_staged(tmp_path):
    """git_diff returns staged changes."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello")
    git_add("test.txt", str(tmp_path))
    diff = git_diff(staged=True, cwd=str(tmp_path))
    assert "hello" in diff


def test_git_diff_unstaged(tmp_path):
    """git_diff returns unstaged changes."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("v1")
    git_add("test.txt", str(tmp_path))
    git_commit("Initial", str(tmp_path))
    (tmp_path / "test.txt").write_text("v2")
    diff = git_diff(cwd=str(tmp_path))
    assert "v2" in diff


def test_git_diff_specific_file(tmp_path):
    """git_diff can filter to specific file."""
    git_init(str(tmp_path))
    (tmp_path / "a.txt").write_text("aaa")
    (tmp_path / "b.txt").write_text("bbb")
    git_add("a.txt", str(tmp_path))
    git_add("b.txt", str(tmp_path))
    diff = git_diff("a.txt", staged=True, cwd=str(tmp_path))
    assert "aaa" in diff
    assert "bbb" not in diff


# ##################################################################
# test git_log
def test_git_log_empty_repo(tmp_path):
    """git_log returns empty list for repo with no commits."""
    git_init(str(tmp_path))
    commits = git_log(cwd=str(tmp_path))
    assert commits == []


def test_git_log_returns_commits(tmp_path):
    """git_log returns commit history."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello")
    git_add("test.txt", str(tmp_path))
    git_commit("First commit", str(tmp_path))
    commits = git_log(cwd=str(tmp_path))
    assert len(commits) == 1
    assert commits[0].message == "First commit"
    assert isinstance(commits[0], GitCommit)


def test_git_log_multiple_commits(tmp_path):
    """git_log returns multiple commits in order."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("v1")
    git_add("test.txt", str(tmp_path))
    git_commit("First", str(tmp_path))
    (tmp_path / "test.txt").write_text("v2")
    git_add("test.txt", str(tmp_path))
    git_commit("Second", str(tmp_path))
    commits = git_log(cwd=str(tmp_path))
    assert len(commits) == 2
    assert commits[0].message == "Second"
    assert commits[1].message == "First"


def test_git_log_for_specific_file(tmp_path):
    """git_log can filter to specific file."""
    git_init(str(tmp_path))
    (tmp_path / "a.txt").write_text("aaa")
    git_add("a.txt", str(tmp_path))
    git_commit("Add a", str(tmp_path))
    (tmp_path / "b.txt").write_text("bbb")
    git_add("b.txt", str(tmp_path))
    git_commit("Add b", str(tmp_path))
    commits = git_log("a.txt", cwd=str(tmp_path))
    assert len(commits) == 1
    assert commits[0].message == "Add a"


def test_git_log_limit(tmp_path):
    """git_log respects limit parameter."""
    git_init(str(tmp_path))
    for i in range(5):
        (tmp_path / "test.txt").write_text(f"v{i}")
        git_add("test.txt", str(tmp_path))
        git_commit(f"Commit {i}", str(tmp_path))
    commits = git_log(limit=2, cwd=str(tmp_path))
    assert len(commits) == 2


# ##################################################################
# test git_show
def test_git_show_file_at_commit(tmp_path):
    """git_show returns file content at specific commit."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("version1")
    git_add("test.txt", str(tmp_path))
    git_commit("First", str(tmp_path))
    commits = git_log(cwd=str(tmp_path))
    content = git_show(commits[0].hash, "test.txt", str(tmp_path))
    assert content == "version1"


def test_git_show_old_version(tmp_path):
    """git_show returns old file content."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("old")
    git_add("test.txt", str(tmp_path))
    git_commit("First", str(tmp_path))
    (tmp_path / "test.txt").write_text("new")
    git_add("test.txt", str(tmp_path))
    git_commit("Second", str(tmp_path))
    commits = git_log(cwd=str(tmp_path))
    old_content = git_show(commits[1].hash, "test.txt", str(tmp_path))
    assert old_content == "old"
    new_content = git_show(commits[0].hash, "test.txt", str(tmp_path))
    assert new_content == "new"


def test_git_show_nonexistent_commit(tmp_path):
    """git_show returns None for nonexistent commit."""
    git_init(str(tmp_path))
    content = git_show("nonexistent", "test.txt", str(tmp_path))
    assert content is None


def test_git_show_nonexistent_file(tmp_path):
    """git_show returns None for nonexistent file."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello")
    git_add("test.txt", str(tmp_path))
    git_commit("First", str(tmp_path))
    commits = git_log(cwd=str(tmp_path))
    content = git_show(commits[0].hash, "other.txt", str(tmp_path))
    assert content is None


# ##################################################################
# test ensure_gitignore
def test_ensure_gitignore_creates_file(tmp_path):
    """ensure_gitignore creates .gitignore with required entries."""
    ensure_gitignore(str(tmp_path))
    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert "local/" in content
    assert "agents.json" in content


def test_ensure_gitignore_adds_missing_entries(tmp_path):
    """ensure_gitignore adds missing entries to existing file."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n")
    ensure_gitignore(str(tmp_path))
    content = gitignore.read_text()
    assert "*.pyc" in content
    assert "local/" in content


def test_ensure_gitignore_idempotent(tmp_path):
    """ensure_gitignore doesn't duplicate entries."""
    ensure_gitignore(str(tmp_path))
    ensure_gitignore(str(tmp_path))
    gitignore = tmp_path / ".gitignore"
    content = gitignore.read_text()
    assert content.count("local/") == 1


# ##################################################################
# test git_has_changes
def test_git_has_changes_true(tmp_path):
    """git_has_changes returns True when there are staged changes."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello")
    git_add("test.txt", str(tmp_path))
    assert git_has_changes(cwd=str(tmp_path))


def test_git_has_changes_false(tmp_path):
    """git_has_changes returns False when there are no staged changes."""
    git_init(str(tmp_path))
    (tmp_path / "test.txt").write_text("hello")
    git_add("test.txt", str(tmp_path))
    git_commit("Commit", str(tmp_path))
    assert not git_has_changes(cwd=str(tmp_path))


def test_git_has_changes_specific_file(tmp_path):
    """git_has_changes can check specific file."""
    git_init(str(tmp_path))
    (tmp_path / "a.txt").write_text("aaa")
    (tmp_path / "b.txt").write_text("bbb")
    git_add("a.txt", str(tmp_path))
    assert git_has_changes("a.txt", str(tmp_path))
    assert not git_has_changes("b.txt", str(tmp_path))
