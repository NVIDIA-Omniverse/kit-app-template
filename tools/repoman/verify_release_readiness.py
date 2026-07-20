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
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import omni.repo.man
import toml
from omni.repo.man import print_log

logger = logging.getLogger(__name__)


def get_kit_kernel_version() -> str:
    """Extract kit-kernel version from packman XML file."""
    xml_path = Path(omni.repo.man.resolve_tokens("${root}/tools/deps/kit-sdk.packman.xml"))
    if not xml_path.exists():
        raise omni.repo.man.RepoToolError(f"Kit SDK packman file not found: {xml_path}")

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for package in root.findall(".//package"):
            if package.get("name") == "kit-kernel":
                full_version = package.get("version")
                # Extract base version (e.g., "109.0.0" from "109.0.0+master.235603.536b49ae.gl.${platform}.${config}")
                base_version = full_version.split("+")[0]
                return base_version

        raise omni.repo.man.RepoToolError("kit-kernel package not found in packman XML")
    except ET.ParseError as e:
        raise omni.repo.man.RepoToolError(f"Failed to parse packman XML: {e}")


def get_repo_deploy_exts_branches(config: Dict) -> List[str]:
    """Extract branch names from repo_deploy_exts configuration."""
    repo_deploy_exts = config.get("repo_deploy_exts", {})
    pipeline_repo = repo_deploy_exts.get("pipeline_repo", {})
    branch_config = pipeline_repo.get("branch", {})

    return list(branch_config.keys())


def extract_version_scopes_from_branches(branches: List[str]) -> List[str]:
    """Extract version scopes from branch names like 'prod-109', 'integ-110.2', or 'prod-110.2.0'."""
    version_scopes = []
    for branch in branches:
        match = re.search(r"-(\d+(?:\.\d+){0,2})$", branch)
        if match:
            version_scopes.append(match.group(1))

    return sorted(set(version_scopes))


def version_scope_matches_kit(scope: str, kit_version: str) -> bool:
    """Return whether a deploy_exts branch version scope matches the Kit kernel version prefix."""
    scope_parts = scope.split(".")
    kit_parts = kit_version.split(".")
    return kit_parts[: len(scope_parts)] == scope_parts


def is_release_candidate() -> bool:
    """Check if VERSION.md contains '-rc' indicating a release candidate."""
    version_file = Path(omni.repo.man.resolve_tokens("${root}/VERSION.md"))
    if not version_file.exists():
        logger.warning("VERSION.md file not found")
        return False

    with open(version_file, "r") as f:
        content = f.read().strip()

    return "-rc" in content


def _get_kit_kernel_hash_from_packman(xml_path: Path) -> str | None:
    """Extract kit kernel hash from packman XML if version string contains it. Returns None if not present."""
    with open(xml_path) as f:
        content = f.read()

    # Version string may include hash: e.g. "110.0.0+feature.274308.5f0ed89a.gl.${platform}.${config}"
    version_match = re.search(r'version="[^"]*\+[^.]+\.\d+\.([a-f0-9]+)\.gl', content)
    if not version_match:
        return None

    git_hash = version_match.group(1)
    if not re.match(r"^[a-f0-9]{8}$", git_hash):
        raise omni.repo.man.RepoToolError(f"Invalid kit kernel hash format in packman XML: {git_hash!r}")
    return git_hash


def _get_kit_kernel_hash_from_kit_binary() -> str | None:
    """Run kit --help and parse hash from 'Kit Version: ...hash.gl' line. Returns None if unavailable."""
    root = Path(omni.repo.man.resolve_tokens("${root}"))
    # Use repo/carb tokens for platform and executable (matches repo.toml kit_path)
    kit_path_templates = [
        "${root}/_build/${platform}/release/kit${exe_ext}",
        "${root}/_build/target-deps/kit/release/kit${exe_ext}",
    ]
    for template in kit_path_templates:
        kit_path = Path(omni.repo.man.resolve_tokens(template))
        if not kit_path.exists():
            continue
        try:
            _code, lines = omni.repo.man.utils.run_process_return_output(
                [str(kit_path), "--help"],
                quiet=True,
                print_stdout=False,
                print_stderr=False,
                cwd=str(root),
            )
            out = "\n".join(lines) if lines else ""
            # Last line is typically "Kit Version: 110.0.0+feature.276876.4a5123f4.gl"
            m = re.search(r"Kit Version:\s*\S+\.([a-f0-9]{8})\.gl", out)
            if m:
                return m.group(1)
        except Exception as e:
            # Expected when kit is missing, wrong arch, or not runnable; try next path.
            logger.debug("Kit kernel hash probe failed for %s: %s", kit_path, e)
            continue
    return None


