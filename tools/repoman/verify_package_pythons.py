# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Detect duplicate Packman Python revisions in Kit SDK airgap archives."""

from __future__ import annotations

import argparse
import sys
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

_PYTHON_CACHE_PATH = ("_cache", "packman", "python")
_PLATFORM_MARKERS = ("-manylinux_", "-windows-", "-linux-", "-macos-")


def get_package_base_version(package_directory: str) -> str:
    """Remove the target-platform suffix from a Packman package directory."""
    marker_positions = [package_directory.find(marker) for marker in _PLATFORM_MARKERS]
    marker_positions = [position for position in marker_positions if position >= 0]
    return package_directory[: min(marker_positions)] if marker_positions else package_directory


def find_python_packages(archive: Path) -> dict[str, set[str]]:
    """Return Packman Python package directories grouped by base version."""
    packages: dict[str, set[str]] = defaultdict(set)
    with zipfile.ZipFile(archive) as package_zip:
        for member in package_zip.namelist():
            parts = PurePosixPath(member).parts
            for index in range(len(parts) - len(_PYTHON_CACHE_PATH)):
                if parts[index : index + len(_PYTHON_CACHE_PATH)] != _PYTHON_CACHE_PATH:
                    continue
                package_index = index + len(_PYTHON_CACHE_PATH)
                if package_index < len(parts):
                    package_directory = parts[package_index]
                    packages[get_package_base_version(package_directory)].add(package_directory)
                break
    return dict(packages)


def verify_archive(archive: Path) -> bool:
    """Print a diagnostic and return whether an archive has one Python revision."""
    print(f"Checking Packman Python cache in {archive}")
    packages = find_python_packages(archive)

    if not packages:
        print("  PASS: no top-level _cache/packman/python packages were found.")
        return True

    for version, directories in sorted(packages.items()):
        print(f"  Python package revision: {version}")
        for directory in sorted(directories):
            print(f"    _cache/packman/python/{directory}")

    if len(packages) == 1:
        print("  PASS: the package contains one Packman Python revision.")
        return True

    print(
        "ERROR: the package contains multiple top-level Packman Python revisions.\n"
        "Dependencies or build tools are pinning different Python packages, which increases the package size and "
        "security-maintenance surface. Align those pins so _cache/packman/python contains one revision.\n"
        "Carbonite scripting-python variants under carb_sdk are intentionally outside this check."
    )
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path, help="Kit SDK airgap ZIP archive(s) to inspect")
    args = parser.parse_args(argv)

    missing = [archive for archive in args.archives if not archive.is_file()]
    if missing:
        for archive in missing:
            print(f"ERROR: package archive does not exist: {archive}", file=sys.stderr)
        return 1

    try:
        results = [verify_archive(archive) for archive in args.archives]
    except zipfile.BadZipFile as error:
        print(f"ERROR: could not inspect package archive: {error}", file=sys.stderr)
        return 1
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
