# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Smoke-test for tools/ci/publish.py via ``repo ci publish`` in dry-run mode.

Catches import errors (e.g. vendored dependency ordering), config issues, and
other problems that would cause the deploy-ngc CI job to fail at startup.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_is_windows = sys.platform == "win32"
_repo_cmd = str(REPO_ROOT / ("repo.bat" if _is_windows else "repo.sh"))


def test_publish_dry_run():
    """``repo ci publish`` must succeed in dry-run mode (no NGC credentials needed)."""
    env = os.environ.copy()
    env["DRY_RUN"] = "true"

    result = subprocess.run(
        [_repo_cmd, "ci", "publish"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, (
        f"repo ci publish (DRY_RUN=true) failed with exit code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-2000:]}\n"
        f"--- stderr ---\n{result.stderr[-2000:]}"
    )
