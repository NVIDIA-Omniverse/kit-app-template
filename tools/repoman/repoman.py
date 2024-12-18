# SPDX-FileCopyrightText: Copyright (c) 2019-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

import contextlib
import io
import json
import os
import sys
import warnings
from pathlib import Path

import packmanapi

REPO_ROOT = os.path.join(os.path.dirname(os.path.normpath(__file__)), "../..")
REPO_DEPS_FILE = Path(REPO_ROOT) / "tools/deps/repo-deps.packman.xml"
OPT_DEPS_FILE = Path(REPO_ROOT) / "tools/deps/repo-deps-nv.packman.xml"
REPO_CACHE_FILE = os.path.join(REPO_ROOT, "repo-cache.json")


def prep_cache_paths():
    """
    There are several environment variables that repo_man can optionally set to control where various caches are placed. They will all be relative to the repository root.
    - PM_PACKAGES_ROOT: this is where Packman stores its package cache
    - PIP_CACHE_DIR: this is where pip stores its wheel cache
    - UV_CACHE_DIR: this is where uv stores its wheel and package cache

    There are several gating flags as well to prevent repo_man from using the pip/uv default cache dir envvars unless explicitly set by us.
    - OM_PIP_CACHE: gating pip cache dir flag for omni.repo.man.deps.pip_install_requirements
    - OM_UV_CACHE: gating uv cache dir flag for omni.repo.man.deps._uv_requirements_load
    """

    repo_cache_file = Path(REPO_CACHE_FILE)
    if repo_cache_file.is_file():
        # cache file is present, read it in and set environment variables.
        cache_path_data = json.loads(repo_cache_file.read_text())
        # resolve REPO_ROOT rather than relative path to avoid any chdir shenanigans.
        resolved_root = Path(REPO_ROOT).resolve()

        for cache, cache_path in cache_path_data.items():
            # Expand $HOME and ~
            resolved_path = Path(os.path.expandvars(os.path.expanduser(cache_path)))
            if not resolved_path.is_dir():
                # Relative path to current working directory or absolute path is not present.
                # It's possible repo was somehow executed outside of the repository root.
                resolved_path = resolved_root / cache_path

            # Fully resolve path to avoid weird dir popping in some workflows.
            os.environ[cache] = resolved_path.resolve().as_posix()
            resolved_path.mkdir(parents=True, exist_ok=True)

            # Set repo_man breadcrumb to respect PIP_CACHE_DIR and UV_CACHE_DIR.
            # Unset OMNI_REPO_ROOT to force the caching of installed Python deps
            # in the packman cache dir.
            if cache == "PIP_CACHE_DIR":
                os.environ["OM_PIP_CACHE"] = "1"
                os.environ["OMNI_REPO_ROOT"] = ""
            elif cache == "UV_CACHE_DIR":
                os.environ["OM_UV_CACHE"] = "1"
                os.environ["OMNI_REPO_ROOT"] = ""


def bootstrap():
    """
    Bootstrap all omni.repo modules.

    Pull with packman from repo.packman.xml and add them all to python sys.path to enable importing.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        for file in [REPO_DEPS_FILE, OPT_DEPS_FILE]:
            if file.is_file():
                deps = packmanapi.pull(file.as_posix())

                for dep_path in deps.values():
                    if dep_path not in sys.path:
                        sys.path.append(dep_path)


if __name__ == "__main__":
    prep_cache_paths()
    bootstrap()

    with warnings.catch_warnings(record=True):
        # Ignore repo_changelog missing warnings associated with
        # repo_kit_tools. repo_kit_tools will warn if changelog is missing
        # but we do not use changelog functionality in kit-app-template.
        warnings.filterwarnings("ignore", message=r".*repo_changelog.*")
        import omni.repo.man

        omni.repo.man.main(REPO_ROOT)
