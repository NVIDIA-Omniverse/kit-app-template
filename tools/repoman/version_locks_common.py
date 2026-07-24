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
Shared utilities for version lock management tools.

Configuration is read from repo.toml [repo_version_locks] section.
"""

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python

import omni.repo.man
import packmanapi
from omni.repo.man import print_log

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class EtmFileConfig:
    """Configuration for an ETM file to generate."""

    name: str
    title: str
    description: str
    section: str  # "extensions" or "extensions.sample_p1"
    extra_extensions: list[str] = field(default_factory=list)  # e.g. ["omni.foo-1.2.3"]


@dataclass
class VersionLocksConfig:
    """Configuration for version lock management."""

    version_locks_dir: str = "${root}/source/version-locks"
    master_lock_file: str = "version_locks.kit"
    team_file_pattern: str = "team_*.toml"
    etm_output_dir: str = "${root}/_build/generated/etm"
    kit_path: str = "${root}/_build/target-deps/kit/release/kit${exe_ext}"
    etm_files: List[EtmFileConfig] = field(default_factory=list)
    dev_registries: List[Dict] = field(default_factory=list)

    @classmethod
    def from_repo_config(cls, config: Optional[Dict] = None) -> "VersionLocksConfig":
        """
        Create config from repo.toml config dict.

        Args:
            config: The repo.toml config dict (or None for defaults).

        Returns:
            VersionLocksConfig with values from config or defaults.
        """
        if config is None:
            config = {}

        vl_config = config.get("repo_version_locks", {})

        # Parse ETM file configs
        etm_files = []
        for etm in vl_config.get("etm_files", []):
            etm_files.append(
                EtmFileConfig(
                    name=etm.get("name", ""),
                    title=etm.get("title", ""),
                    description=etm.get("description", ""),
                    section=etm.get("section", "extensions"),
                    extra_extensions=etm.get("extra_extensions", []),
                )
            )

        # Use defaults if no ETM files configured
        if not etm_files:
            etm_files = [
                EtmFileConfig(
                    name="omni.etm.list.kit_app_template",
                    title="ETM test list for Kit App Template",
                    description="Auto-generated from team_*.toml files for ETM kit-app-template test suite",
                    section="extensions.default",
                ),
                EtmFileConfig(
                    name="omni.etm.list.sample_p1",
                    title="ETM test list for Sample P1",
                    description="Auto-generated from team_*.toml files for ETM sample-p1 test suite",
                    section="extensions.sample_p1",
                ),
            ]

        dev_registries = config.get("registry_mapping", {}).get("dev", {}).get("registries", [])

        return cls(
            version_locks_dir=vl_config.get("version_locks_dir", "${root}/source/version-locks"),
            master_lock_file=vl_config.get("master_lock_file", "version_locks.kit"),
            team_file_pattern=vl_config.get("team_file_pattern", "team_*.toml"),
            etm_output_dir=vl_config.get("etm_output_dir", "${root}/_build/generated/etm"),
            kit_path=vl_config.get("kit_path", "${root}/_build/target-deps/kit/release/kit${exe_ext}"),
            etm_files=etm_files,
            dev_registries=dev_registries,
        )


# Module-level config cache
_config: Optional[VersionLocksConfig] = None


def get_config(config: Optional[Dict] = None) -> VersionLocksConfig:
    """
    Get version locks configuration.

    Args:
        config: Optional repo.toml config dict. If provided, creates new config.
                If None, returns cached config or creates default.
    """
    global _config
    if config is not None:
        _config = VersionLocksConfig.from_repo_config(config)
    elif _config is None:
        _config = VersionLocksConfig.from_repo_config({})
    return _config


def set_config(config: Dict) -> None:
    """Set the config from repo.toml dict. Called by tools at startup."""
    global _config
    _config = VersionLocksConfig.from_repo_config(config)


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------


def get_root_dir() -> Path:
    """Get the repository root directory."""
    return Path(omni.repo.man.resolve_tokens("${root}"))


def get_version_locks_dir(config: Optional[Dict] = None) -> Path:
    """Get the version-locks directory."""
    cfg = get_config(config)
    # Only resolve tokens if they exist (config from repo tools is already resolved)
    path_str = cfg.version_locks_dir
    if "${" in path_str:
        path_str = omni.repo.man.resolve_tokens(path_str)
    return Path(path_str)


def get_team_files(config: Optional[Dict] = None) -> List[Path]:
    """Get all team TOML files sorted by name."""
    cfg = get_config(config)
    return sorted(get_version_locks_dir().glob(cfg.team_file_pattern))


def get_master_lock_path(config: Optional[Dict] = None) -> Path:
    """Get the path to the master version_locks.kit file."""
    cfg = get_config(config)
    return get_version_locks_dir() / cfg.master_lock_file


def get_etm_output_dir(config: Optional[Dict] = None) -> Path:
    """Get the ETM output directory."""
    cfg = get_config(config)
    # Only resolve tokens if they exist (config from repo tools is already resolved)
    path_str = cfg.etm_output_dir
    if "${" in path_str:
        path_str = omni.repo.man.resolve_tokens(path_str)
    return Path(path_str)


def get_kit_path(config: Optional[Dict] = None) -> str:
    """Get the path to the Kit executable."""
    cfg = get_config(config)
    path_str = cfg.kit_path
    if "${" in path_str:
        path_str = omni.repo.man.resolve_tokens(path_str)
    return path_str


def get_kit_version() -> str:
    """
    Get the Kit version from the kit-kernel packman dependency.

    Parses tools/deps/kit-sdk.packman.xml to extract the kit-kernel version,
    stripping any build metadata (e.g., "110.2.0+master.277277..." -> "110.2.0").

    Returns:
        Kit version string (e.g., "110.2.0").

    Raises:
        RuntimeError: If kit-kernel version cannot be parsed from the packman XML.
    """
    root = omni.repo.man.resolve_tokens("${root}")
    packman_xml = Path(root) / "tools" / "deps" / "kit-sdk.packman.xml"
    content = packman_xml.read_text()
    match = re.search(r'package name="kit-kernel" version="([^"]+)"', content)
    if not match:
        raise RuntimeError(f"Could not find kit-kernel version in {packman_xml}")
    return match.group(1).split("+")[0]


# ---------------------------------------------------------------------------
# Team TOML parsing
# ---------------------------------------------------------------------------


def parse_team_toml(file_path: Path) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    Parse a team_*.toml file.

    Returns:
        (team_info, kat_extensions, sample_extensions)
        Where extensions are dicts of {extension_name: version}.
    """
    content = file_path.read_text()
    data = tomllib.loads(content)

    team_info = data.get("team", {})

    # kit-app-template extensions (in [extensions.default] section)
    kat_extensions = {}
    extensions = data.get("extensions", {})
    default_section = extensions.get("default", {})

    for key, value in default_section.items():
        if not isinstance(value, dict):  # Skip nested tables
            kat_extensions[key] = str(value)

    # sample-p1 extensions (in [extensions.sample_p1] section)
    sample_extensions = {}
    sample_p1 = extensions.get("sample_p1", {})
    for key, value in sample_p1.items():
        if not isinstance(value, dict):  # Skip nested tables
            sample_extensions[key] = str(value)

    return team_info, kat_extensions, sample_extensions


