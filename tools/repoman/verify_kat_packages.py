# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Dict, List, Optional

import omni.repo.man
import packmanapi

logger = logging.getLogger(__name__)

PACKAGE_NAMES = ["kit_core_templates", "kit_sample_templates"]

# Known platform ABI suffixes that appear at the end of version strings
PLATFORM_PATTERN = re.compile(r"\.(manylinux_[^\s]+|linux[_-][^\s]+|windows[_-][^\s]+)$")

# Leading MAJOR.MINOR.PATCH at the start of a SemVer-style version string.
MAJOR_MINOR_PATCH_PATTERN = re.compile(r"^(\d+\.\d+\.\d+)")


def get_major_minor_patch(version_str: str) -> Optional[str]:
    """Extract the leading MAJOR.MINOR.PATCH from a SemVer-style version string."""
    if not version_str:
        return None
    match = MAJOR_MINOR_PATCH_PATTERN.match(version_str)
    return match.group(1) if match else None


def parse_kat_version(version_str: str) -> Optional[Dict]:
    """Parse a KAT package version string into components.

    Expected format: MAJOR.MINOR.PATCH+branch.build_number.git_hash.suffix.platform_abi
    Example: 110.0.0+main.9520.939494e7.gl.manylinux_2_35_x86_64

    Returns:
        Dict with keys: full, base, branch, build_number, git_hash, platform, prefix
        or None if the version string doesn't match the expected format.
    """
    if "+" not in version_str:
        logger.warning(f"Version string missing build metadata separator '+': {version_str}")
        return None

    base, metadata = version_str.split("+", 1)

    # Strip platform suffix
    platform_match = PLATFORM_PATTERN.search(metadata)
    platform = platform_match.group(1) if platform_match else None
    metadata_no_platform = PLATFORM_PATTERN.sub("", metadata)

    # Split remaining metadata: branch.build_number.git_hash[.suffix...]
    parts = metadata_no_platform.split(".")
    if len(parts) < 3:
        logger.warning(f"Unexpected metadata format in version: {version_str}")
        return None

    branch = parts[0]
    try:
        build_number = int(parts[1])
    except ValueError:
        logger.warning(f"Non-numeric build number '{parts[1]}' in version: {version_str}")
        return None

    git_hash = parts[2]

    return {
        "full": version_str,
        "base": base,
        "branch": branch,
        "build_number": build_number,
        "git_hash": git_hash,
        "platform": platform,
        "prefix": f"{base}+{branch}",
    }


def strip_platform(version_str: str) -> str:
    """Remove trailing platform ABI suffix from a version string."""
    return PLATFORM_PATTERN.sub("", version_str)


def get_latest_version(package_name: str, prefix: str, verbose: bool = False) -> Optional[Dict]:
    """Query packman for the latest version of a package matching a prefix.

    Args:
        package_name: Packman package name (e.g. 'kit_core_templates').
        prefix: Version prefix to filter by (e.g. '110.0.0+main').
        verbose: Log additional detail about filtering.

    Returns:
        Parsed version dict for the latest matching version, or None.
    """
    all_versions: dict = packmanapi.list_files(f"{package_name}")
    all_versions = all_versions["packman:cloudfront"]

    if verbose:
        omni.repo.man.print_log(f"  packmanapi.list_files('{package_name}') returned {len(all_versions)} version(s)")

    matching = []
    for v in all_versions:
        if not v.startswith(prefix):
            continue
        # Reject longer-MMP false positives, e.g. prefix '110.1.1' matching '110.1.10'.
        # The next character must be a SemVer separator: '+' (build), '-' (prerelease), '.' (deeper prerelease).
        next_char = v[len(prefix) : len(prefix) + 1]
        if next_char and next_char not in ("+", "-", "."):
            continue
        parsed = parse_kat_version(v)
        if parsed:
            matching.append(parsed)

    if verbose:
        omni.repo.man.print_log(f"  {len(matching)} version(s) match prefix '{prefix}'")

    if not matching:
        return None

    # Sort by build number descending — highest is latest
    matching.sort(key=lambda p: p["build_number"], reverse=True)

    if verbose and len(matching) > 1:
        top = matching[:5]
        omni.repo.man.print_log("  Top versions by build number:")
        for m in top:
            omni.repo.man.print_log(f"    {m['full']}  (build {m['build_number']})")

    return matching[0]


