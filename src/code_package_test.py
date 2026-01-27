"""Tests for code packaging module."""

import zipfile
import io

from src.code_package import (
    get_package_files,
    create_code_package,
    get_package_manifest,
)


# ##################################################################
# test get_package_files returns tuples
def test_get_package_files_returns_tuples():
    files = get_package_files()
    assert len(files) > 0
    for abs_path, archive_path in files:
        assert abs_path.exists()
        assert isinstance(archive_path, str)


# ##################################################################
# test get_package_files excludes test files
def test_get_package_files_excludes_tests():
    files = get_package_files()
    for abs_path, archive_path in files:
        assert "_test.py" not in archive_path
        assert not archive_path.startswith("test_")


# ##################################################################
# test create_code_package returns bytes
def test_create_code_package_returns_bytes():
    package = create_code_package()
    assert isinstance(package, bytes)
    assert len(package) > 0


# ##################################################################
# test create_code_package is valid zip
def test_create_code_package_is_valid_zip():
    package = create_code_package()
    buffer = io.BytesIO(package)
    with zipfile.ZipFile(buffer, "r") as zf:
        # Should not raise BadZipFile
        names = zf.namelist()
        assert len(names) > 0


# ##################################################################
# test create_code_package contains version file
def test_create_code_package_contains_version():
    package = create_code_package()
    buffer = io.BytesIO(package)
    with zipfile.ZipFile(buffer, "r") as zf:
        assert "VERSION" in zf.namelist()
        version = zf.read("VERSION").decode()
        assert len(version) == 12  # Hash length


# ##################################################################
# test create_code_package contains python files
def test_create_code_package_contains_python_files():
    package = create_code_package()
    buffer = io.BytesIO(package)
    with zipfile.ZipFile(buffer, "r") as zf:
        py_files = [n for n in zf.namelist() if n.endswith(".py")]
        assert len(py_files) > 0


# ##################################################################
# test get_package_manifest returns dict
def test_get_package_manifest_returns_dict():
    manifest = get_package_manifest()
    assert isinstance(manifest, dict)
    assert "version" in manifest
    assert "files" in manifest
    assert "file_count" in manifest


# ##################################################################
# test get_package_manifest has correct file count
def test_get_package_manifest_file_count():
    manifest = get_package_manifest()
    assert manifest["file_count"] == len(manifest["files"])


# ##################################################################
# test get_package_manifest files have path and size
def test_get_package_manifest_file_structure():
    manifest = get_package_manifest()
    for f in manifest["files"]:
        assert "path" in f
        assert "size" in f
        assert isinstance(f["size"], int)