def parse_team_toml_section(file_path: Path, section: str) -> Dict[str, str]:
    """
    Parse a specific section from a team_*.toml file.

    Args:
        file_path: Path to the team TOML file.
        section: Section path like "extensions" or "extensions.sample_p1".

    Returns:
        Dict of {extension_name: version} for that section.
    """
    content = file_path.read_text()
    data = tomllib.loads(content)

    # Navigate to the section
    parts = section.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, {})
        else:
            return {}

    # Extract extensions (skip nested tables)
    result = {}
    if isinstance(current, dict):
        for key, value in current.items():
            if not isinstance(value, dict):
                result[key] = str(value)

    return result


def collect_all_extensions(team_files: List[Path]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Collect all extensions from team files.

    Returns:
        (kat_extensions, sample_extensions) - both are {ext_name: version} dicts
    """
    kat_extensions: Dict[str, str] = {}
    sample_extensions: Dict[str, str] = {}

    for team_file in team_files:
        _, kat_exts, sample_exts = parse_team_toml(team_file)
        kat_extensions.update(kat_exts)
        sample_extensions.update(sample_exts)

    return kat_extensions, sample_extensions


def collect_extensions_by_section(
    team_files: List[Path],
    etm_configs: List[EtmFileConfig],
) -> Dict[str, Dict[str, str]]:
    """
    Collect extensions grouped by ETM section.

    Args:
        team_files: List of team TOML file paths.
        etm_configs: List of ETM file configurations.

    Returns:
        Dict mapping section name to {ext_name: version} dict.
    """
    result: Dict[str, Dict[str, str]] = {}

    for etm_cfg in etm_configs:
        section_exts: Dict[str, str] = {}
        for team_file in team_files:
            exts = parse_team_toml_section(team_file, etm_cfg.section)
            section_exts.update(exts)
        result[etm_cfg.section] = section_exts

    return result


# ---------------------------------------------------------------------------
# Validation utilities
# ---------------------------------------------------------------------------


def check_version_conflicts(team_files: List[Path]) -> List[str]:
    """
    Check for version conflicts across team files.

    Args:
        team_files: List of team TOML file paths.

    Returns:
        List of conflict messages (empty if no conflicts).
    """
    from collections import defaultdict

    all_versions: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    for team_file in team_files:
        _, kat_exts, sample_exts = parse_team_toml(team_file)
        all_exts = {**kat_exts, **sample_exts}
        for ext_name, version in all_exts.items():
            if version != "0.0.0":  # Skip placeholders
                all_versions[ext_name].append((team_file.stem, version))

    conflicts = []
    for ext_name, versions in all_versions.items():
        unique_versions = set(v for _, v in versions)
        if len(unique_versions) > 1:
            details = ", ".join(f"{team}={ver}" for team, ver in versions)
            conflicts.append(f"  {ext_name}: {details}")

    return conflicts


def check_etm_suite_exclusivity(
    team_files: List[Path],
    etm_configs: List[EtmFileConfig],
) -> List[str]:
    """
    Ensure each extension appears in at most one ETM suite (section).

    Args:
        team_files: List of team TOML file paths.
        etm_configs: List of ETM file configs (each has a section, e.g. extensions.default).

    Returns:
        List of error messages (empty if each extension is in at most one section).
    """
    from collections import defaultdict

    # ext_name -> [(section, team_file_stem), ...]
    ext_to_sections: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    for etm_cfg in etm_configs:
        for team_file in team_files:
            exts = parse_team_toml_section(team_file, etm_cfg.section)
            for ext_name in exts:
                ext_to_sections[ext_name].append((etm_cfg.section, team_file.stem))

    errors = []
    for ext_name, locations in sorted(ext_to_sections.items()):
        # Dedupe by section (same ext in same section from two team files is still one suite)
        sections = list(dict.fromkeys(s for s, _ in locations))
        if len(sections) > 1:
            sections_str = ", ".join(sections)
            team_files_str = ", ".join(sorted(set(f"{t}.toml" for _, t in locations)))
            errors.append(
                f"  {ext_name} appears in multiple ETM suites in {team_files_str}: {sections_str}. Assign it to exactly one."
            )

    return errors


# ---------------------------------------------------------------------------
# Master lock file parsing
# ---------------------------------------------------------------------------


def parse_master_lock_file(file_path: Path) -> List[Tuple[str, str]]:
    """
    Parse the master version_locks.kit file.

    Returns:
        List of (extension_name, version) tuples from the enabled list.
    """
    content = file_path.read_text()
    extensions = []

    # Find enabled = [...] section
    in_enabled = False
    for line in content.split("\n"):
        if "enabled = [" in line:
            in_enabled = True
            continue
        if in_enabled and line.strip() == "]":
            break

        if in_enabled:
            # Match lines like: "omni.foo-1.2.3",
            match = re.match(r'\s*"([^"]+)-(\d+\.\d+\.\d+[^"]*)"', line)
            if match:
                ext_name = match.group(1)
                version = match.group(2)
                extensions.append((ext_name, version))

    return extensions


# ---------------------------------------------------------------------------
# Kit log parsing
# ---------------------------------------------------------------------------


def parse_extensions_from_kit_log(log_path: Path) -> Dict[str, str]:
    """
    Parse Kit log to extract registered extension versions.

    Returns:
        Dict of {extension_name: version}.
    """
    if not log_path.exists():
        return {}

    content = log_path.read_text(encoding="utf-8", errors="ignore")
    versions = {}

    # Match: [ext: extension.name-1.2.3+build.suffix] registered
    pattern = r"\[ext: ([^-\]]+)-(\d+\.\d+\.\d+[^\]]*)\] registered"

    for match in re.finditer(pattern, content):
        ext_name = match.group(1)
        version = match.group(2)
        # Strip build suffixes like +107.3.wx64.r.cp312
        if "+" in version:
            version = version.split("+")[0]
        versions[ext_name] = version

    return versions


# ---------------------------------------------------------------------------
# solve_extensions resolution
# ---------------------------------------------------------------------------


def _ensure_kit_executable(kit_path: str) -> None:
    """Ensure Kit executable exists, auto-fetching if necessary.

    Args:
        kit_path: Path to the Kit executable.

    Raises:
        omni.repo.man.RepoToolError: If Kit cannot be found or fetched.
    """
    if Path(kit_path).exists():
        return

    print_log(f"Kit executable not found: {kit_path}")
    print_log("Auto-fetching Kit SDK...")

    # Get tokens with platform and config
    tokens = omni.repo.man.get_tokens()
    tokens["config"] = "release"

    # Pull kit-sdk.packman.xml
    root = omni.repo.man.resolve_tokens("${root}")
    packman_xml = Path(root) / "tools" / "deps" / "kit-sdk.packman.xml"
    try:
        packmanapi.pull(str(packman_xml), tokens=tokens)
    except packmanapi.PackmanErrorFileExists:
        # Link target already exists as a real directory; remove the stale link and retry
        kit_release_dir = Path(kit_path).parent
        print_log(f"Removing existing non-link directory at {kit_release_dir} to recreate packman link...")
        packmanapi.unlink(str(kit_release_dir))
        packmanapi.pull(str(packman_xml), tokens=tokens)

    # Verify it was fetched successfully
    if not Path(kit_path).exists():
        raise omni.repo.man.RepoToolError(
            f"Kit executable still not found after fetch: {kit_path}\n"
            "Try running 'repo build --fetch-only' manually."
        )


def _ext_name_from_id(ext_id: str) -> str:
    """Extract extension name from id like 'omni.foo-1.2.3' or 'omni.foo-bar-0.0.0'."""
    m = re.match(r"^(.+)-(\d+\.\d+\.\d+)", ext_id)
    return m.group(1) if m else ext_id


def run_solve_extensions(
    extensions: Dict[str, str],
    log_stats: bool = True,
    use_locked_versions: bool = True,
) -> Tuple[
    str, List[Tuple[str, str]], Optional[Dict[str, List[str]]], Optional[Set[str]], Optional[Dict[str, List[str]]]
]:
    """
    Run Kit with solve_extensions to resolve all dependencies.

    Uses the dump_resolved_dependencies.py script to call Kit's solve_extensions API,
    which automatically filters out Kit SDK bundled extensions.
    Always requests dependency data (DUMP_RESOLVED_INCLUDE_DEPS=1) so callers can
    validate that all required transitives are in the lock.

    Args:
        extensions: Dict mapping extension name to locked version.
        log_stats: If True, log statistics about resolved extensions.
        use_locked_versions: If True, pass name-version to solver to respect locks.
                            If False, pass just names to get latest versions.

    Returns:
        (kit_version, resolved_extensions, deps_map, skipped_names, optional_deps_map).
        deps_map: ext_name -> list of required dependency names (empty dict if not in output).
        skipped_names: set of extension names that were skipped as kit-bundled (for validation).
        optional_deps_map: ext_name -> list of optional dependency names (None if no dep data).

    Raises:
        omni.repo.man.RepoToolError: If resolution fails.
    """
    kit_path = get_kit_path()
    root_dir = get_root_dir()

    _ensure_kit_executable(kit_path)

    # Build CLI overrides for dev registries from repo.toml so the solver
    # resolves against the internal registry (which has all extensions).
    # The kernel ships with only prod registries by default.
    registry_args: List[str] = []
    dev_registries = get_config().dev_registries
    if dev_registries:
        for i, reg in enumerate(dev_registries):
            prefix = f"--/exts/omni.kit.registry.nucleus/registries/{i}"
            for key, value in reg.items():
                registry_args.append(f"{prefix}/{key}={value}")
        registry_names = [r.get("name", "?") for r in dev_registries]
        print_log(f"  Using dev registries for resolve: {', '.join(registry_names)}")
    else:
        print_log("  No [registry_mapping.dev] in repo.toml; using kernel default registries")

    # Create temp file for output
    temp_dir = Path(tempfile.gettempdir()) / "kit_solve_extensions"
    temp_dir.mkdir(exist_ok=True)
    output_file = temp_dir / "resolved_deps.json"

    # Build the command to run inside Kit
    script_path = root_dir / "tools" / "ci" / "dump_resolved_dependencies.py"

    if not script_path.exists():
        raise omni.repo.man.RepoToolError(f"Script not found: {script_path}")

    # Format extension identifiers - with or without versions
    if use_locked_versions:
        # Pass name-version where we have a lock; name-only for unlocked deps (solver picks version)
        ext_ids = [f"{name}-{version}" if version else name for name, version in extensions.items()]
    else:
        # Pass just names to resolve to latest versions
        ext_ids = list(extensions.keys())

    # Run Kit with the dump script (always request deps so we can validate transitives are in lock)
    args = [
        kit_path,
        "--no-window",
        "--enable",
        "omni.kit.loop",
        "--enable",
        "omni.kit.registry.nucleus",
        "--/app/extensions/registryEnabled=1",
        "--/app/hangDetector/enabled=false",
        *registry_args,
        "--exec",
        f"{script_path} {output_file} {' '.join(ext_ids)}",
    ]
    orig_deps_env = os.environ.get("DUMP_RESOLVED_INCLUDE_DEPS")
    os.environ["DUMP_RESOLVED_INCLUDE_DEPS"] = "1"
    try:
        omni.repo.man.run_process(args, exit_on_error=True)
    except Exception as e:
        raise omni.repo.man.RepoToolError(f"Kit solve_extensions failed: {e}")
    finally:
        if orig_deps_env is None:
            os.environ.pop("DUMP_RESOLVED_INCLUDE_DEPS", None)
        else:
            os.environ["DUMP_RESOLVED_INCLUDE_DEPS"] = orig_deps_env

    # Read the output
    if not output_file.exists():
        raise omni.repo.man.RepoToolError(f"Output file not created: {output_file}")

    with open(output_file, "r") as f:
        data = json.load(f)

    kit_version = data.get("kit_version")
    if not kit_version:
        raise omni.repo.man.RepoToolError(
            "Kit solve_extensions output is missing 'kit_version'. "
            "The dump_resolved_dependencies.py script may have failed."
        )
    resolved_exts = data.get("resolved_extensions", [])
    resolved = [(ext["name"], ext["version"]) for ext in resolved_exts]

    # Build deps map, optional_deps map, and skipped set for validation (we always request DEPS via env)
    deps_map: Dict[str, List[str]] = {}
    optional_deps_map: Optional[Dict[str, List[str]]] = None
    if resolved_exts and "dependencies" in resolved_exts[0]:
        deps_map = {ext["name"]: ext.get("dependencies", []) for ext in resolved_exts}
        optional_deps_map = {
            ext["name"]: ext.get("optional_dependencies", [])
            for ext in resolved_exts
            if ext.get("optional_dependencies")
        }
        if not optional_deps_map:
            optional_deps_map = None
        build_dir = Path(root_dir) / "_build"
        build_dir.mkdir(exist_ok=True)
        deps_path = build_dir / "resolved_dependencies_with_deps.json"
        with open(deps_path, "w") as f:
            json.dump(data, f, indent=2)
        print_log(f"  Wrote dependency data to {deps_path} (grep for an ext name to see who pulls it in)")
    # All "skipped" categories are Kit-provided (bundled/core/local); deps in these sets are allowed to be absent from the lock.
    # optional_deps_kit_bundled: optional dep names the dump script looked up and found to have kitHash (programmatic, no hard-coded list).
    skipped_names = set(_ext_name_from_id(ext_id) for ext_id in data.get("skipped_kit_bundled", []))
    skipped_names.update(_ext_name_from_id(ext_id) for ext_id in data.get("skipped_core", []))
    skipped_names.update(_ext_name_from_id(ext_id) for ext_id in data.get("skipped_local", []))
    skipped_names.update(data.get("optional_deps_kit_bundled", []))

    # Log statistics
    if log_stats:
        print_log(f"  Kit version: {kit_version}")
        print_log(f"  Resolved: {len(resolved)} extensions")
        print_log(f"  Skipped Kit-bundled: {len(data.get('skipped_kit_bundled', []))}")
        print_log(f"  Optional deps Kit-bundled (no warn): {len(data.get('optional_deps_kit_bundled', []))}")
        print_log(f"  Skipped local: {len(data.get('skipped_local', []))}")
        print_log(f"  Skipped core: {len(data.get('skipped_core', []))}")

        if data.get("errors"):
            for err in data["errors"]:
                print_log(f"  WARNING: {err}")

    # Cleanup
    output_file.unlink()

    return kit_version, resolved, deps_map if deps_map else None, skipped_names, optional_deps_map
