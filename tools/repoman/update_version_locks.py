# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
"""
Update version locks for team TOML files.

Resolves LATEST versions from the extension registry and updates team TOML files.
Automatically runs resolve_version_locks after updating to regenerate the master lock file.

Usage:
    repo update_version_locks           # List team files
    repo update_version_locks --all     # Update all teams to latest versions
    repo update_version_locks --team X  # Update one team to latest versions
    repo update_version_locks --all --no-resolve  # Update without resolving (escape hatch)
"""

import argparse
import re
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import omni.repo.man
from omni.repo.man import print_log
from resolve_version_locks import resolve_version_locks as _resolve_version_locks
from version_locks_common import (
    check_version_conflicts,
    get_config,
    get_kit_path,
    get_root_dir,
    get_team_files,
    get_version_locks_dir,
    parse_extensions_from_kit_log,
    parse_team_toml,
    set_config,
)

# ---------------------------------------------------------------------------
# TOML file updates
# ---------------------------------------------------------------------------


def _update_team_toml(
    file_path: Path,
    new_versions: Dict[str, str],
) -> Tuple[List[Tuple[str, str, str]], int]:
    """
    Update versions in a team TOML file.

    Returns:
        (changes, total_count) where changes is list of (ext_name, old_ver, new_ver).
    """
    content = file_path.read_text()
    original_content = content
    changes: List[Tuple[str, str, str]] = []
    total_count = 0

    for ext_name, new_version in new_versions.items():
        # Match: "ext.name" = "old_version" and capture old version
        pattern = rf'("{re.escape(ext_name)}"\s*=\s*)"([^"]+)"'
        match = re.search(pattern, content)
        if match:
            total_count += 1
            old_version = match.group(2)
            if old_version != new_version:
                replacement = rf'\1"{new_version}"'
                content = re.sub(pattern, replacement, content)
                changes.append((ext_name, old_version, new_version))

    if content != original_content:
        file_path.write_text(content)

    return changes, total_count


