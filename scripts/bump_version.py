#!/usr/bin/env python3
"""Bump version for logurich across all files."""

import re
import subprocess
import sys
from pathlib import Path


def validate_version(version: str) -> bool:
    """Validate version format (x.y.z)."""
    pattern = r"^\d+\.\d+\.\d+$"
    return bool(re.match(pattern, version))


def update_pyproject_toml(root: Path, new_version: str) -> None:
    """Update version in pyproject.toml."""
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text()

    pattern = r'^version = "[^"]+"'
    replacement = f'version = "{new_version}"'
    new_content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)

    pyproject.write_text(new_content)
    print("  Updated pyproject.toml")


def update_init_py(root: Path, new_version: str) -> None:
    """Update __version__ in __init__.py."""
    init_file = root / "src" / "logurich" / "__init__.py"
    content = init_file.read_text()

    pattern = r'^__version__ = "[^"]+"'
    replacement = f'__version__ = "{new_version}"'
    new_content = re.sub(pattern, replacement, content, count=1, flags=re.MULTILINE)

    init_file.write_text(new_content)
    print("  Updated src/logurich/__init__.py")


def update_uv_lock(root: Path) -> None:
    """Run uv lock to update uv.lock with new version."""
    print("  Running uv lock to update uv.lock...")
    result = subprocess.run(
        ["uv", "lock"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Warning: uv lock failed: {result.stderr}")
    else:
        print("  Updated uv.lock")


def get_current_version(root: Path) -> str:
    """Get current version from pyproject.toml."""
    pyproject = root / "pyproject.toml"
    content = pyproject.read_text()
    match = re.search(r'^version = "([^"]+)"', content, re.MULTILINE)
    return match.group(1) if match else "unknown"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/bump_version.py <version>")
        print("Example: uv run python scripts/bump_version.py 0.8.0")
        return 1

    new_version = sys.argv[1]

    if not validate_version(new_version):
        print(f"Error: Invalid version format '{new_version}'")
        print("Version must be in format: x.y.z (e.g., 0.8.0, 1.0.0)")
        return 1

    root = Path(__file__).parent.parent
    current_version = get_current_version(root)

    print(f"Bumping version: {current_version} -> {new_version}")
    print()

    update_pyproject_toml(root, new_version)
    update_init_py(root, new_version)
    update_uv_lock(root)

    print()
    print(f"Version bumped to {new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
