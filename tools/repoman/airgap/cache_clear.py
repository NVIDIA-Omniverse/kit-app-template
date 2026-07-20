# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

"""Clear Omniverse-related caches for airgap validation (profiles: airgap vs full)."""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from .types import ClearCacheOptions, ClearCacheResult, Profile

logger = logging.getLogger(__name__)


def _remove_directory_contents(path: Path) -> bool:
    """Remove contents of directory; keep directory. Returns True if cleared or empty."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        return True
    if not path.is_dir():
        return False
    for item in list(path.iterdir()):
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                try:
                    item.unlink()
                except OSError:
                    pass
        except OSError:
            if sys.platform == "win32" and item.is_file():
                try:
                    os.chmod(item, stat.S_IWRITE)
                    item.unlink()
                except OSError:
                    subprocess.run(
                        ["cmd", "/c", "del", "/f", "/q", str(item)],
                        check=False,
                        capture_output=True,
                    )
            else:
                shutil.rmtree(item, ignore_errors=True) if item.is_dir() else None
    return True


def _airgap_profile_paths() -> List[Tuple[Path, str]]:
    """Paths safe to clear without removing global packman (Omniverse app/runtime caches)."""
    paths: List[Tuple[Path, str]] = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            p = Path(local) / "ov"
            paths.append((p, "Omniverse application data (%LOCALAPPDATA%/ov)"))
    else:
        home = Path.home()
        paths.append((home / ".local" / "share" / "ov", "Omniverse application data (~/.local/share/ov)"))
        paths.append((home / ".cache" / "ov", "Omniverse cache (~/.cache/ov)"))
    return paths


def _full_profile_extra_paths() -> List[Tuple[Path, str]]:
    """Additional paths for --profile full (destructive for offline repo if packman cleared)."""
    extra: List[Tuple[Path, str]] = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            lp = Path(local)
            extra.append((lp / "uv" / "cache", "uv cache"))
            extra.append((lp / "NVIDIA" / "DXCache" / "Omniverse", "NVIDIA DXCache Omniverse"))
            extra.append((lp / "NVIDIA" / "GLCache", "NVIDIA GLCache"))
        pm = os.environ.get("PM_PACKAGES_ROOT")
        if pm:
            extra.append((Path(pm), "Packman (PM_PACKAGES_ROOT)"))
        else:
            sd = os.environ.get("SystemDrive", "C:")
            extra.append((Path(f"{sd}\\packman-repo"), "Packman default (C:\\packman-repo)"))
    else:
        home = Path.home()
        extra.append((home / ".cache" / "packman", "Packman default"))
        extra.append((home / ".cache" / "uv", "uv cache"))
        extra.append((home / ".cache" / "pip", "pip cache"))
        pm = os.environ.get("PM_PACKAGES_ROOT")
        if pm:
            extra.append((Path(pm), "Packman (PM_PACKAGES_ROOT)"))
    return extra


def clear_caches_impl(options: ClearCacheOptions) -> ClearCacheResult:
    """Non-interactive cache clearing. API entry used by cli and CI."""
    result = ClearCacheResult(effective_env=dict(options.session_env or {}))

    to_clear: List[Tuple[Path, str]] = _airgap_profile_paths()
    if options.profile == "full":
        to_clear = to_clear + _full_profile_extra_paths()
    elif options.profile == "airgap":
        pass
    else:
        raise ValueError(f"Unknown profile: {options.profile}")

    if options.profile == "full" and options.preserve_packman:
        filtered: List[Tuple[Path, str]] = []
        for p, desc in to_clear:
            if "Packman" in desc or "packman" in desc.lower():
                result.skipped_paths.append(p)
                continue
            filtered.append((p, desc))
        to_clear = filtered

    logger.info("Cache clear profile: %s (%d directories to process)", options.profile, len(to_clear))

    for path, desc in to_clear:
        if options.interactive_confirm:
            pass
        if not path.exists():
            logger.info("  [skip] %s — does not exist (%s)", desc, path)
            result.cleared_paths.append(path)
            continue
        try:
            logger.info("  [clearing] %s (%s) ...", desc, path)
            if _remove_directory_contents(path):
                logger.info("  [cleared]  %s", desc)
                result.cleared_paths.append(path)
            else:
                logger.warning("  [failed]   %s — not a directory", desc)
                result.skipped_paths.append(path)
        except OSError as exc:
            logger.warning("  [skipped]  %s — %s", desc, exc)
            result.skipped_paths.append(path)

    return result