def _generate_temp_kit_file(all_extensions: Dict[str, str]) -> str:
    """
    Generate a temporary .kit file for version resolution.
    Uses no version constraints so Kit resolves to latest.
    """
    lines = [
        "[package]",
        'title = "Temporary Version Lock Resolver"',
        'version = "1.0.0"',
        "",
        "[dependencies]",
        "# All extensions from team TOML files - let Kit resolve versions",
    ]

    for ext_name in sorted(all_extensions.keys()):
        lines.append(f'"{ext_name}" = {{}}')

    lines.append("")
    lines.append(
        "########################################################################################################################"
    )
    lines.append("# BEGIN GENERATED PART (Remove from 'BEGIN' to 'END' to regenerate)")
    lines.append(
        "########################################################################################################################"
    )
    lines.append("")
    lines.append("[settings.app.exts]")
    lines.append("enabled = []")
    lines.append("")
    lines.append(
        "########################################################################################################################"
    )
    lines.append("# END GENERATED PART")
    lines.append(
        "########################################################################################################################"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Python API
# ---------------------------------------------------------------------------


def list_team_files() -> List[Tuple[str, int]]:
    """
    List available team files with extension counts.

    Returns:
        List of (team_name, extension_count) tuples.
    """
    result = []
    for team_file in get_team_files():
        _, kat_exts, sample_exts = parse_team_toml(team_file)
        total = len(kat_exts) + len(sample_exts)
        short_name = team_file.stem.replace("team_", "")
        result.append((short_name, total))
    return result


def update_version_locks(
    team: Optional[str] = None,
    update_all: bool = False,
    skip_resolve: bool = False,
) -> Dict[str, List[Tuple[str, str, str]]]:
    """
    Update team TOML files to latest extension versions from registry.

    Args:
        team: Specific team name to update (e.g., "animation" or "team_animation").
              If None and update_all is False, raises error.
        update_all: If True, update all team files.
        skip_resolve: If True, skip running resolve_version_locks after updating.
                      Default is False (resolve runs automatically).

    Returns:
        Dict mapping team names to their changes: {team: [(ext, old_ver, new_ver), ...]}

    Raises:
        omni.repo.man.RepoToolError: On invalid team or resolution failure.
    """
    all_team_files = get_team_files()

    if not all_team_files:
        raise omni.repo.man.RepoToolError(f"No team TOML files found in {get_version_locks_dir()}")

    # Filter by team if specified
    team_files = all_team_files
    if team:
        team_name = team
        if not team_name.startswith("team_"):
            team_name = f"team_{team_name}"
        team_files = [f for f in all_team_files if f.stem == team_name]
        if not team_files:
            available = ", ".join(f.stem.replace("team_", "") for f in all_team_files)
            raise omni.repo.man.RepoToolError(f"Team '{team}' not found. Available: {available}")

    if not team and not update_all:
        raise omni.repo.man.RepoToolError("Must specify --team <name> or --all")

    # Step 1: Collect all extensions from team files
    print_log("=== Collecting extensions from team files ===")
    all_extensions: Dict[str, str] = {}

    for team_file in team_files:
        _, kat_exts, sample_exts = parse_team_toml(team_file)
        all_extensions.update({**kat_exts, **sample_exts})

    print_log(f"Found {len(all_extensions)} extensions across {len(team_files)} team files")

    # Step 2: Generate temporary kit file
    print_log("")
    print_log("=== Generating temporary kit file ===")

    root_dir = get_root_dir()
    temp_dir = Path(root_dir) / "_build" / "_version_lock_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_kit_path = temp_dir / "_temp_version_resolver.kit"
    temp_content = _generate_temp_kit_file(all_extensions)
    temp_kit_path.write_text(temp_content)
    print_log(f"Written: {temp_kit_path}")

    # Step 3: Run Kit to resolve versions
    print_log("")
    print_log("=== Running Kit to resolve versions ===")

    kit_path = get_kit_path()
    log_dir = Path(tempfile.gettempdir()) / "kit_update_version_locks"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "resolver.log"

    # Build dev registry overrides from repo.toml so Kit resolves against the
    # internal registry (kit-kernel ships with only prod registries).
    registry_args: List[str] = []
    dev_registries = get_config().dev_registries
    if dev_registries:
        for i, reg in enumerate(dev_registries):
            prefix = f"--/exts/omni.kit.registry.nucleus/registries/{i}"
            for key, value in reg.items():
                registry_args.append(f"{prefix}/{key}={value}")
        registry_names = [r.get("name", "?") for r in dev_registries]
        print_log(f"  Using dev registries: {', '.join(registry_names)}")

    args = [
        kit_path,
        str(temp_kit_path),
        "--no-window",
        "--/app/extensions/registryEnabled=1",
        "--/app/extensions/precacheMode=1",
        "--/app/hangDetector/enabled=false",
        "--update-exts",
        f"--/log/file={log_path}",
        "--/log/level=info",
    ] + registry_args

    try:
        omni.repo.man.run_process(args, exit_on_error=True)
    except BaseException:
        if temp_kit_path.exists():
            temp_kit_path.unlink()
        raise

    # Step 4: Parse resolved versions
    print_log("")
    print_log("=== Parsing resolved versions from Kit log ===")

    resolved_versions = parse_extensions_from_kit_log(log_path)
    print_log(f"Resolved {len(resolved_versions)} extension versions from log")

    # Clean up temp files
    if temp_kit_path.exists():
        temp_kit_path.unlink()
        print_log(f"Cleaned up: {temp_kit_path.name}")
    if log_path.exists():
        log_path.unlink()
        print_log(f"Cleaned up: {log_path.name}")

    # Step 5: Update team TOML files
    print_log("")
    print_log("=== Updating team TOML files ===")

    result: Dict[str, List[Tuple[str, str, str]]] = {}
    total_processed = 0

    for team_file in team_files:
        _, kat_exts, sample_exts = parse_team_toml(team_file)
        team_exts = {**kat_exts, **sample_exts}

        updates = {ext: ver for ext, ver in resolved_versions.items() if ext in team_exts}

        if updates:
            changes, processed = _update_team_toml(team_file, updates)
            total_processed += processed
            team_name = team_file.stem.replace("team_", "")
            result[team_name] = changes

            if changes:
                print_log(f"  {team_name}: {len(changes)} changed (of {processed})")
                for ext_name, old_ver, new_ver in changes:
                    print_log(f"    {ext_name}: {old_ver} -> {new_ver}")
            else:
                print_log(f"  {team_name}: up to date ({processed} extensions)")

    print_log("")
    total_changes = sum(len(c) for c in result.values())
    if total_changes:
        print_log(f"Total: {total_changes} versions changed (of {total_processed})")
    else:
        print_log(f"All {total_processed} extensions already at latest versions.")

    # Step 6: Validate for conflicts
    print_log("")
    print_log("=== Validating for conflicts ===")

    conflicts = check_version_conflicts(team_files)
    if conflicts:
        print_log("")
        print_log("WARNING: Version conflicts detected:")
        for conflict in conflicts:
            print_log(conflict)
    else:
        print_log("No conflicts detected.")

    # Step 7: Run resolve_version_locks unless skipped
    if skip_resolve:
        print_log("")
        print_log("Skipping resolve_version_locks (--no-resolve specified)")
        print_log("Run 'repo resolve_version_locks' manually to update master lock file.")
    else:
        print_log("")
        print_log("=== Running resolve_version_locks ===")
        _resolve_version_locks(dry_run=False)

    print_log("")
    print_log("Done!")

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _run_cli(options: argparse.Namespace, config: Dict) -> None:
    """CLI wrapper that calls the Python API."""
    set_config(config)

    # List mode (no --all and no --team)
    if not options.all and not options.team:
        print_log("Available team files:")
        for team_name, ext_count in list_team_files():
            print_log(f"  {team_name} ({ext_count} extensions)")
        print_log("")
        print_log("Usage:")
        print_log("  repo update_version_locks --all              # Update all teams")
        print_log("  repo update_version_locks --team animation   # Update one team")
        return

    update_version_locks(team=options.team, update_all=options.all, skip_resolve=options.no_resolve)


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Optional[Callable]:
    """Entry point for 'repo update_version_locks' tool."""

    parser.description = (
        "Update team TOML files to latest extension versions from registry.\n\n"
        "Options:\n"
        "  --all              Update all team files\n"
        "  --team <name>      Update one team's file\n"
        "  --no-resolve       Skip running resolve_version_locks after updating\n\n"
        "Examples:\n"
        "  repo update_version_locks --all\n"
        "  repo update_version_locks --team animation\n"
        "  repo update_version_locks --all --no-resolve"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all team TOML files with latest versions",
    )
    parser.add_argument(
        "--team",
        type=str,
        help="Update a specific team's TOML file (e.g., 'animation' or 'team_animation')",
    )
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="Skip running resolve_version_locks after updating (escape hatch)",
    )

    return _run_cli
