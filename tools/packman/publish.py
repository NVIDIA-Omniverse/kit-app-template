# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Helpers for NGC publish metadata generation and validation."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable, Sequence

RELEASE_VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+)-(dev|stage|rc)\.(\d+)$")


def get_package_version_part(file_name: str, platform: str, include_build_metadata: bool = False) -> str:
    """Extract the published package version from a package artifact filename."""
    if "@" not in file_name:
        return file_name
    _, rest = file_name.split("@", 1)
    marker = f".{platform}"
    if marker in rest:
        version_part = rest.split(marker, 1)[0]
    else:
        version_part = rest
    if version_part.endswith(".zip"):
        version_part = version_part[:-4]
    if version_part.endswith(".release"):
        version_part = version_part[:-8]
    if version_part.endswith(".windows"):
        version_part = version_part[:-8]
    if "." in version_part and not include_build_metadata:
        candidate = RELEASE_VERSION_RE.match(version_part)
        if candidate:
            return f"{candidate.group(1)}-{candidate.group(2)}.{candidate.group(3)}"
    return version_part


def _write_key_value_lines(dotenv_path: Path, values: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    dotenv_path.parent.mkdir(parents=True, exist_ok=True)
    dotenv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_release_version(value: str) -> tuple[str, str, str]:
    match = RELEASE_VERSION_RE.match(value)
    if not match:
        return "", "", ""
    base, qualifier, number = match.groups()
    return base, qualifier, number


def write_publish_dotenv(
    dotenv_path,
    *,
    org_name: str,
    team_name: str,
    branch_type: str,
    resource_suffix: str,
    dry_run: bool,
    records: Sequence[dict[str, str]],
) -> None:
    """Write publish metadata for downstream NGC publishing."""
    versions = [str(record["version"]) for record in records]
    version_value = ",".join(versions)
    base_values = { _parse_release_version(v)[0] for v in versions if _parse_release_version(v)[0] }
    qualifiers = { _parse_release_version(v)[1] for v in versions if _parse_release_version(v)[1] }
    numbers = { _parse_release_version(v)[2] for v in versions if _parse_release_version(v)[2] }

    if len(base_values) == 1 and len(qualifiers) == 1 and len(numbers) == 1:
        base, qualifier, number = _parse_release_version(versions[0])
        version_base = base
        version_qualifier = qualifier
        version_number = number
    else:
        version_base = ""
        version_qualifier = ""
        version_number = ""

    resource_names = []
    resource_versions = []
    airgap_versions = []
    for record in records:
        ngc_resource_name = str(record["ngc_resource_name"])
        resource_names.append(ngc_resource_name)
        resource_versions.append(f"{ngc_resource_name}:{record['version']}")
        if "airgap" in str(record["resource_base_name"]).lower():
            airgap_versions.append(f"{ngc_resource_name}:{record['version']}")

    values = {
        "PUBLISH_NGC_VERSION": version_value,
        "PUBLISH_NGC_VERSION_BASE": version_base,
        "PUBLISH_NGC_VERSION_QUALIFIER": version_qualifier,
        "PUBLISH_NGC_VERSION_NUMBER": version_number,
        "PUBLISH_NGC_VERSIONS": version_value,
        "PUBLISH_NGC_ORG": org_name,
        "PUBLISH_NGC_TEAM": team_name,
        "PUBLISH_NGC_RESOURCES": ",".join(resource_names),
        "PUBLISH_NGC_RESOURCE_VERSIONS": ",".join(resource_versions),
        "PUBLISH_NGC_AIRGAP_RESOURCE_VERSIONS": ",".join(airgap_versions),
        "PUBLISH_DRY_RUN": "true" if dry_run else "false",
    }
    _write_key_value_lines(Path(dotenv_path), values)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--org-name", default=os.environ.get("PUBLISH_NGC_ORG", ""))
    parser.add_argument("--team-name", default=os.environ.get("PUBLISH_NGC_TEAM", ""))
    parser.add_argument("--branch-type", default="feature")
    parser.add_argument("--resource-suffix", default="")
    parser.add_argument("--out", default="publish.env")
    args = parser.parse_args(list(argv) if argv is not None else None)

    records = []
    for key in sorted(os.environ):
        if key.startswith("PUBLISH_NGC_RECORD_"):
            try:
                records.append({
                    "version": os.environ[key],
                    "ngc_resource_name": key.rsplit("_", 1)[-1],
                    "resource_base_name": key.rsplit("_", 1)[-1],
                })
            except Exception:
                pass
    write_publish_dotenv(
        args.out,
        org_name=args.org_name,
        team_name=args.team_name,
        branch_type=args.branch_type,
        resource_suffix=args.resource_suffix,
        dry_run=args.dry_run,
        records=records,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
