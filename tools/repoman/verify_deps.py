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
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Dict, Iterable

import omni.repo.man
import packmanapi
from omni.repo.man import print_log

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MissingDependency:
    deps_file: str
    platform: str
    build_config: str
    remote: str
    package_name: str
    package_version: str


@contextmanager
def gitlab_log_section(name: str, title: str):
    """Collapse verbose Packman diagnostics in GitLab while keeping local output plain."""
    is_gitlab_ci = os.environ.get("GITLAB_CI") == "true"
    if is_gitlab_ci:
        print(f"\033[0Ksection_start:{int(time.time())}:{name}[collapsed=true]\r\033[0K{title}", flush=True)
    else:
        print_log(title)

    try:
        yield
    finally:
        if is_gitlab_ci:
            print(f"\033[0Ksection_end:{int(time.time())}:{name}\r\033[0K", flush=True)


def format_missing_dependencies(missing_dependencies: Iterable[MissingDependency]) -> str:
    """Format missing dependencies without repeating packages across checks."""
    grouped = {}
    for missing in missing_dependencies:
        key = (missing.package_name, missing.package_version, missing.remote)
        grouped.setdefault(key, set()).add((missing.deps_file, missing.platform, missing.build_config))

    lines = [f"Public dependency verification failed: {len(grouped)} unique package(s) are not public."]
    for (package_name, package_version, remote), checks in sorted(grouped.items()):
        lines.extend(
            [
                "",
                f"  {package_name}",
                f"    version: {package_version}",
                f"    remote:  {remote.partition('packman:')[-1]}",
                "    checks:",
            ]
        )
        for deps_file, platform, build_config in sorted(checks):
            lines.append(f"      - {platform} / {build_config} ({deps_file})")

    lines.extend(["", "Machine-readable report: _repo/missing_deps.csv"])
    return "\n".join(lines)


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

    missing_dependencies = []
    for platform in platforms:
        platform_target_abi = omni.repo.man.get_abi_platform_translation(
            platform, abi_version=omni.repo.man.resolve_tokens("$abi")
        )
        tokens = omni.repo.man.get_tokens(platform=platform)
        tokens["platform_host"] = platform
        tokens["platform_target_abi"] = platform_target_abi
        for build_config in build_configs:
            tokens["config"] = build_config
            for deps_file_index, deps_file in enumerate(deps_files):
                section_name = f"verify_deps_{platform}_{build_config}_{deps_file_index}".replace("-", "_")
                title = f"Packman details: {deps_file} | {platform} | {build_config}"
                with gitlab_log_section(section_name, title):
                    _, missing = packmanapi.verify(
                        deps_file,
                        platform=platform_target_abi,
                        tokens=tokens,
                        exclude_local=True,
                        remotes=remotes,
                        tags={"public": "true"},
                    )

                for remote, package in missing:
                    missing_dependencies.append(
                        MissingDependency(
                            deps_file=deps_file,
                            platform=platform,
                            build_config=build_config,
                            remote=remote,
                            package_name=package.name,
                            package_version=package.version,
                        )
                    )

    if not missing_dependencies:
        print_log("Verification Passed.")
    else:
        with open(f"_repo/missing_deps.csv", "w") as f:
            csv = {
                f"{missing.package_name},{missing.package_version},{missing.remote.partition('packman:')[-1]}"
                for missing in missing_dependencies
            }
            f.write("\n".join(["name,version,remote"] + sorted(csv)))
        logger.error(format_missing_dependencies(missing_dependencies))
        raise omni.repo.man.RepoToolError("Verification Failed")


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Callable:
    parser.description = "Tool to verify whether packman dependencies are public"
    tool_config = config.get("repo_verify_deps", {})
    if not tool_config.get("enabled", True):
        return None

    return run_verify_deps
