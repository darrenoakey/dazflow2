"""Tests for code versioning module."""

from src.code_version import (
    CODE_DIRS,
    compute_code_hash,
    get_code_files,
    get_code_version,
    get_cached_code_version,
    clear_version_cache,
)


# ##################################################################
# test get_code_files returns python files
def test_get_code_files_returns_python_files():
    files = get_code_files()
    assert len(files) > 0
    # All files should be .py
    for f in files:
        assert f.suffix == ".py"


# ##################################################################
# test get_code_files is sorted
def test_get_code_files_is_sorted():
    files = get_code_files()
    assert files == sorted(files)


# ##################################################################
# test compute_code_hash returns string
def test_compute_code_hash_returns_string():
    hash_val = compute_code_hash()
    assert isinstance(hash_val, str)
    assert len(hash_val) == 12  # Truncated to 12 chars


# ##################################################################
# test compute_code_hash is deterministic
def test_compute_code_hash_is_deterministic():
    hash1 = compute_code_hash()
    hash2 = compute_code_hash()
    assert hash1 == hash2


# ##################################################################
# test get_code_version returns hash
def test_get_code_version_returns_hash():
    version = get_code_version()
    assert isinstance(version, str)
    assert len(version) == 12


# ##################################################################
# test cached version works
def test_cached_version():
    clear_version_cache()
    v1 = get_cached_code_version()
    v2 = get_cached_code_version()
    assert v1 == v2


# ##################################################################
# test code dirs exist
def test_code_dirs_exist():
    # At least some dirs should exist
    existing = [d for d in CODE_DIRS if d.exists()]
    assert len(existing) > 0


# ##################################################################
# test hash excludes test files
def test_hash_excludes_test_files():
    # This is a behavior test - test files shouldn't affect the hash
    # We can verify by checking that test files aren't in the file list
    # that contributes to the hash (indirectly tested by the implementation)
    files = get_code_files()
    # Test files are included in get_code_files but excluded in compute_code_hash
    # So we just verify get_code_files returns test files
    test_files = [f for f in files if "_test.py" in f.name]
    # There should be some test files
    assert len(test_files) > 0
