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
Resolve version locks and generate master lock file.

Workflow:
1. Reads all team_*.toml files to collect direct extensions
2. Uses Kit's solve_extensions API to resolve ALL dependencies
3. Writes master version_locks.kit with all resolved versions

Usage:
    repo resolve_version_locks           # Resolve and update master lock file
    repo resolve_version_locks --dry-run # Show what would be resolved
"""

import argparse
import logging
import re
import shutil
from collections import deque
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

import omni.repo.man
from omni.repo.man import print_log
from version_locks_common import (
    check_etm_suite_exclusivity,
    check_version_conflicts,
    get_config,
    get_kit_version,
    get_master_lock_path,
    get_root_dir,
    get_team_files,
    get_version_locks_dir,
    parse_master_lock_file,
    parse_team_toml,
    run_solve_extensions,
    set_config,
)


def _print_dependency_changes(
    previous: Dict[str, str],
    current: Dict[str, str],
) -> None:
    """
    Print changes in dependencies for debugging race conditions.

    Args:
        previous: Dict of previous {ext_name: version}
        current: Dict of current {ext_name: version}
    """
    prev_names = set(previous.keys())
    curr_names = set(current.keys())

    added = curr_names - prev_names
    removed = prev_names - curr_names
    common = prev_names & curr_names

    updated = {name for name in common if previous[name] != current[name]}

    if not added and not removed and not updated:
        print_log("  No changes in dependencies")
        return

    print_log("> Changes in dependencies:")

    if added:
        print_log(">> Added:")
        for name in sorted(added):
            print_log(f"    {name}: {current[name]}")

    if removed:
        print_log(">> Removed:")
        for name in sorted(removed):
            print_log(f"    {name}: {previous[name]}")

    if updated:
        print_log(">> Updated:")
        for name in sorted(updated):
            print_log(f"    {name}: {previous[name]} -> {current[name]}")


# Kit files that get version locks applied at build time (workspace only, not committed)
PRECACHE_KIT_FILES = [
    "source/apps/omni.app.editor.base.kit",
    "source/apps/omni.app.editor.full.kit",
]


def _has_version_locks_in_file(kit_path: Path) -> bool:
    """Return True if the .kit file contains version locks (must not be committed).

    Detects both:
    - Old format: [settings.app.exts] with enabled = [ ... ]
    - New format: app.exts.enabled = [ ... ] (build-time generated block at end of file)
    """
    content = kit_path.read_text()
    lines = content.split("\n")
    entry_re = re.compile(r'^\s*"[^"]+-[\d.]+[^"]*"\s*,?\s*(#.*)?$')

    in_exts = False
    in_enabled = False
    for line in lines:
        stripped = line.strip()
        if stripped == "[settings.app.exts]":
            in_exts = True
            in_enabled = False
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_exts = False
            in_enabled = False
            continue
        if in_exts and (stripped.startswith("enabled = [") or stripped == "enabled = ["):
            in_enabled = True
            continue
        if in_enabled:
            if "]" in stripped:
                break
            if entry_re.match(line):
                return True

    in_app_exts_enabled = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("app.exts.enabled = [") or stripped == "app.exts.enabled = [":
            in_app_exts_enabled = True
            continue
        if in_app_exts_enabled:
            if "]" in stripped:
                break
            if entry_re.match(line):
                return True
    return False


def check_kit_files_no_version_locks(root: Path) -> List[str]:
    """Return list of PRECACHE_KIT_FILES paths that contain version locks. Empty if all clean."""
    failed = []
    for rel in PRECACHE_KIT_FILES:
        path = root / rel
        if not path.is_file():
            continue
        if _has_version_locks_in_file(path):
            failed.append(rel)
    return failed


def _parse_kit_dependencies(kit_path: Path) -> List[str]:
    """Parse extension names from a kit file's [dependencies] section."""
    content = kit_path.read_text()
    extensions = []
    in_dependencies = False
    for line in content.split("\n"):
        if line.strip().startswith("["):
            in_dependencies = line.strip() == "[dependencies]"
            continue
        if in_dependencies:
            match = re.match(r'^"([^"]+)"\s*=', line)
            if match:
                extensions.append(match.group(1))
    return extensions


def _find_settings_app_exts_ranges(lines: List[str]) -> List[Tuple[int, int]]:
    """Return list of (start, end) line indices for each [settings.app.exts] block (0-based, end inclusive)."""
    ranges: List[Tuple[int, int]] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "[settings.app.exts]":
            start = i
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("[") and s.endswith("]") and s != "[settings.app.exts]":
                    break
                if s == "[settings.app.exts]":
                    break
                i += 1
            ranges.append((start, i - 1))
            continue
        i += 1
    return ranges


