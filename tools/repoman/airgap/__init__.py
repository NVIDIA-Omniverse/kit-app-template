# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#
"""Local airgap test workflow: fetch NGC artifacts, prepare KAT project, clear caches, run tests."""

from .api import (
    clear_caches,
    fetch_assets,
    get_base_version,
    prepare_kat_project,
    run_airgap_tests,
)
from .precache_exts import (
    precache_version_locked_extensions,
)
from .types import (
    AirgapState,
    ClearCacheOptions,
    ClearCacheResult,
    FetchOptions,
    FetchResult,
    PrepareOptions,
    PrepareResult,
    RunTestsOptions,
)

__all__ = [
    "AirgapState",
    "ClearCacheOptions",
    "ClearCacheResult",
    "FetchOptions",
    "FetchResult",
    "PrepareOptions",
    "PrepareResult",
    "RunTestsOptions",
    "clear_caches",
    "fetch_assets",
    "get_base_version",
    "precache_version_locked_extensions",
    "prepare_kat_project",
    "run_airgap_tests",
]
