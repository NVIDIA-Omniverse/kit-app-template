# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

Profile = Literal["airgap", "full"]


@dataclass
class FetchOptions:
    """Options for downloading NGC registry resources."""

    staging_dir: Path
    org_name: str
    team_name: str
    ngc_api_key_envvars: List[str]
    airgap_sdk_resource: str
    airgap_sdk_version: str
    registry_resource: str
    registry_version: str
    api_key: Optional[str] = None
    api_key_from_config: bool = False
    force_update: bool = False
    """When True, delete existing download directories before fetching."""


@dataclass
class FetchedArtifact:
    resource_name: str
    version: str
    download_root: Path
    """Directory passed to download_resource; NGC may add a versioned subfolder."""


@dataclass
class FetchResult:
    artifacts: List[FetchedArtifact] = field(default_factory=list)
    sdk_zip: Optional[Path] = None
    """Resolved path to kit-sdk-airgap zip if found under download roots."""
    registry_dir: Optional[Path] = None
    """Path to extracted kit-extensions-registry tree if discoverable."""
    registry_zip: Optional[Path] = None
    """Path to kit-extensions-registry zip (when not yet extracted)."""


@dataclass
class PrepareOptions:
    kit_sdk_public_root: Path
    staging_dir: Path
    kat_project_name: str = "my-kit-airgap-test"
    airgap_zip: Optional[Path] = None
    """If set, use this zip instead of searching staging_dir."""
    registry_dir: Optional[Path] = None
    """Local registry folder for repo_precache_exts (forward-slash path written to TOML)."""
    extract_subdir: str = "extracted"


@dataclass
class PrepareResult:
    extract_root: Path
    kat_project: Path
    state_path: Path
    registry_url_toml: str


@dataclass
class ClearCacheOptions:
    profile: Profile = "airgap"
    preserve_packman: bool = True
    session_env: Optional[Dict[str, str]] = None
    interactive_confirm: bool = False


@dataclass
class ClearCacheResult:
    cleared_paths: List[Path] = field(default_factory=list)
    skipped_paths: List[Path] = field(default_factory=list)
    effective_env: Dict[str, str] = field(default_factory=dict)


@dataclass
class RunTestsOptions:
    kit_sdk_public_root: Path
    kat_project: Optional[Path] = None
    """If None, load from state file under staging_dir."""
    staging_dir: Optional[Path] = None
    block_network: bool = False
    """When True, block outbound network via OS firewall for the duration of the test run."""


@dataclass
class AirgapState:
    """Persisted under staging_dir / state.json."""

    kat_project: str
    airgap_extract_root: str
    registry_path: Optional[str] = None
    kit_sdk_public_root: Optional[str] = None

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "kat_project": self.kat_project,
            "airgap_extract_root": self.airgap_extract_root,
            "registry_path": self.registry_path,
            "kit_sdk_public_root": self.kit_sdk_public_root,
        }

    @staticmethod
    def from_json_dict(d: Dict[str, Any]) -> "AirgapState":
        return AirgapState(
            kat_project=d["kat_project"],
            airgap_extract_root=d["airgap_extract_root"],
            registry_path=d.get("registry_path"),
            kit_sdk_public_root=d.get("kit_sdk_public_root"),
        )
