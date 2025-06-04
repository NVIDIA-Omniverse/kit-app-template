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
from repoman_bootstrapper import repoman_bootstrap

REPO_ROOT = os.path.join(os.path.dirname(os.path.normpath(__file__)), "../..")
REPO_DEPS_FILE = Path(REPO_ROOT) / "tools/deps/repo-deps.packman.xml"
OPT_DEPS_FILE = Path(REPO_ROOT) / "tools/deps/repo-deps-nv.packman.xml"
REPO_CACHE_FILE = os.path.join(REPO_ROOT, "repo-cache.json")


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
    repoman_bootstrap()
    bootstrap()

    with warnings.catch_warnings(record=True):
        # Ignore repo_changelog missing warnings associated with
        # repo_kit_tools. repo_kit_tools will warn if changelog is missing
        # but we do not use changelog functionality in kit-app-template.
        warnings.filterwarnings("ignore", message=r".*repo_changelog.*")
        import omni.repo.man

        omni.repo.man.main(REPO_ROOT)
