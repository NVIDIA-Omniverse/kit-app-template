# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Validate that locked pip-bundling extensions contain compatible versions."""

import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import omni.repo.man
import toml
from version_locks_common import get_config, get_kit_path, get_root_dir

KIT_PIP_ARCHIVE = "omni.kit.pip_archive"


def normalize_package_name(name: str) -> str:
    """Normalize a Python distribution name using PEP 503 rules."""
    return re.sub(r"[-_.]+", "-", name).lower()


def get_exact_extension_ids(lock_path: Path) -> List[str]:
    """Return the complete direct and transitive extension lock set."""
    lock_data = toml.load(str(lock_path))
    extension_ids = lock_data.get("settings", {}).get("app", {}).get("exts", {}).get("enabled", [])
    if not isinstance(extension_ids, list) or not all(isinstance(extension_id, str) for extension_id in extension_ids):
        raise omni.repo.man.RepoToolError(f"Invalid [settings.app.exts].enabled lock set in {lock_path}")
    return extension_ids


def find_version_mismatches(archives: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, List[str]]]:
    """Find shared Python distributions whose versions differ across bundles."""
    package_versions = defaultdict(lambda: defaultdict(list))
    for archive_name, distributions in archives.items():
        for package_name, value in distributions.items():
            versions = value if isinstance(value, list) else [value]
            for version in versions:
                package_versions[normalize_package_name(package_name)][str(version)].append(archive_name)

    return {package_name: dict(versions) for package_name, versions in package_versions.items() if len(versions) > 1}


def format_mismatches(mismatches: Dict[str, Dict[str, List[str]]]) -> str:
    lines = []
    for package_name, versions in sorted(mismatches.items()):
        lines.append(f"  {package_name}:")
        for version, archive_names in sorted(versions.items()):
            lines.append(f"    {version}: {', '.join(sorted(archive_names))}")
    return "\n".join(lines)


def validate_pip_archive_versions(lock_path: Path) -> Dict[str, Dict[str, List[str]]]:
    """Resolve and compare every locked extension that bundles pip distributions."""
    locked_extension_ids = get_exact_extension_ids(lock_path)
    if not locked_extension_ids:
        raise omni.repo.man.RepoToolError(f"No exact extension versions found in {lock_path}")

    extension_ids = [KIT_PIP_ARCHIVE]
    extension_ids.extend(sorted(locked_extension_ids))

    root = get_root_dir()
    script_path = root / "tools" / "ci" / "inspect_pip_archive_versions.py"
    with tempfile.TemporaryDirectory(prefix="kit_pip_archive_validation_") as request_dir_name:
        request_dir = Path(request_dir_name)
        request_path = request_dir / "request.json"
        output_path = request_dir / "result.json"
        request_path.write_text(json.dumps({"extension_ids": extension_ids, "output_path": str(output_path)}))

        registry_args = []
        for index, registry in enumerate(get_config().dev_registries):
            prefix = f"--/exts/omni.kit.registry.nucleus/registries/{index}"
            registry_args.extend(f"{prefix}/{key}={value}" for key, value in registry.items())

        kit_path = get_kit_path()
        command = [
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
            f"{script_path} {request_path}",
        ]
        try:
            omni.repo.man.run_process(command, exit_on_error=True)
        except Exception as error:
            raise omni.repo.man.RepoToolError(f"Pip archive version validation failed: {error}") from error

        if not output_path.exists():
            raise omni.repo.man.RepoToolError(f"Pip archive inspector did not create {output_path}")
        archives = json.loads(output_path.read_text())
    mismatches = find_version_mismatches(archives)
    if not mismatches:
        omni.repo.man.print_log(f"  All shared Python distributions match across {len(archives)} pip bundles")
    return mismatches
