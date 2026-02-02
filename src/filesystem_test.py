"""Tests for filesystem module."""

import os
import tempfile
from pathlib import Path

import pytest

from .filesystem import (
    DirectoryEntry,
    DirectoryListing,
    PathInfo,
    check_path,
    expand_path,
    get_home_directory,
    list_directory,
)


class TestExpandPath:
    """Tests for expand_path function."""

    def test_expand_tilde(self):
        """Expands ~ to home directory."""
        result = expand_path("~/test")
        assert result == str(Path.home() / "test")

    def test_expand_tilde_only(self):
        """Expands ~ alone to home directory."""
        result = expand_path("~")
        assert result == str(Path.home())

    def test_no_expansion_needed(self):
        """Returns absolute path unchanged."""
        result = expand_path("/absolute/path")
        assert result == "/absolute/path"

    def test_expand_env_var(self):
        """Expands environment variables."""
        os.environ["TEST_VAR_XYZ"] = "/test/path"
        try:
            result = expand_path("$TEST_VAR_XYZ/subdir")
            assert result == "/test/path/subdir"
        finally:
            del os.environ["TEST_VAR_XYZ"]


class TestListDirectory:
    """Tests for list_directory function."""

    def test_list_directory_basic(self):
        """Lists directory contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files and directories
            Path(tmpdir, "dir1").mkdir()
            Path(tmpdir, "dir2").mkdir()
            Path(tmpdir, "file1.txt").write_text("content")
            Path(tmpdir, "file2.txt").write_text("content")

            result = list_directory(tmpdir)

            assert result.path == tmpdir
            assert result.error is None
            assert len(result.directories) == 2
            assert len(result.files) == 2

            dir_names = [d.name for d in result.directories]
            file_names = [f.name for f in result.files]

            assert "dir1" in dir_names
            assert "dir2" in dir_names
            assert "file1.txt" in file_names
            assert "file2.txt" in file_names

    def test_list_directory_hidden_files_excluded(self):
        """Hidden files are excluded by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, ".hidden").write_text("hidden")
            Path(tmpdir, ".hidden_dir").mkdir()
            Path(tmpdir, "visible.txt").write_text("visible")

            result = list_directory(tmpdir, show_hidden=False)

            assert len(result.directories) == 0
            assert len(result.files) == 1
            assert result.files[0].name == "visible.txt"

    def test_list_directory_show_hidden(self):
        """Hidden files are included when show_hidden=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, ".hidden").write_text("hidden")
            Path(tmpdir, ".hidden_dir").mkdir()
            Path(tmpdir, "visible.txt").write_text("visible")

            result = list_directory(tmpdir, show_hidden=True)

            assert len(result.directories) == 1
            assert len(result.files) == 2

            file_names = [f.name for f in result.files]
            assert ".hidden" in file_names
            assert "visible.txt" in file_names

    def test_list_directory_directories_only(self):
        """Only directories are returned when directories_only=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "dir1").mkdir()
            Path(tmpdir, "file1.txt").write_text("content")

            result = list_directory(tmpdir, directories_only=True)

            assert len(result.directories) == 1
            assert len(result.files) == 0
            assert result.directories[0].name == "dir1"

    def test_list_directory_not_found(self):
        """Returns error for non-existent directory."""
        result = list_directory("/nonexistent/path/xyz123")

        assert result.error == "Directory not found"
        assert len(result.directories) == 0
        assert len(result.files) == 0

    def test_list_directory_not_a_directory(self):
        """Returns error when path is a file, not a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir, "file.txt")
            file_path.write_text("content")

            result = list_directory(str(file_path))

            assert result.error == "Path is not a directory"

    def test_list_directory_expands_tilde(self):
        """Expands ~ in path."""
        result = list_directory("~")

        assert result.path == str(Path.home())
        assert result.error is None

    def test_list_directory_sorted_alphabetically(self):
        """Entries are sorted alphabetically (case-insensitive)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "Zebra").mkdir()
            Path(tmpdir, "apple").mkdir()
            Path(tmpdir, "Banana").mkdir()

            result = list_directory(tmpdir)

            names = [d.name for d in result.directories]
            assert names == ["apple", "Banana", "Zebra"]

    def test_list_directory_file_sizes(self):
        """File entries include size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir, "file.txt")
            file_path.write_text("hello")  # 5 bytes

            result = list_directory(tmpdir)

            assert len(result.files) == 1
            assert result.files[0].size == 5

    def test_list_directory_root_restriction_valid(self):
        """Allows paths within root restriction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, "subdir")
            subdir.mkdir()
            Path(subdir, "file.txt").write_text("content")

            result = list_directory(str(subdir), root_path=tmpdir)

            assert result.error is None
            assert len(result.files) == 1

    def test_list_directory_root_restriction_blocked(self):
        """Blocks paths outside root restriction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = list_directory("/tmp", root_path=tmpdir)

            assert result.error is not None
            assert "must be within" in result.error

    def test_list_directory_root_restriction_exact_root(self):
        """Allows listing the exact root path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "file.txt").write_text("content")

            result = list_directory(tmpdir, root_path=tmpdir)

            assert result.error is None
            assert len(result.files) == 1


class TestCheckPath:
    """Tests for check_path function."""

    def test_check_path_exists_file(self):
        """Returns correct info for existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir, "file.txt")
            file_path.write_text("content")

            result = check_path(str(file_path))

            assert result.exists is True
            assert result.is_directory is False

    def test_check_path_exists_directory(self):
        """Returns correct info for existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_path(tmpdir)

            assert result.exists is True
            assert result.is_directory is True

    def test_check_path_not_exists(self):
        """Returns correct info for non-existent path."""
        result = check_path("/nonexistent/path/xyz123")

        assert result.exists is False
        assert result.is_directory is None

    def test_check_path_expands_tilde(self):
        """Expands ~ in path."""
        result = check_path("~")

        assert result.path == str(Path.home())
        assert result.exists is True
        assert result.is_directory is True


class TestGetHomeDirectory:
    """Tests for get_home_directory function."""

    def test_returns_home_directory(self):
        """Returns the home directory path."""
        result = get_home_directory()

        assert result == str(Path.home())
        assert Path(result).exists()
        assert Path(result).is_dir()


class TestDirectoryEntry:
    """Tests for DirectoryEntry dataclass."""

    def test_directory_entry_fields(self):
        """DirectoryEntry has expected fields."""
        entry = DirectoryEntry(
            name="test",
            path="/path/to/test",
            is_directory=True,
            size=None,
        )

        assert entry.name == "test"
        assert entry.path == "/path/to/test"
        assert entry.is_directory is True
        assert entry.size is None

    def test_file_entry_with_size(self):
        """File entry includes size."""
        entry = DirectoryEntry(
            name="file.txt",
            path="/path/to/file.txt",
            is_directory=False,
            size=1234,
        )

        assert entry.is_directory is False
        assert entry.size == 1234


class TestPathInfo:
    """Tests for PathInfo dataclass."""

    def test_path_info_exists(self):
        """PathInfo for existing path."""
        info = PathInfo(path="/some/path", exists=True, is_directory=True)

        assert info.path == "/some/path"
        assert info.exists is True
        assert info.is_directory is True

    def test_path_info_not_exists(self):
        """PathInfo for non-existent path."""
        info = PathInfo(path="/nonexistent", exists=False)

        assert info.exists is False
        assert info.is_directory is None
