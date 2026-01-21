"""Code packaging for agent distribution.

Creates a zip package of all code files that agents need to execute nodes locally.
"""

import io
import zipfile
from pathlib import Path

from .code_version import PROJECT_ROOT, get_code_files, get_cached_code_version


def get_package_files() -> list[tuple[Path, str]]:
    """Get all files to include in the package with their archive paths.

    Returns list of (absolute_path, archive_path) tuples.
    """
    files = []

    for file_path in get_code_files():
        # Skip test files
        if "_test.py" in file_path.name or file_path.name.startswith("test_"):
            continue
        # Skip __pycache__
        if "__pycache__" in str(file_path):
            continue

        try:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            files.append((file_path, str(rel_path)))
        except ValueError:
            # File not under PROJECT_ROOT, skip
            continue

    return files


def create_code_package() -> bytes:
    """Create a zip package of all agent code.

    Returns the zip file as bytes.
    """
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path, archive_path in get_package_files():
            try:
                zf.write(abs_path, archive_path)
            except (OSError, ValueError):
                # Skip files we can't read
                continue

        # Add requirements.txt for dependency installation
        requirements_path = PROJECT_ROOT / "requirements.txt"
        if requirements_path.exists():
            zf.write(requirements_path, "requirements.txt")

        # Add a version file
        version = get_cached_code_version()
        zf.writestr("VERSION", version)

    return buffer.getvalue()


def get_package_manifest() -> dict:
    """Get manifest of all files in the package.

    Returns dict with version and file list.
    """
    files = []
    for abs_path, archive_path in get_package_files():
        try:
            size = abs_path.stat().st_size
            files.append({"path": archive_path, "size": size})
        except OSError:
            continue

    return {
        "version": get_cached_code_version(),
        "files": files,
        "file_count": len(files),
    }