def read_package_versions(xml_path: Path) -> Dict[str, str]:
    """Read current version strings for KAT packages from the packman XML.

    Returns:
        Dict mapping package name to its current version string.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    versions = {}
    for package in root.iter("package"):
        name = package.get("name")
        if name in PACKAGE_NAMES:
            versions[name] = package.get("version", "")
    return versions


def read_kit_kernel_version(xml_path: Path) -> Optional[str]:
    """Read the kit-kernel package version from kit-sdk.packman.xml."""
    if not xml_path.is_file():
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for package in root.iter("package"):
        if package.get("name") == "kit-kernel":
            return package.get("version", "")
    return None


def update_package_versions(xml_path: Path, updates: Dict[str, str]) -> None:
    """Write updated version strings back to the packman XML.

    Args:
        xml_path: Path to repo-deps.packman.xml.
        updates: Dict mapping package name to new version string.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    for package in root.iter("package"):
        name = package.get("name")
        if name in updates:
            package_name = updates[name].split("@")[1].strip(".zip")
            package.set("version", package_name)  # Ensure we don't accidentally write a .zip suffix

    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def run_repo_tool(options: argparse.Namespace, config: Dict):
    verbose = getattr(options, "verbose", False)
    dry_run = getattr(options, "dry_run", False)
    update = getattr(options, "update", False)

    if verbose:
        packmanapi.set_verbosity_level(packmanapi.VERBOSITY_HIGH)

    is_ci = omni.repo.man.get_ci_platform() != "local"

    if is_ci and update:
        omni.repo.man.print_log("WARNING: --update is ignored on CI. Running in verification-only mode.")
        update = False

    xml_path = Path(omni.repo.man.resolve_tokens("${root}")) / "tools" / "deps" / "repo-deps.packman.xml"
    if not xml_path.is_file():
        raise omni.repo.man.RepoToolError(f"Packman deps file not found: {xml_path}")

    # Cross-check against kit-sdk.packman.xml: when KAT packages drift from the kit-kernel
    # MAJOR.MINOR.PATCH, search packman for the kit-kernel MMP rather than continuing to
    # look for newer builds of an already-stale MMP.
    kit_sdk_xml = Path(omni.repo.man.resolve_tokens("${root}")) / "tools" / "deps" / "kit-sdk.packman.xml"
    kit_kernel_version = read_kit_kernel_version(kit_sdk_xml)
    target_mmp = get_major_minor_patch(kit_kernel_version) if kit_kernel_version else None
    if not target_mmp:
        omni.repo.man.print_log(
            f"WARNING: Could not determine kit-kernel MAJOR.MINOR.PATCH from {kit_sdk_xml}; "
            f"falling back to per-package version base."
        )
    elif verbose:
        omni.repo.man.print_log(f"kit-sdk.packman.xml kit-kernel: {kit_kernel_version}")
        omni.repo.man.print_log(f"Target MAJOR.MINOR.PATCH: {target_mmp}")

    current_versions = read_package_versions(xml_path)
    if not current_versions:
        raise omni.repo.man.RepoToolError(f"No KAT packages ({', '.join(PACKAGE_NAMES)}) found in {xml_path}")

    results = {}  # package_name -> {current, latest, is_current}
    updates = {}  # package_name -> new_version (only if update needed)

    for name in PACKAGE_NAMES:
        current_full = current_versions.get(name)
        if not current_full:
            omni.repo.man.print_log(f"WARNING: Package '{name}' not found in {xml_path}")
            results[name] = {"current": None, "latest": None, "is_current": True}
            continue

        parsed_current = parse_kat_version(current_full)
        if not parsed_current:
            omni.repo.man.print_log(f"WARNING: Could not parse version for '{name}': {current_full}")
            results[name] = {"current": current_full, "latest": None, "is_current": True}
            continue

        current_mmp = get_major_minor_patch(parsed_current["base"])
        mmp_mismatch = bool(target_mmp and current_mmp and current_mmp != target_mmp)

        # On MMP mismatch, broaden the search to any version at the kit-sdk MMP
        # (any prerelease, any branch). When MMPs match, keep the prerelease-aware
        # search by using the full SemVer base.
        if mmp_mismatch:
            search_query = f"{name}@{target_mmp}"
        else:
            search_query = f"{name}@{parsed_current['base']}"

        omni.repo.man.print_log(f"Checking {name} (current: {current_full})")

        if verbose:
            omni.repo.man.print_log(f"  Base: {parsed_current['base']}")
            omni.repo.man.print_log(f"  Branch: {parsed_current['branch']}")
            omni.repo.man.print_log(f"  Build number: {parsed_current['build_number']}")
            omni.repo.man.print_log(f"  Search query: {search_query}")

        latest = get_latest_version(name, search_query, verbose=verbose)

        if not latest:
            omni.repo.man.print_log(f"  No versions found matching prefix '{search_query}'")
            results[name] = {"current": current_full, "latest": None, "is_current": True}
            continue

        # When MMPs differ, build numbers across MMPs are not comparable; treat as stale.
        if mmp_mismatch:
            is_current = False
        else:
            is_current = parsed_current["build_number"] >= latest["build_number"]

        results[name] = {
            "current": current_full,
            "latest": latest["full"],
            "is_current": is_current,
        }

        if is_current:
            omni.repo.man.print_log(f"  UP TO DATE (build {parsed_current['build_number']})")
        else:
            if mmp_mismatch:
                omni.repo.man.print_log(f"  STALE: MAJOR.MINOR.PATCH {current_mmp} -> {target_mmp}")
            else:
                omni.repo.man.print_log(f"  STALE: build {parsed_current['build_number']} -> {latest['build_number']}")
            omni.repo.man.print_log(f"    Current: {current_full}")
            omni.repo.man.print_log(f"    Latest:  {latest['full']}")
            updates[name] = latest["full"]

    # Summary
    omni.repo.man.print_log("")
    omni.repo.man.print_log("=== Summary ===")
    any_stale = False
    for name in PACKAGE_NAMES:
        r = results.get(name)
        if not r:
            continue
        status = "CURRENT" if r["is_current"] else "STALE"
        if not r["is_current"]:
            any_stale = True
        omni.repo.man.print_log(f"  {name}: {status}")
        if r["current"]:
            omni.repo.man.print_log(f"    Current: {r['current']}")
        if r["latest"] and not r["is_current"]:
            omni.repo.man.print_log(f"    Latest:  {r['latest']}")

    if any_stale:
        if is_ci:
            raise omni.repo.man.RepoToolError("KAT package version(s) are not current. See summary above.")
        elif update:
            if dry_run:
                omni.repo.man.print_log("")
                omni.repo.man.print_log(
                    "DRY RUN: Would update the following versions in "
                    f"{xml_path.relative_to(Path(omni.repo.man.resolve_tokens('${root}')))}:"
                )
                for name, new_ver in updates.items():
                    omni.repo.man.print_log(f"  {name}: {results[name]['current']} -> {new_ver}")
            else:
                omni.repo.man.print_log("")
                omni.repo.man.print_log(f"Updating {xml_path.name}...")
                update_package_versions(xml_path, updates)
                for name, new_ver in updates.items():
                    omni.repo.man.print_log(f"  Updated {name}: {results[name]['current']} -> {new_ver}")
                omni.repo.man.print_log("Done.")
        else:
            omni.repo.man.print_log("")
            omni.repo.man.print_log("Run with --update to apply changes (local only).")
    else:
        omni.repo.man.print_log("")
        omni.repo.man.print_log("All KAT packages are up to date.")


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Callable:
    parser.description = (
        "Verify that kit_core_templates and kit_sample_templates in "
        "repo-deps.packman.xml are at the latest published version for their branch."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging and packman debug output.")
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run", help="Show what would be updated without modifying files."
    )
    parser.add_argument(
        "--update", action="store_true", help="Update repo-deps.packman.xml with latest versions (ignored on CI)."
    )
    return run_repo_tool
