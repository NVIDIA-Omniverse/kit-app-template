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
Generate ETM (Extension Test Manager) list files using solve_extensions.

Workflow:
1. Team files (team_*.toml) define direct extensions teams own
2. This tool uses Kit's solve_extensions to resolve full dependencies
3. Version is aligned with Kit major.minor, patch auto-increments

Usage:
    repo generate_etm_files

ETM Versioning (per ETM infrastructure):
- major.minor must match Kit version (e.g., 110.0 for Kit 110)
- patch version: locally generated as .0, CI publishing increments based on registry
- ETM test process finds latest ETM list matching Kit binary's major.minor
"""

import argparse
from typing import Callable, List, Optional, Tuple

import omni.repo.man
from omni.repo.man import print_log
from version_locks_common import (
    EtmFileConfig,
    collect_extensions_by_section,
    get_config,
    get_etm_output_dir,
    get_team_files,
    get_version_locks_dir,
    run_solve_extensions,
    set_config,
)

# ---------------------------------------------------------------------------
# ETM file generation
# ---------------------------------------------------------------------------


def _generate_etm_file_content(
    etm_cfg: EtmFileConfig,
    direct_extensions: List[str],
    all_resolved: List[Tuple[str, str]],
    version: str,
) -> str:
    """
    Generate an ETM-compatible kit file.

    The ETM file includes ALL resolved extensions (direct + transitive) to ensure
    explicit version control and consistent dependency comparison with the registry.

    Args:
        etm_cfg: ETM file configuration.
        direct_extensions: Direct extension names for this ETM suite (used for comments).
        all_resolved: All resolved extensions (name, version) tuples.
        version: Version string for the ETM file (e.g., "110.0.5").
    """
    direct_set = set(direct_extensions)

    lines = []
    lines.append("[package]")
    lines.append(f'title = "{etm_cfg.title}"')
    lines.append(f'version = "{version}"')
    lines.append(f'description = """{etm_cfg.description}"""')
    lines.append("")

    # Dependencies section - all resolved extensions with exact versions
    lines.append("[dependencies]")
    lines.append("# All resolved extensions (direct + transitive)")

    for ext_name, ext_version in sorted(all_resolved, key=lambda x: x[0]):
        marker = "" if ext_name in direct_set else "  # transitive"
        lines.append(f'"{ext_name}" = {{ version = "{ext_version}" }}{marker}')
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Python API
# ---------------------------------------------------------------------------


def generate_etm_files() -> None:
    """
    Generate ETM list files using solve_extensions.

    Uses Kit's solve_extensions API to:
    - Resolve all dependencies correctly (respecting locked versions)
    - Automatically skip Kit SDK bundled extensions

    ETM versioning:
    - major.minor aligns with Kit version (the ETM "namespace")
    - patch version is set to 0 here; publish_etm_list.py queries registry and increments patch

    Raises:
        omni.repo.man.RepoToolError: If generation fails.
    """
    cfg = get_config()
    locks_dir = get_version_locks_dir()

    # Find all team TOML files
    team_files = get_team_files()
    print_log(f"Found {len(team_files)} team TOML files")

    if not team_files:
        raise omni.repo.man.RepoToolError(f"No team files found in {locks_dir}")

    # Collect extensions by section for each ETM config (with versions)
    print_log("Reading team files...")
    extensions_by_section = collect_extensions_by_section(team_files, cfg.etm_files)

    for etm_cfg in cfg.etm_files:
        ext_count = len(extensions_by_section.get(etm_cfg.section, {}))
        print_log(f"  {etm_cfg.name}: {ext_count} direct extensions")

    # Generate ETM files - resolve dependencies separately for each suite
    generated_dir = get_etm_output_dir()
    generated_dir.mkdir(parents=True, exist_ok=True)

    kit_version = None
    etm_version = None

    for etm_cfg in cfg.etm_files:
        section_exts = extensions_by_section.get(etm_cfg.section, {})
        direct_ext_names = list(section_exts.keys())

        if not section_exts:
            print_log(f"\n  Skipping {etm_cfg.name}: no direct extensions")
            continue

        # Resolve dependencies for THIS suite's extensions only
        print_log(f"\n=== Resolving dependencies for {etm_cfg.name} ===")
        print_log("  Using locked versions from team files")
        suite_kit_version, suite_resolved, _, _, _ = run_solve_extensions(section_exts, use_locked_versions=True)

        # Append extra extensions (e.g. Windows-only extensions not resolvable on Linux)
        if etm_cfg.extra_extensions:
            resolved_names = {name for name, _ in suite_resolved}
            for ext_id in etm_cfg.extra_extensions:
                # Parse "name-version" format; version starts at the first digit segment after '-'
                parts = ext_id.split("-")
                name = parts[0]
                version = "-".join(parts[1:])
                if name not in resolved_names:
                    suite_resolved.append((name, version))
                    print_log(f"  Added extra extension: {name}-{version}")
                else:
                    print_log(f"  Extra extension already resolved: {name} (skipping)")

        # Use Kit version from first resolution (should be same for all)
        if kit_version is None:
            kit_version = suite_kit_version
            version_parts = kit_version.split(".")
            etm_version = f"{version_parts[0]}.{version_parts[1]}.0"

        content = _generate_etm_file_content(
            etm_cfg=etm_cfg,
            direct_extensions=direct_ext_names,
            all_resolved=suite_resolved,
            version=etm_version,
        )

        file_path = generated_dir / f"{etm_cfg.name}.kit"
        file_path.write_text(content)
        print_log(f"  Written: {file_path.name}")
        print_log(f"    - Version: {etm_version}")
        print_log(f"    - {len(suite_resolved)} total extensions ({len(direct_ext_names)} direct)")

    print_log("")
    print_log("Done!")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _run_cli(options: argparse.Namespace, config: dict) -> None:
    """CLI wrapper that calls the Python API."""
    set_config(config)
    generate_etm_files()


def setup_repo_tool(parser: argparse.ArgumentParser, config: dict) -> Optional[Callable]:
    """Entry point for 'repo generate_etm_files' tool."""

    parser.description = (
        "Generate ETM (Extension Test Manager) list files.\n\n"
        "Uses Kit's solve_extensions to resolve all dependencies, which:\n"
        "- Ensures correct dependency resolution\n"
        "- Automatically skips Kit SDK bundled extensions\n\n"
        "ETM versioning: major.minor aligns with Kit, patch is set to 0.\n"
        "Use 'repo ci publish_etm_list' to query registry and increment patch before publishing.\n\n"
        "Output directory is configured in repo.toml [repo_version_locks]."
    )

    return _run_cli
