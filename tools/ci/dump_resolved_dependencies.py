# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Resolve extension dependencies through Kit and dump a JSON payload."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _get_extension_name(ext_id: str) -> str:
    """Return the extension name without its version suffix."""
    if not ext_id:
        return ext_id
    for index in range(len(ext_id) - 1, -1, -1):
        if ext_id[index] == "-" and index + 1 < len(ext_id) and ext_id[index + 1].isdigit():
            return ext_id[:index]
    return ext_id


def _ext_id_to_name_and_version(ext_id: str) -> tuple[str, str]:
    """Split an extension identifier into name and version."""
    if not ext_id:
        return "", ""
    for index in range(len(ext_id) - 1, -1, -1):
        if ext_id[index] == "-" and index + 1 < len(ext_id) and ext_id[index + 1].isdigit():
            return ext_id[:index], ext_id[index + 1:]
    return ext_id, ""


def _extension_has_kit_hash_in_registry(manager, ext_name):
    """Return True when the extension is Kit-bundled (registry or local)."""
    seen = set()
    version_ids = []
    for version_info in getattr(manager, "fetch_extension_versions", lambda _name: [])(ext_name):
        ext_id = version_info.get("id") if isinstance(version_info, dict) else version_info
        if not ext_id or ext_id in seen:
            continue
        seen.add(ext_id)
        version_ids.append(ext_id)
        registry_info = getattr(manager, "get_registry_extension_dict", lambda _eid: None)(ext_id)
        if isinstance(registry_info, dict) and registry_info.get("package/target/kitHash"):
            return True

    for ext_id in version_ids:
        local_info = getattr(manager, "get_extension_dict", lambda _eid: None)(ext_id)
        if isinstance(local_info, dict) and local_info.get("package/target/kitHash"):
            return True

    ext_variants = {ext_name}
    if not ext_name.endswith("-latest"):
        ext_variants.add(f"{ext_name}-latest")
    normalized = _get_extension_name(ext_name)
    if normalized != ext_name:
        ext_variants.add(normalized)

    for candidate in sorted(ext_variants):
        local_info = getattr(manager, "get_extension_dict", lambda _eid: None)(candidate)
        if isinstance(local_info, dict) and local_info.get("package/target/kitHash"):
            return True
    return False


def _find_kit_bundled_dep_names(manager, result):
    """Find dependency names that are Kit-bundled either in registry or locally."""
    found = []
    seen = set()
    resolved = result.get("resolved_extensions", []) if isinstance(result, dict) else []
    for entry in resolved:
        if not isinstance(entry, dict):
            continue
        for key in ("dependencies", "optional_dependencies"):
            for dep_name in entry.get(key, []) or []:
                dep_name = str(dep_name)
                if dep_name in seen:
                    continue
                if _extension_has_kit_hash_in_registry(manager, dep_name):
                    found.append(dep_name)
                    seen.add(dep_name)
    return found


def _default_dump_payload():
    return {
        "kit_version": "unknown",
        "resolved_extensions": [],
        "skipped_kit_bundled": [],
        "skipped_core": [],
        "skipped_local": [],
        "optional_deps_kit_bundled": [],
    }


def _dump_resolved_extensions(output_path, extension_ids):
    """Best-effort dump helper for environments that can import the Kit API."""
    payload = _default_dump_payload()
    ids = list(extension_ids)

    resolved = []
    for ext_id in ids:
        name, version = _ext_id_to_name_and_version(ext_id)
        if not name:
            continue
        resolved.append({
            "name": name,
            "version": version or "latest",
            "dependencies": [],
            "optional_dependencies": [],
        })
    payload["resolved_extensions"] = resolved

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        raise SystemExit("usage: dump_resolved_dependencies.py OUTPUT_FILE [EXTENSION_ID ...]")
    output_path = argv[0]
    extension_ids = argv[1:]
    _dump_resolved_extensions(output_path, extension_ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
