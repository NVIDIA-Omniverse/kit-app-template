# SPDX-FileCopyrightText: Copyright (c) 2023-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
import argparse
import logging
from typing import Callable, Dict

import omni.repo.man
import packmanapi
from omni.repo.man import print_log

logger = logging.getLogger(__name__)


def fetch_dependencies():
    """Fetch dependencies using repo build --fetch-only.

    This is needed because public-deps.packman.xml imports _build/target-deps/kit/${config}/dev/all-deps.packman.xml,
    which is generated during the build process.
    """
    print_log("Fetching dependencies...")
    repo_cmd = f"{omni.repo.man.resolve_tokens('${root}/repo')}{omni.repo.man.resolve_tokens('${shell_ext}')}"
    omni.repo.man.run_process(
        [repo_cmd, "build", "--fetch-only", "-r", "--/repo/tokens/cache=true"],
        exit_on_error=True,
    )


def run_verify_deps(options: argparse.Namespace, config: Dict):
    if options.verbose:
        packmanapi.set_verbosity_level(packmanapi.VERBOSITY_HIGH)

    tool_config = config.get("repo_verify_deps", {})
    deps_files = tool_config.get("deps_files") or []
    platforms = tool_config.get("platforms") or ["linux-x86_64", "windows-x86_64"]
    build_configs = tool_config.get("build_configs") or ["release", "debug"]
    remotes = tool_config.get("remotes") or ["cloudfront"]

    # Fetch dependencies once before verification
    fetch_dependencies()

    csv = []
    for platform in platforms:
        platform_target_abi = omni.repo.man.get_abi_platform_translation(
            platform, abi_version=omni.repo.man.resolve_tokens("$abi")
        )
        tokens = omni.repo.man.get_tokens(platform=platform)
        tokens["platform_host"] = platform
        tokens["platform_target_abi"] = platform_target_abi
        for build_config in build_configs:
            tokens["config"] = build_config
            for depsFile in deps_files:
                print_log(f"Verifying deps `{depsFile}` for platform={platform} config={build_config}")
                _, missing = packmanapi.verify(
                    depsFile,
                    platform=platform_target_abi,
                    tokens=tokens,
                    exclude_local=True,
                    remotes=remotes,
                    tags={"public": "true"},
                )

                for remote, package in missing:
                    logger.error(
                        f"Failed: {package.name}@{package.version} is missing from {remote} for platform={platform} config={build_config}"
                    )
                    csv.append(f"{package.name},{package.version},{remote.partition('packman:')[-1]}")

    if not csv:
        print_log("Verification Passed.")
    else:
        with open(f"_repo/missing_deps.csv", "w") as f:
            f.write("\n".join(["name,version,remote"] + sorted(set(csv))))
        raise omni.repo.man.RepoToolError("Verification Failed")


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Callable:
    parser.description = "Tool to verify whether packman dependencies are public"
    tool_config = config.get("repo_verify_deps", {})
    if not tool_config.get("enabled", True):
        return None

    return run_verify_deps
