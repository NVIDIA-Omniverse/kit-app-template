# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

"""Precache version-locked extensions into a local folder.

Uses Kit's ``--ext-precache-mode`` to resolve all extensions listed in
``version_locks.kit`` from the standard registry.  The resulting folder
can be used as a local extension folder for offline / airgap builds.

Usage from Python::

    from airgap.precache_exts import precache_version_locked_extensions

    precache_version_locked_extensions(kit_binary, version_locks_kit, output_dir)

The output directory will contain one sub-directory per extension
(``name`` only, without version — via ``omitExtVersion``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def precache_version_locked_extensions(
    kit_binary: Path,
    version_locks_kit: Path,
    extscache_dir: Path,
) -> int:
    """Download all version-locked extensions into *extscache_dir*.

    Uses Kit's ``--ext-precache-mode`` with *version_locks_kit* as the app
    file to resolve all locked extensions from the standard registry.  Only
    fetches extensions compatible with the current platform.

    ``omitExtVersion`` is set so that cached directories use the extension
    name without a version or build-hash suffix (e.g. ``omni.anim.curve.bundle``
    instead of ``omni.anim.curve.bundle-1.4.0+110.0.0.u7f4``).  This makes the
    cache usable as a plain ``--ext-folder`` search path.

    Args:
        kit_binary: Path to the Kit executable.
        version_locks_kit: Path to the ``version_locks.kit`` file.
        extscache_dir: Output directory for cached extensions.

    Returns:
        Number of extension directories in *extscache_dir*.
    """
    extscache_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(kit_binary),
        str(version_locks_kit),
        "--ext-precache-mode",
        "--/app/extensions/registryEnabled=1",
        f"--/app/extensions/registryCacheFull={extscache_dir}",
        "--/exts/omni.kit.registry.nucleus/omitExtVersion=1",
        "--/app/enableStdoutOutput=1",
        "--/log/flushStandardStreamOutput=1",
    ]
    print(f"Precaching version-locked extensions into {extscache_dir} ...")
    print(f"  Kit binary: {kit_binary}")
    print(f"  Version locks: {version_locks_kit}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"WARNING: precache returned code {result.returncode} (some extensions may be missing)")

    ext_count = sum(1 for p in extscache_dir.iterdir() if p.is_dir() or p.is_symlink())
    print(f"  Precached {ext_count} extensions")
    return ext_count