# Standard generated-block markers (same pattern as repo_precache / Kit SDK generated .kit files)
VERSION_LOCKS_BLOCK_BEGIN = "# BEGIN GENERATED PART (Remove from 'BEGIN' to 'END' to regenerate)"
VERSION_LOCKS_BLOCK_END = "# END GENERATED PART"
# Exact 100-char separator line used for generated block (no ##########)
_VERSION_LOCKS_SEPARATOR = "########################################################################################################################"
# Legacy markers we still recognize so we replace old blocks with the new format
_LEGACY_BEGIN = "# --- BEGIN version locks (applied at build time, do not commit) ---"
_LEGACY_END = "# --- END version locks ---"


def _find_version_locks_comment_block(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Return (start, end) line indices of the version-locks generated block (0-based, end inclusive), or None.
    Recognizes both standard BEGIN/END GENERATED PART and legacy --- BEGIN/END version locks --- markers.
    Start is extended back to include the leading separator line so the whole block is replaced cleanly."""
    begin_i: Optional[int] = None
    end_i: Optional[int] = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if begin_i is None and (stripped == VERSION_LOCKS_BLOCK_BEGIN or stripped == _LEGACY_BEGIN):
            begin_i = i
        elif begin_i is not None and (stripped == VERSION_LOCKS_BLOCK_END or stripped == _LEGACY_END):
            end_i = i
            break
    if begin_i is None or end_i is None:
        return None
    # Include separator or ########## line(s) immediately before BEGIN so we replace the full visual block
    start = begin_i
    while start > 0 and lines[start - 1].strip() in (_VERSION_LOCKS_SEPARATOR, "##########"):
        start -= 1
    return (start, end_i)


def _apply_version_constraints_to_deps(
    lines: List[str],
    version_map: Dict[str, str],
) -> Tuple[List[str], set, Optional[int]]:
    """Rewrite [dependencies] entries in *lines* to include exact version constraints.

    For each ``"ext_name" = {}`` (or ``= { ... }``) line inside the ``[dependencies]``
    section, if *version_map* contains *ext_name*, the line is replaced with
    ``"ext_name" = { version = "=<ver>" }``.  Inline comments are preserved.

    Returns ``(modified_lines, modified_dep_names, deps_section_end_index)``.
    *deps_section_end_index* is the line index of the first ``[…]`` header after
    ``[dependencies]``, or ``len(lines)`` if ``[dependencies]`` runs to the end of the
    file, or ``None`` if no ``[dependencies]`` section was found.
    """
    out = list(lines)
    in_deps = False
    deps_section_end: Optional[int] = None
    modified: set = set()

    for i, line in enumerate(out):
        stripped = line.strip()
        if stripped == "[dependencies]":
            in_deps = True
            continue
        if in_deps and stripped.startswith("["):
            deps_section_end = i
            in_deps = False
            break
        if in_deps and stripped.startswith('"'):
            parts = stripped.split('"')
            if len(parts) >= 2:
                ext_name = parts[1]
                if ext_name in version_map:
                    comment = ""
                    if "#" in line:
                        comment = " " + line[line.index("#") :]
                    out[i] = f'"{ext_name}" = {{ version = "={version_map[ext_name]}" }}{comment}'
                    modified.add(ext_name)

    if in_deps and deps_section_end is None:
        deps_section_end = len(out)

    return out, modified, deps_section_end


def _build_transitive_dep_lines(
    resolved_extensions: List[Tuple[str, str]],
    already_modified: set,
) -> List[str]:
    """Return ``[dependencies]`` lines for resolved extensions not already present.

    Each line uses the exact-version constraint format so Kit's solver pins
    the correct version during precache."""
    result: List[str] = []
    for name, version in sorted(resolved_extensions, key=lambda x: x[0]):
        if name not in already_modified:
            result.append(f'"{name}" = {{ version = "={version}" }}  # transitive (version lock)')
    return result


def _build_generated_block(
    resolved_extensions: List[Tuple[str, str]],
    direct_deps: List[str],
) -> List[str]:
    """Build the ``app.exts.enabled`` documentation block (BEGIN/END GENERATED PART).

    This block is appended at the end of the .kit file for visibility / debugging.
    It does **not** affect the solver; the actual pinning is done via ``[dependencies]``
    version constraints."""
    direct_set = set(direct_deps)
    enabled_lines = ["app.exts.enabled = ["]
    for ext_name, version in sorted(resolved_extensions, key=lambda x: x[0]):
        marker = "" if ext_name in direct_set else "  # transitive"
        enabled_lines.append(f'\t"{ext_name}-{version}",{marker}')
    enabled_lines.append("]")

    return (
        [
            _VERSION_LOCKS_SEPARATOR,
            VERSION_LOCKS_BLOCK_BEGIN,
            _VERSION_LOCKS_SEPARATOR,
            "# Version lock for all dependencies (temporary, build-time only; do not commit):",
            "",
        ]
        + enabled_lines
        + [
            "",
            VERSION_LOCKS_BLOCK_END,
        ]
    )


def _update_kit_file_with_version_locks(
    kit_path: Path,
    resolved_extensions: List[Tuple[str, str]],
    direct_deps: List[str],
) -> None:
    """Update a .kit file with version locks so precache_exts downloads pinned versions.

    Performs four steps:
    1. Removes any existing generated block (idempotent re-run).
    2. Adds ``version = "=X.Y.Z"`` to existing ``[dependencies]`` entries.
    3. Inserts transitive deps (not already in ``[dependencies]``) into the section.
    4. Appends an ``app.exts.enabled`` block for documentation/reference.

    Steps 2-3 are what actually constrain the Kit solver during
    ``precache_exts --ext-precache-mode``.  Step 4 is informational only."""
    lines = kit_path.read_text().split("\n")
    version_map = dict(resolved_extensions)

    # Step 1 – strip old generated block
    block_range = _find_version_locks_comment_block(lines)
    if block_range is not None:
        start, end = block_range
        lines = lines[:start] + lines[end + 1 :]
        while lines and lines[-1].strip() == "":
            lines.pop()

    # Step 2 – pin existing [dependencies] entries
    lines, modified_deps, deps_end = _apply_version_constraints_to_deps(lines, version_map)

    # Step 3 – insert transitive deps
    transitive = _build_transitive_dep_lines(resolved_extensions, modified_deps)
    if transitive and deps_end is not None:
        insert_at = deps_end
        while insert_at > 0 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        header = ["# Transitive dependencies (version lock, build-time only):"]
        lines = lines[:insert_at] + header + transitive + [""] + lines[insert_at:]

    # Step 4 – append documentation block
    block = _build_generated_block(resolved_extensions, direct_deps)
    while lines and lines[-1].strip() == "":
        lines.pop()
    lines = lines + [""] + block

    kit_path.write_text("\n".join(lines))


def _compute_dep_chain(
    missing_ext: str,
    direct_dep_names: Iterable[str],
    deps_map: Optional[Dict[str, List[str]]],
) -> Optional[List[str]]:
    """Compute dependency chain from a direct dep to missing_ext using reverse deps. Returns [direct_dep, ..., missing_ext] or None."""
    if not deps_map:
        return None
    rev_deps: Dict[str, List[str]] = {}
    for ext, deps in deps_map.items():
        for d in deps:
            rev_deps.setdefault(d, []).append(ext)
    direct_set = set(direct_dep_names)
    if missing_ext in direct_set:
        return [missing_ext]
    queue: deque = deque([missing_ext])
    parent: Dict[str, Optional[str]] = {missing_ext: None}
    while queue:
        cur = queue.popleft()
        for dependant in rev_deps.get(cur, []):
            if dependant not in parent:
                parent[dependant] = cur
                if dependant in direct_set:
                    path = [dependant]
                    while path[-1] != missing_ext:
                        path.append(parent[path[-1]])  # type: ignore[arg-type]
                    return path
                queue.append(dependant)
    return None


def _update_precache_kit_files(
    master_version_map: Dict[str, str],
) -> List[Tuple[str, str, str, Optional[List[str]]]]:
    """Update precache app .kit files with version locks from master (runs Kit solver). Returns list of (kit, ext, ver, dep_chain) missing from lock."""
    root_dir = get_root_dir()
    all_missing: List[Tuple[str, str, str]] = []
    # Write applied-locks artifact so you can SEE what was applied (precache overwrites .kit; this is the record).
    out_dir = root_dir / "_build"
    out_dir.mkdir(parents=True, exist_ok=True)
    applied_locks_path = out_dir / "applied_version_locks.txt"
    with open(applied_locks_path, "w", encoding="utf-8") as f:
        f.write(
            "# Version locks applied to app .kit files at build time.\n"
            "# Precache overwrites the .kit files; this file is the record of what was applied.\n"
            "# See also: repo resolve_version_locks --apply-locks-to-precache-apps\n\n"
        )
    print_log("\n=== Applying version locks to precache app .kit files ===")
    for kit_rel_path in PRECACHE_KIT_FILES:
        kit_path = root_dir / kit_rel_path
        if not kit_path.exists():
            print_log(f"  WARNING: Kit file not found: {kit_rel_path}")
            continue
        print_log(f"  Processing {kit_path.name}...")
        direct_dep_names = _parse_kit_dependencies(kit_path)
        if not direct_dep_names:
            continue
        # Kit file defines the dependency set; version_locks only constrains versions.
        # Use lock version when present, empty string for deps not in lock (solver picks version).
        direct_deps = {n: master_version_map.get(n, "") for n in direct_dep_names}
        unlocked_count = sum(1 for v in direct_deps.values() if not v)
        if unlocked_count:
            print_log(f"    {unlocked_count} dependencies not in master lock (solver will pick version)")
        try:
            _, resolved_raw, deps_map, _, _ = run_solve_extensions(
                direct_deps, log_stats=False, use_locked_versions=True
            )
        except Exception as e:
            print_log(f"Failed to resolve dependencies for {kit_path.name}: {e}", logging.ERROR)
            continue
        resolved_filtered, excluded = _filter_platform_specific_extensions(resolved_raw)
        if excluded:
            print_log(f"    Excluded {len(excluded)} platform-specific extensions")
        resolved_extensions = []
        missing_from_master = []
        for ext_name, resolved_version in resolved_filtered:
            if ext_name in master_version_map:
                resolved_extensions.append((ext_name, master_version_map[ext_name]))
            else:
                missing_from_master.append((ext_name, resolved_version))
                resolved_extensions.append((ext_name, resolved_version))
        if missing_from_master:
            direct_dep_names = list(direct_deps.keys())
            for ext_name, version in missing_from_master:
                chain = _compute_dep_chain(ext_name, direct_dep_names, deps_map)
                all_missing.append((kit_path.name, ext_name, version, chain))
        _update_kit_file_with_version_locks(kit_path, resolved_extensions, list(direct_deps.keys()))
        _write_applied_locks_artifact(root_dir, kit_path.name, resolved_extensions, list(direct_deps.keys()))
        print_log(f"    Updated {kit_path.name}")
    print_log(f"  Applied locks written to _build/applied_version_locks.txt (visible after build)")
    return all_missing


def _write_applied_locks_artifact(
    root_dir: Path,
    kit_name: str,
    resolved_extensions: List[Tuple[str, str]],
    direct_deps: List[str],
) -> None:
    """Write applied version locks to _build/applied_version_locks.txt so they are visible after build.
    Precache overwrites the .kit files; this artifact is the record of what was applied."""
    direct_set = set(direct_deps)
    out_dir = root_dir / "_build"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "applied_version_locks.txt"
    with open(out_file, "a", encoding="utf-8") as f:
        f.write(f"\n## {kit_name}\n\n")
        for ext_name, version in sorted(resolved_extensions, key=lambda x: x[0]):
            kind = " (direct)" if ext_name in direct_set else " (transitive)"
            f.write(f"  {ext_name}-{version}{kind}\n")
        f.write("\n")


def _update_precache_files(all_resolved: List[Tuple[str, str]]) -> None:
    """Update precache app .kit files with version locks. Raises if extensions missing from lock."""
    version_map = {ext_name: version for ext_name, version in all_resolved}
    missing_exts = _update_precache_kit_files(version_map)
    if missing_exts:
        print_log("")
        print_log("ERROR: Some extensions in precache kit files are not in the master lock.")
        for kit_name, ext_name, version, chain in sorted(missing_exts, key=lambda x: (x[0], x[1])):
            if chain and len(chain) > 1:
                chain_str = " -> ".join(chain)
                print_log(f"  {ext_name} (required by {kit_name} via {chain_str}, resolved version: {version})")
            else:
                print_log(f"  {ext_name} (required by {kit_name}, resolved version: {version})")
        print_log("Add them to a team_*.toml file and re-run resolve_version_locks.")
        ext_list = ", ".join(m[1] for m in missing_exts)
        raise omni.repo.man.RepoToolError(f"Missing {len(missing_exts)} extensions from team files: {ext_list}")


def apply_version_locks_to_precache_files() -> None:
    """Apply version_locks.kit to precache app .kit files (build-time only, not committed).
    Runs the Kit solver per app so each .kit gets only its direct deps + transitives (not the full lock file)."""
    master_path = get_master_lock_path()
    if not master_path.exists():
        raise omni.repo.man.RepoToolError(
            f"Master lock file not found: {master_path}. Run 'repo resolve_version_locks' first."
        )
    version_map = dict(parse_master_lock_file(master_path))
    if not version_map:
        raise omni.repo.man.RepoToolError("version_locks.kit has no enabled extensions.")
    missing_exts = _update_precache_kit_files(version_map)
    if missing_exts:
        # Some transitives may not be in version_locks.kit (e.g. bundled); we still pin the rest.
        print_log("")
        print_log(
            f"  Note: {len(missing_exts)} app dependencies are not in version_locks.kit (e.g. bundled); using lock for the rest."
        )


# ---------------------------------------------------------------------------
# Master lock file generation
# ---------------------------------------------------------------------------


def _filter_platform_specific_extensions(
    all_resolved: List[Tuple[str, str]],
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Filter out platform-specific extensions that differ between Windows/Linux.

    Platform-specific shader cache extensions are selected at runtime based on
    the platform, so we exclude them from the lock file to avoid CI conflicts.

    Returns:
        (filtered_extensions, excluded_names)
    """
    # Patterns for platform-specific extensions
    platform_patterns = [
        ".shadercache.d3d12",  # Windows DirectX 12
        ".shadercache.vulkan",  # Linux Vulkan
    ]

    filtered = []
    excluded = []

    for ext_name, version in all_resolved:
        is_platform_specific = any(ext_name.endswith(pattern) for pattern in platform_patterns)
        if is_platform_specific:
            excluded.append(f"{ext_name}-{version}")
        else:
            filtered.append((ext_name, version))

    return filtered, excluded


def _generate_master_lock_content(
    direct_extensions: Dict[str, str],
    all_resolved: List[Tuple[str, str]],
    kit_version: str,
) -> str:
    """Generate the master version_locks.kit file content."""
    direct_set = set(direct_extensions.keys())
    transitive_count = len([e for e, _ in all_resolved if e not in direct_set])
    direct_count = len(direct_extensions)
    total = len(all_resolved)
    print_log(
        f"Version lock stats: direct extensions={direct_count}, "
        f"transitive dependencies={transitive_count}, total locked={total}"
    )

    # Use Kit major.minor.0 for package version
    version_parts = kit_version.split(".")
    package_version = f"{version_parts[0]}.{version_parts[1]}.0"

    lines = [
        "# Master Version Lock File",
        "# =========================",
        "# This file is the SINGLE SOURCE OF TRUTH for all release dependencies.",
        "# It contains ALL resolved extension versions (direct + transitive).",
        "# Any consumer that needs the full dependency set must use this file.",
        "# Kit SDK bundled extensions are automatically excluded.",
        "# ",
        "# DO NOT EDIT MANUALLY - this file is auto-generated.",
        "# ",
        "# To update:",
        "#   1. Edit team_*.toml files with new direct extension versions",
        "#   2. Run: repo resolve_version_locks",
        "#   3. Run: repo generate_etm_files",
        "#",
        "",
        "[package]",
        'title = "Master Version Locks"',
        f'version = "{package_version}"',
        'description = """All resolved extension versions for release stability."""',
        "",
        "[dependencies]",
        "# Direct extensions from team_*.toml files",
    ]

    for ext_name, version in sorted(direct_extensions.items()):
        lines.append(f'"{ext_name}" = {{ version = "={version}" }}')

    lines.append("")
    lines.append("# All resolved versions (direct + transitive)")
    lines.append("[settings.app.exts]")
    lines.append("enabled = [")
    for ext_name, version in sorted(all_resolved, key=lambda x: x[0]):
        marker = "" if ext_name in direct_set else "  # transitive"
        lines.append(f'\t"{ext_name}-{version}",{marker}')
    lines.append("]")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Python API - Step Functions
# ---------------------------------------------------------------------------


def _check_for_conflicts(team_files: List[Path]) -> None:
    """
    Check for version conflicts across team files.

    Args:
        team_files: List of team TOML file paths.

    Raises:
        omni.repo.man.RepoToolError: If conflicts are detected.
    """
    print_log("=== Checking for version conflicts ===")
    conflicts = check_version_conflicts(team_files)
    if conflicts:
        print_log("")
        print_log("ERROR: Version conflicts detected across team files:")
        for conflict in conflicts:
            print_log(conflict)
        print_log("")
        print_log("Please align versions across teams before resolving.")
        raise omni.repo.man.RepoToolError("Version conflicts detected")
    print_log("  No conflicts found.")


def _check_etm_suite_exclusivity(team_files: List[Path]) -> List[str]:
    """
    Ensure each extension is assigned to exactly one ETM suite (section).

    Returns:
        List of error messages (empty if no violations). Does not raise.
    """
    print_log("=== Checking ETM suite exclusivity ===")
    cfg = get_config()
    errors = check_etm_suite_exclusivity(team_files, cfg.etm_files)
    if errors:
        print_log("  Violations found (reported with other errors below)")
    else:
        print_log("  Each extension is in at most one suite.")
    return errors


def _collect_direct_extensions(team_files: List[Path]) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Collect all direct extensions from team TOML files.

    Args:
        team_files: List of team TOML file paths.

    Returns:
        (all_direct, ext_to_team_files) where all_direct maps ext name to version,
        and ext_to_team_files maps ext name to list of team file stems that list it.
    """
    print_log("\n=== Collecting direct extensions from team files ===")
    all_direct: Dict[str, str] = {}
    ext_to_team_files: Dict[str, List[str]] = {}

    for team_file in team_files:
        _, kat_exts, sample_exts = parse_team_toml(team_file)
        team_exts = {**kat_exts, **sample_exts}
        print_log(f"  {team_file.stem}: {len(team_exts)} extensions")
        for ext_name in team_exts:
            ext_to_team_files.setdefault(ext_name, []).append(team_file.stem)
        all_direct.update(team_exts)

    print_log(f"\nTotal direct extensions: {len(all_direct)}")
    return all_direct, ext_to_team_files


def _load_existing_transitive_locks(
    master_path: Path,
    direct_extensions: Dict[str, str],
) -> Dict[str, str]:
    """
    Load existing transitive locks from master lock file.

    Excludes direct extensions since those come from team TOML files
    and may have been updated.

    Args:
        master_path: Path to the master lock file (must exist).
        direct_extensions: Dict of direct extensions to exclude.

    Returns:
        Dict mapping transitive extension name to version.
    """
    all_locks = dict(parse_master_lock_file(master_path))
    transitive_locks = {k: v for k, v in all_locks.items() if k not in direct_extensions}
    print_log(f"\n=== Loaded {len(transitive_locks)} existing transitive locks ===")
    return transitive_locks


def _resolve_dependencies(
    all_direct: Dict[str, str],
    existing_transitive_locks: Dict[str, str],
) -> Tuple[List[Tuple[str, str]], bool, Optional[Dict[str, List[str]]], Optional[Set[str]]]:
    """
    Resolve dependencies using solve_extensions.

    Strategy: Try with existing transitive locks as constraints first (preserves them).
    If that fails (conflicts), fall back to direct deps only (allows transitive updates).

    Args:
        all_direct: Dict of direct extension dependencies.
        existing_transitive_locks: Dict of existing transitive locked versions.

    Returns:
        Tuple of (resolved_extensions, used_fallback, deps_map, skipped_names, optional_deps_map).
        deps_map/skipped_names/optional_deps_map are from the solver run that produced the result (for validation).

    Raises:
        omni.repo.man.RepoToolError: If resolution fails completely.
    """
    print_log("\n=== Resolving dependencies with solve_extensions ===")

    all_resolved_raw: List[Tuple[str, str]] = []
    used_fallback = False
    deps_map: Optional[Dict[str, List[str]]] = None
    skipped_names: Optional[Set[str]] = None
    optional_deps_map: Optional[Dict[str, List[str]]] = None

    if existing_transitive_locks:
        # Merge direct deps with existing transitive locks
        all_constraints = {**existing_transitive_locks, **all_direct}
        print_log(f"  Trying with {len(all_constraints)} constraints (direct + transitive locks)...")

        try:
            _, all_resolved_raw, deps_map, skipped_names, optional_deps_map = run_solve_extensions(
                all_constraints, use_locked_versions=True
            )
            if len(all_resolved_raw) > 0:
                print_log("  Success: existing locks are still valid")
        except Exception as e:
            print_log(f"  Solver failed with existing locks: {e}")
            all_resolved_raw = []
            deps_map = None
            skipped_names = None

        if len(all_resolved_raw) == 0:
            print_log("  Falling back to direct deps only (transitive deps may change)...")
            used_fallback = True
            deps_map = None
            skipped_names = None
            optional_deps_map = None

    if len(all_resolved_raw) == 0:
        # Either no existing locks or conflicts - solve with direct deps only
        print_log(f"  Using {len(all_direct)} direct extension constraints")
        _, all_resolved_raw, deps_map, skipped_names, optional_deps_map = run_solve_extensions(
            all_direct, use_locked_versions=True
        )

    # Filter out platform-specific extensions
    all_resolved, excluded = _filter_platform_specific_extensions(all_resolved_raw)
    if excluded:
        print_log(f"\nExcluding {len(excluded)} platform-specific extensions:")
        for ext in excluded:
            print_log(f"  - {ext}")

    if len(all_resolved) == 0:
        print_log("No resolved extensions found!", logging.ERROR)
        print_log("This might indicate a problem with the registry or extension conflicts.", logging.ERROR)
        print_log("Check the solve_extensions output above for conflict details.", logging.ERROR)
        raise omni.repo.man.RepoToolError("solve_extensions returned no results - cannot write version_locks.kit")

    return all_resolved, used_fallback, deps_map, skipped_names, optional_deps_map


def _check_direct_deps_in_lock(
    all_direct: Dict[str, str],
    all_resolved: List[Tuple[str, str]],
    ext_to_team_files: Dict[str, List[str]],
    deps_map: Optional[Dict[str, List[str]]],
    skipped_names: Optional[Set[str]],
) -> List[str]:
    """
    Check that every direct extension's required dependencies are in the resolved set.

    Ensures we have a version lock for every required transitive (e.g. omni.physx.gpu
    for omni.physx.foundation in team_physx.toml). Kit-bundled deps (in skipped_names) are allowed.
    Optional dependencies (extension.toml "dep" = { optional = true }) are not required in the lock.

    Returns:
        List of error messages (empty if none). Does not raise.
    """
    if not deps_map:
        return []
    resolved_names = set(name for name, _ in all_resolved)
    skipped = skipped_names or set()
    errors: List[str] = []
    for direct_ext in all_direct:
        deps = deps_map.get(direct_ext, [])
        team_files_str = ", ".join(f"{t}.toml" for t in ext_to_team_files.get(direct_ext, []))
        for dep in deps:
            if dep in resolved_names:
                continue
            if dep in skipped:
                continue
            errors.append(f"  {direct_ext} (in {team_files_str}) requires {dep} which is not in the version lock.")
    return sorted(set(errors))


def _warn_missing_optional_deps(
    all_direct: Dict[str, str],
    all_resolved: List[Tuple[str, str]],
    ext_to_team_files: Dict[str, List[str]],
    optional_deps_map: Optional[Dict[str, List[str]]],
    skipped_names: Optional[Set[str]],
) -> None:
    """
    Log clear WARNINGs for each direct extension that has an optional dependency
    not present in the version lock. Optional deps are not required for build;
    warnings inform maintainers so they can add them to a team file if desired.
    """
    if not optional_deps_map:
        return
    resolved_names = set(name for name, _ in all_resolved)
    skipped = skipped_names or set()
    warnings: List[str] = []
    for direct_ext in all_direct:
        optional_deps = optional_deps_map.get(direct_ext, [])
        team_files_str = ", ".join(f"{t}.toml" for t in ext_to_team_files.get(direct_ext, []))
        for dep in optional_deps:
            if dep in resolved_names or dep in skipped:
                continue
            warnings.append(
                f"  {direct_ext} (in {team_files_str}) has optional dependency {dep} which is not in the version lock."
            )
    if not warnings:
        return
    print_log("", logging.WARNING)
    print_log(
        "WARNING: Optional dependencies missing from the version lock (optional; not required for build):",
        logging.WARNING,
    )
    for msg in sorted(set(warnings)):
        print_log(msg, logging.WARNING)
    print_log(
        "  Add to a team_*.toml only if you want these optional extensions locked.",
        logging.WARNING,
    )


def _log_resolution_summary(
    all_direct: Dict[str, str],
    all_resolved: List[Tuple[str, str]],
    existing_transitive_locks: Dict[str, str],
    used_fallback: bool,
) -> None:
    """
    Log resolution summary and dependency changes.

    Args:
        all_direct: Dict of direct extension dependencies.
        all_resolved: List of resolved (name, version) tuples.
        existing_transitive_locks: Dict of previously locked transitive versions for diff.
        used_fallback: Whether fallback resolution was used.
    """
    direct_set = set(all_direct.keys())
    transitive_count = len([e for e, _ in all_resolved if e not in direct_set])
    print_log(f"\nResolution summary:")
    print_log(f"  - Direct: {len(all_direct)}")
    print_log(f"  - Transitive: {transitive_count}")
    print_log(f"  - Total (excluding Kit-bundled): {len(all_resolved)}")

    if used_fallback:
        print_log("")
        print_log(
            "Transitive dependencies were updated due to conflicts with direct deps.",
            logging.WARNING,
        )
        print_log(
            "Review the changes below and commit the updated version_locks.kit.",
            logging.WARNING,
        )

    # Print transitive dependency changes (exclude direct deps from comparison)
    current_transitive = {k: v for k, v in all_resolved if k not in direct_set}
    print_log("")
    _print_dependency_changes(existing_transitive_locks, current_transitive)


def _verify_master_lock_contains_all(
    master_path: Path,
    all_resolved: List[Tuple[str, str]],
) -> None:
    """
    Verify the written master lock contains every resolved extension (direct + transitive).

    Ensures we never miss necessary dependencies for release.

    Raises:
        omni.repo.man.RepoToolError: If any resolved extension is missing from the lock.
    """
    written = dict(parse_master_lock_file(master_path))
    resolved_set = set(all_resolved)
    missing = []
    for ext_name, version in resolved_set:
        if written.get(ext_name) != version:
            missing.append((ext_name, version))
    if missing:
        msg = (
            f"Master lock is missing {len(missing)} resolved extension(s). "
            "This would leave release dependencies incomplete."
        )
        print_log("", logging.ERROR)
        print_log(f"ERROR: {msg}", logging.ERROR)
        for ext_name, version in sorted(missing, key=lambda x: x[0]):
            print_log(f"  {ext_name}-{version}", logging.ERROR)
        raise omni.repo.man.RepoToolError(msg)


def _write_master_lock(
    master_path: Path,
    all_direct: Dict[str, str],
    all_resolved: List[Tuple[str, str]],
    kit_version: str,
) -> None:
    """
    Write the master lock file.

    The lock file is the single source of truth for all release dependencies
    (direct from team_*.toml plus transitive). Any consumer that needs the full
    set of dependencies must use version_locks.kit, not the raw team file lists.

    Args:
        master_path: Path to write the master lock file.
        all_direct: Dict of direct extension dependencies.
        all_resolved: List of resolved (name, version) tuples.
        kit_version: Kit version string.
    """
    print_log("\n=== Writing master lock file ===")
    master_content = _generate_master_lock_content(all_direct, all_resolved, kit_version)
    master_path.write_text(master_content)
    print_log(f"Written: {master_path.name}")
    _verify_master_lock_contains_all(master_path, all_resolved)


# ---------------------------------------------------------------------------
# Python API - Main Function
# ---------------------------------------------------------------------------


def resolve_version_locks(dry_run: bool = False, refresh: bool = False, apply_only: bool = False) -> None:
    """
    Resolve version locks and generate master lock file.

    Uses Kit's solve_extensions API for robust dependency resolution.
    Kit SDK bundled extensions are automatically excluded.

    Args:
        dry_run: If True, only show what would be resolved without running Kit.
        refresh: If True, ignore existing transitive locks and resolve fresh.
        apply_only: If True, only apply existing version_locks.kit to app .kit files (build-time).

    Raises:
        omni.repo.man.RepoToolError: On conflicts or resolution failure.
    """
    if apply_only:
        apply_version_locks_to_precache_files()
        print_log("\n=== Done (apply-only) ===")
        return

    locks_dir = get_version_locks_dir()
    team_files = get_team_files()
    master_path = get_master_lock_path()
    kit_version = get_kit_version()

    if not team_files:
        raise omni.repo.man.RepoToolError(f"No team_*.toml files found in {locks_dir}")

    if not refresh and not master_path.exists():
        raise omni.repo.man.RepoToolError(
            f"Master lock file not found: {master_path}\n" "Run 'repo resolve_version_locks --refresh' to create it."
        )

    _check_for_conflicts(team_files)
    exclusivity_errors = _check_etm_suite_exclusivity(team_files)
    all_direct, ext_to_team_files = _collect_direct_extensions(team_files)

    if dry_run:
        print_log("\n[DRY RUN] Would resolve these extensions:")
        for ext_name, version in sorted(all_direct.items()):
            print_log(f"  {ext_name} = {version}")
        if exclusivity_errors:
            print_log("")
            print_log("ERROR: ETM suite exclusivity violations (fix before resolving):")
            for err in exclusivity_errors:
                print_log(err, logging.ERROR)
            raise omni.repo.man.RepoToolError("Extensions in multiple ETM suites")
        return

    # Load existing transitive locks (unless refresh mode)
    if refresh:
        print_log("\n=== Refresh mode: ignoring existing transitive locks ===")
        existing_transitive_locks: Dict[str, str] = {}
    else:
        existing_transitive_locks = _load_existing_transitive_locks(master_path, all_direct)

    all_resolved, used_fallback, deps_map, skipped_names, optional_deps_map = _resolve_dependencies(
        all_direct, existing_transitive_locks
    )
    missing_dep_errors = _check_direct_deps_in_lock(
        all_direct, all_resolved, ext_to_team_files, deps_map, skipped_names
    )
    _warn_missing_optional_deps(all_direct, all_resolved, ext_to_team_files, optional_deps_map, skipped_names)

    # Report all validation errors together (no early-out)
    if exclusivity_errors or missing_dep_errors:
        print_log("")
        print_log("ERROR: Validation failed. Fix the following and re-run.", logging.ERROR)
        if exclusivity_errors:
            print_log("", logging.ERROR)
            print_log("Extensions must appear in exactly one ETM suite (section):", logging.ERROR)
            for err in exclusivity_errors:
                print_log(err, logging.ERROR)
            print_log("  Edit team_*.toml so each extension is listed in only one section.", logging.ERROR)
        if missing_dep_errors:
            print_log("", logging.ERROR)
            print_log("Required dependencies missing from the version lock:", logging.ERROR)
            for err in missing_dep_errors:
                print_log(err, logging.ERROR)
            print_log(
                "  Ensure the solver returns all transitives or add the missing extension to a team file.",
                logging.ERROR,
            )
        print_log("")
        raise omni.repo.man.RepoToolError(
            "Validation failed: ETM suite exclusivity and/or missing dependencies in lock"
        )

    _log_resolution_summary(all_direct, all_resolved, existing_transitive_locks, used_fallback)
    _write_master_lock(master_path, all_direct, all_resolved, kit_version)

    # _update_precache_files validates that app .kit deps are in the lock, but as a
    # side effect it writes version pins into the .kit files. Back up first, validate,
    # then restore so the workspace is never left dirty.
    root_dir = get_root_dir()
    backup_dir = Path(root_dir) / "_build" / "_kit_file_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backups: Dict[Path, Path] = {}
    for rel in PRECACHE_KIT_FILES:
        kit_path = Path(root_dir) / rel
        if kit_path.exists():
            bak = backup_dir / kit_path.name
            shutil.copy2(kit_path, bak)
            backups[kit_path] = bak
    try:
        _update_precache_files(all_resolved)
    finally:
        for kit_path, bak in backups.items():
            shutil.move(str(bak), str(kit_path))

    print_log("\n=== Done! ===")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _run_cli(options: argparse.Namespace, config: Dict) -> None:
    """CLI wrapper that calls the Python API."""
    set_config(config)
    resolve_version_locks(dry_run=options.dry_run, refresh=options.refresh, apply_only=options.apply_only)


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Optional[Callable]:
    """Entry point for 'repo resolve_version_locks' tool."""

    parser.description = (
        "Resolve version locks and generate master lock file.\n\n"
        "Uses Kit's solve_extensions API to resolve all dependencies correctly.\n"
        "Reads team_*.toml, writes version_locks.kit, and can apply locks to precache app .kit files."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be resolved without running Kit",
    )

    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore existing transitive locks and resolve all dependencies fresh. "
        "Use this to update transitive deps to their latest compatible versions.",
    )

    parser.add_argument(
        "--apply-locks-to-precache-apps",
        dest="apply_only",
        action="store_true",
        help="Apply version_locks.kit to precache app .kit files (base/full editor) so the next "
        "precache bundles exact locked versions. Does not resolve or write version_locks.kit. "
        "Use before build in CI or when packaging with locked versions. "
        "Changes are temporary (workspace-only); do not commit the modified .kit files. "
        "Precache (generate_version_lock=false) overwrites these files and removes the block; "
        "CI build (tools/ci/build.py) restores them from git after package so the repo stays clean.",
    )

    return _run_cli