@lru_cache(maxsize=1)
def get_kit_kernel_hash() -> str:
    """Extract kit kernel hash from packman XML or kit binary (kit --help). Cached per process."""
    xml_path = Path(omni.repo.man.resolve_tokens("${root}/tools/deps/kit-sdk.packman.xml"))
    if not xml_path.exists():
        raise omni.repo.man.RepoToolError(f"Kit SDK packman file not found: {xml_path}")

    git_hash = _get_kit_kernel_hash_from_packman(xml_path)
    if git_hash:
        return git_hash

    git_hash = _get_kit_kernel_hash_from_kit_binary()
    if git_hash:
        return git_hash

    raise omni.repo.man.RepoToolError(
        "Kit kernel hash not found: packman version string no longer contains hash, "
        "and kit binary (kit --help) could not be used to get version hash. "
        "Run `repo build --fetch-only --release` before verify so kit is available under "
        "_build/target-deps/kit/release/ or _build/${platform}/release/, or use a full "
        "kit-kernel version string in kit-sdk.packman.xml."
    )


def check_registries_reachable() -> Tuple[List[str], List[str]]:
    """Check if all registries defined in repo.toml are reachable."""
    # Load repo.toml
    repo_toml_path = Path(omni.repo.man.resolve_tokens("${root}/repo.toml"))
    with open(repo_toml_path) as f:
        repo_config = toml.load(f)

    unreachable_registries = []
    skipped_registries = []

    # Get kit version info for token resolution
    kit_version = get_kit_kernel_version()
    kit_kernel_hash = get_kit_kernel_hash()
    version_parts = kit_version.split(".")
    additional_tokens = {
        "kit_version_major": version_parts[0],
        "kit_version_short": f"{version_parts[0]}.{version_parts[1]}",
        "kit_git_hash": kit_kernel_hash,
    }

    # Check all registries in all mapping configurations
    for mapping_name, mapping_config in repo_config["registry_mapping"].items():
        # Skip entire mapping if skip_reachable_check is set
        if mapping_config.get("skip_reachable_check", False):
            print_log(f"Skipping reachable check for {mapping_name} registries.")
            continue

        registries = mapping_config["registries"]

        for registry in registries:
            # Resolve any tokens in the URL
            url = omni.repo.man.resolve_tokens(registry["url"])

            # Resolve additional tokens
            for token, value in additional_tokens.items():
                url = url.replace(f"${{{token}}}", value)

            # Skip omniverse:// URLs as they require special handling with omni.client
            if url.startswith("omniverse://"):
                skipped_registries.append(url)
                continue
            if not url.endswith("shared"):
                # Only check shared registries - kit/sdk registry won't exist until after kit-sdk-public is merged.
                skipped_registries.append(url)
                continue

            # Default index format and version
            default_index_format = "summaries.gz"
            default_index_version = "v2"

            # Append /v2/summaries.gz to the URL to check registry reachability
            check_url = f"{url}/{default_index_version}/{default_index_format}"

            try:
                # Try to fetch the URL
                req = urllib.request.Request(
                    check_url, headers={"User-Agent": "Mozilla/5.0"}  # Some servers require a user agent
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200:
                        unreachable_registries.append((check_url, f"Status code: {response.status}"))
            except urllib.error.URLError as e:
                unreachable_registries.append((check_url, str(e.reason)))
            except Exception as e:
                unreachable_registries.append((check_url, str(e)))

    return unreachable_registries, skipped_registries


def validate_deploy_exts_branch_compatibility(config: Dict) -> List[str]:
    """
    Validate that kit-kernel version is compatible with repo_deploy_exts branch configuration.

    Branches can be broad major-scoped targets such as "prod-110" or narrower release-scoped
    targets such as "integ-110.2" and "prod-110.2.0". Each configured branch scope must match
    the corresponding prefix of the kit-kernel version.

    Args:
        config: Repository configuration dictionary containing repo_deploy_exts settings

    Returns:
        List of error messages (empty if validation passes)

    Example:
        Kit version "109.0.0" matches branches ["prod-109", "integ-109"]
        Kit version "110.2.0" matches branches ["prod-110.2", "integ-110.2"]
        Kit version "108.5.2" fails against branches ["prod-109", "integ-109"]
    """
    validation_errors = []

    print_log("=== Checking kit version vs deploy_exts branch compatibility ===")

    # Get kit-kernel version
    kit_version = get_kit_kernel_version()

    print_log(f"Kit-kernel version: {kit_version}")

    # Get repo_deploy_exts branch configuration
    branches = get_repo_deploy_exts_branches(config)
    if branches:
        print_log(f"Configured deploy_exts branches: {branches}")

        branch_version_scopes = extract_version_scopes_from_branches(branches)
        print_log(f"Version scopes from deploy_exts branches: {branch_version_scopes}")

        if not branch_version_scopes:
            error_msg = (
                f"Could not extract deploy_exts version scopes from branches {branches}. "
                "Please use branch names such as prod-110, integ-110.2, or prod-110.2.0."
            )
            validation_errors.append(error_msg)
        else:
            mismatched_scopes = [
                scope for scope in branch_version_scopes if not version_scope_matches_kit(scope, kit_version)
            ]
            if mismatched_scopes:
                error_msg = (
                    f"Kit-kernel version '{kit_version}' does not match deploy_exts branch version scopes "
                    f"{mismatched_scopes}. Please update repo_deploy_exts branch configuration in repo.toml "
                    f"to match kit-kernel version {kit_version}"
                )
                validation_errors.append(error_msg)
            else:
                print_log(f"PASS: Kit version {kit_version} matches deploy_exts branch scopes {branch_version_scopes}")
    else:
        print_log("No repo_deploy_exts branches configured - skipping deploy_exts compatibility check")

    return validation_errors


def check_registry_reachability_validation() -> List[str]:
    """
    Check if all configured registries are reachable.
    Returns list of error messages (empty if no errors).
    """
    validation_errors = []

    print_log("\n=== Checking registry reachability ===")

    unreachable_registries, skipped_registries = check_registries_reachable()

    if skipped_registries:
        print_log("Skipped registries (omniverse:// URLs or non-shared):")
        for url in skipped_registries:
            print_log(f"  - {url}")

    # Check for unreachable registries, but allow integ/prod to be unreachable in dev builds
    if unreachable_registries:
        version_file = Path(omni.repo.man.resolve_tokens("${root}/VERSION.md"))
        current_version = ""
        if version_file.exists():
            with open(version_file, "r") as f:
                current_version = f.read().strip()

        # All registry issues should be treated as warnings, but provide context for integ/prod in dev
        if "dev" in current_version.lower():
            integ_prod_unreachable = []
            other_unreachable = []

            for url, error in unreachable_registries:
                if any(stage in url.lower() for stage in ["integ", "prod", "production"]):
                    integ_prod_unreachable.append((url, error))
                else:
                    other_unreachable.append((url, error))

            if integ_prod_unreachable:
                print_log("Integ/prod registries are unreachable (may not be provisioned yet for this version):")
                for url, error in integ_prod_unreachable:
                    print_log(f"  - {url}: {error}")

            # All unreachable registries should produce warnings in dev builds
            if unreachable_registries:
                registry_error = "The following registries are not reachable:\n" + "\n".join(
                    [f"  - {url}: {error}" for url, error in unreachable_registries]
                )
                validation_errors.append(registry_error)
        else:
            # For non-dev builds, all unreachable registries are errors
            registry_error = "The following registries are not reachable:\n" + "\n".join(
                [f"  - {url}: {error}" for url, error in unreachable_registries]
            )
            validation_errors.append(registry_error)
    else:
        print_log("PASS: All registries are reachable")

    return validation_errors


def run_verify_release_readiness(options: argparse.Namespace, config: Dict):
    """
    Verify release readiness by performing comprehensive validation checks:

    1. Deploy Extensions Branch Compatibility:
       Validates that kit-kernel major version matches repo_deploy_exts branch configuration
       to ensure extensions are deployed to the correct registry branches
       ALWAYS causes hard failure (exit code 1) if validation fails

    2. Registry Reachability:
       Verifies that all configured extension registries are accessible and responsive
       ALWAYS produces warning only (exit code 2) if validation fails - allows pipeline to continue
    """
    is_rc = is_release_candidate()
    print_log(f"Is release candidate (VERSION.md contains '-rc'): {is_rc}")

    try:
        # Run deploy_exts branch compatibility check - hard failure on error
        deploy_exts_errors = validate_deploy_exts_branch_compatibility(config)

        # Run registry reachability check - warning only on error
        registry_errors = check_registry_reachability_validation()

        # Handle deploy_exts errors (hard failure)
        if deploy_exts_errors:
            print_log("\n=== Deploy Extensions Branch Compatibility Errors ===")
            for i, error in enumerate(deploy_exts_errors, 1):
                print_log(f"{i}. {error}")
            logger.error("Deploy extensions branch compatibility validation failed")
            raise omni.repo.man.RepoToolError("Deploy extensions branch compatibility validation failed")

        # Handle registry errors (warning only - don't fail the job)
        if registry_errors:
            print_log("\n=== Registry Reachability Warnings ===")
            for i, error in enumerate(registry_errors, 1):
                print_log(f"WARNING {i}: {error}")
            logger.warning("Registry reachability validation failed - continuing with warnings")
            print_log("WARNING: Registry reachability issues found, but continuing pipeline")
            print_log("VALIDATION_WARNINGS_FOUND=true")

        # All checks passed
        if registry_errors:
            print_log("\nRESULT: Job completed with registry warnings")
        else:
            print_log("\nPASS: All release readiness checks passed")

    except Exception as e:
        # All exceptions from deploy_exts checks should be hard failures
        logger.error(f"Release readiness validation failed: {e}")
        raise omni.repo.man.RepoToolError(f"Validation failed: {e}")


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Callable:
    parser.description = (
        "Tool to verify release readiness by checking deploy_exts branch compatibility and registry reachability"
    )

    return run_verify_release_readiness
