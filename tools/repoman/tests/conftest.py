# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Fixtures for version lock tool tests.

These tests exercise pure-logic helpers that do NOT require Kit runtime or
repo_man bootstrapping.  The modules under test import ``omni.repo.man``
at the top level, so we provide a lightweight stub so pytest can collect
and run the tests without the full repo_man environment.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub out omni.repo.man and packmanapi so the modules can be imported
# without the repo_man bootstrap (they are only needed for path resolution
# and Kit invocation, which the unit tests never exercise).
# ---------------------------------------------------------------------------

_STUBS_INSTALLED = False


def _install_stubs():
    global _STUBS_INSTALLED
    if _STUBS_INSTALLED:
        return

    # omni -> omni.repo -> omni.repo.man
    omni_pkg = types.ModuleType("omni")
    omni_pkg.__path__ = []
    repo_pkg = types.ModuleType("omni.repo")
    repo_pkg.__path__ = []
    man_mod = MagicMock()
    man_mod.print_log = MagicMock()
    man_mod.resolve_tokens = MagicMock(return_value="/fake/root")
    man_mod.RepoToolError = type("RepoToolError", (Exception,), {})

    omni_pkg.repo = repo_pkg  # type: ignore[attr-defined]
    repo_pkg.man = man_mod  # type: ignore[attr-defined]

    sys.modules.setdefault("omni", omni_pkg)
    sys.modules.setdefault("omni.repo", repo_pkg)
    sys.modules.setdefault("omni.repo.man", man_mod)
    sys.modules.setdefault("packmanapi", MagicMock())

    _STUBS_INSTALLED = True


_install_stubs()

# Put the repoman directory on sys.path so ``import version_locks_common`` works
_repoman_dir = str(Path(__file__).resolve().parent.parent)
if _repoman_dir not in sys.path:
    sys.path.insert(0, _repoman_dir)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_team_file(tmp_path):
    """Create a minimal team TOML file and return its Path."""

    def _make(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    return _make


@pytest.fixture
def tmp_kit_file(tmp_path):
    """Create a minimal .kit file and return its Path."""

    def _make(name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(content)
        return p

    return _make
