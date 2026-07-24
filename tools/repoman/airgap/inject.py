# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

"""Inject airgap pytest and [repo_test] into base_project (shared with containerize_airgap)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

REPO_TEST_SECTION = "\n".join(
    [
        "",
        "[repo_test]",
        'default_suite = "alltests"',
        "",
        "[repo_test.suites.alltests]",
        "# The airgap container runs without GPU (no nvidia runtime available on the",
        "# Docker-in-Docker CI runner).  Exclude tests that need Vulkan/GPU init.",
        "exclude = [",
        '    "*_setup${shell_ext}",',
        '    "*_messaging${shell_ext}",',
        '    "*_ui_extension${shell_ext}",',
        "]",
        "",
        "[repo_test.suites.airgap]",
        'kind = "pytest"',
        'discover_path = "${root}/tools/tests/airgap"',
        'log_file = "${root}/_testoutput/pytest_results.xml"',
        'extra_pytest_args = ["-v", "-s"]',
        "",
    ]
)


def inject_airgap_test_into_base_project(
    base_project_dir: Path,
    source_test_file: Path,
) -> None:
    """Copy test_kat_airgap.py and append [repo_test.suites.airgap] to base_project/repo.toml."""
    test_dest = base_project_dir / "tools" / "tests" / "airgap"
    test_dest.mkdir(parents=True, exist_ok=True)
    dest_file = test_dest / "test_kat_airgap.py"
    shutil.copy2(source_test_file, dest_file)

    base_repo_toml = base_project_dir / "repo.toml"
    if not base_repo_toml.is_file():
        raise FileNotFoundError(f"base_project repo.toml not found: {base_repo_toml}")

    content = base_repo_toml.read_text(encoding="utf-8")
    if "[repo_test]" not in content:
        content += REPO_TEST_SECTION
        base_repo_toml.write_text(content, encoding="utf-8")


def find_base_project_under_extract(extract_root: Path) -> Path:
    """Return path to base_project given extracted airgap package root."""
    direct = extract_root / "base_project"
    if direct.is_dir():
        return direct
    # Some zips have a single top-level directory
    for child in extract_root.iterdir():
        if child.is_dir():
            nested = child / "base_project"
            if nested.is_dir():
                return nested
    raise FileNotFoundError(f"Could not find base_project under {extract_root}")


def find_new_project_script(extract_root: Path) -> Path:
    """Locate new_project.bat or new_project.sh under extracted airgap tree."""
    for name in ("new_project.bat", "new_project.sh"):
        direct = extract_root / name
        if direct.is_file():
            return direct
    for child in extract_root.iterdir():
        if child.is_dir():
            for name in ("new_project.bat", "new_project.sh"):
                p = child / name
                if p.is_file():
                    return p
    raise FileNotFoundError(f"Could not find new_project script under {extract_root}")
