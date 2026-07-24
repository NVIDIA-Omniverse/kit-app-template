# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

"""Python API for airgap local test workflow."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import omni.repo.man
from omni.repo.man import resolve_tokens
from omni.repo.man.utils import extract_archive_to_folder


def _robust_rmtree(path: Path) -> None:
    """Remove a directory tree, handling read-only files on Windows.

    Raises a clear error listing locked files so the user knows what
    process to close.
    """
    locked: list[str] = []

    def _on_error(func, fpath, exc_info):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except PermissionError:
            locked.append(fpath)

    shutil.rmtree(path, onerror=_on_error)
    if locked:
        files = "\n  ".join(locked[:10])
        extra = f"\n  ... and {len(locked) - 10} more" if len(locked) > 10 else ""
        raise PermissionError(
            f"Cannot remove {len(locked)} file(s) in {path} (locked by another process?):\n"
            f"  {files}{extra}\n"
            f"Close any applications using these files and try again."
        )


from .cache_clear import clear_caches_impl
from .inject import find_base_project_under_extract, find_new_project_script, inject_airgap_test_into_base_project
from .types import (
    AirgapState,
    ClearCacheOptions,
    ClearCacheResult,
    FetchedArtifact,
    FetchOptions,
    FetchResult,
    PrepareOptions,
    PrepareResult,
    RunTestsOptions,
)

try:
    from omni.repo.ngc import configure_client, download_resource
except ImportError as e:  # pragma: no cover
    configure_client = None  # type: ignore[assignment]
    download_resource = None  # type: ignore[assignment]
    _NGC_IMPORT_ERROR = e
else:
    _NGC_IMPORT_ERROR = None

STATE_FILENAME = "state.json"
AIRGAP_ZIP_GLOB = "kit-sdk-airgap*.zip"
ENV_KIT_AIRGAP_TEST_PROJECT = "KIT_AIRGAP_TEST_PROJECT"

_VERSION_PRERELEASE_RE = None  # lazy-compiled


def get_base_version() -> str:
    """Read VERSION.md and strip any pre-release suffix (e.g. '110.1.0-rc.1' -> '110.1.0').

    This is used as the default NGC resource version when no explicit override is given.
    """
    import re

    global _VERSION_PRERELEASE_RE
    if _VERSION_PRERELEASE_RE is None:
        _VERSION_PRERELEASE_RE = re.compile(r"^(\d+\.\d+\.\d+)")

    version_file = Path(resolve_tokens("${root}/VERSION.md"))
    raw = version_file.read_text(encoding="utf-8").strip()
    m = _VERSION_PRERELEASE_RE.match(raw)
    if m:
        return m.group(1)
    return raw


def _ensure_ngc() -> None:
    if _NGC_IMPORT_ERROR is not None:
        raise RuntimeError(
            "omni.repo.ngc is required for fetch. Ensure repo_ngc is installed (pull repo deps)."
        ) from _NGC_IMPORT_ERROR


def _find_kit_airgap_zip(search_roots: List[Path]) -> Optional[Path]:
    candidates: List[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        candidates.extend(sorted(root.rglob(AIRGAP_ZIP_GLOB)))
    if not candidates:
        return None
    return candidates[-1]


REGISTRY_ZIP_GLOB = "kit-extensions-registry*.zip"


def _find_registry_zip(search_roots: List[Path]) -> Optional[Path]:
    """Find kit-extensions-registry zip under download roots."""
    for root in search_roots:
        if not root.exists():
            continue
        for p in sorted(root.rglob(REGISTRY_ZIP_GLOB)):
            if p.is_file():
                return p
    return None


def _find_registry_content_dir(search_roots: List[Path]) -> Optional[Path]:
    """Find an extracted registry directory that contains actual registry content.

    A valid registry has a ``v2/`` subdirectory (produced by the Kit extension
    registry build).  Directories that merely *contain* the NGC download zip
    are not valid and should fall through to the zip-extraction path.
    """
    for root in search_roots:
        if not root.exists():
            continue
        for p in root.rglob("v2"):
            if p.is_dir() and (p / "registry.gz").is_file():
                return p.parent
    return None


def fetch_assets(options: FetchOptions) -> FetchResult:
    """Download kit-sdk-airgap and kit-extensions-registry from NGC."""
    _ensure_ngc()
    assert configure_client is not None and download_resource is not None

    options.staging_dir.mkdir(parents=True, exist_ok=True)
    dl_root = options.staging_dir / "ngc_downloads"
    dl_root.mkdir(parents=True, exist_ok=True)

    client = configure_client(
        options.org_name,
        options.team_name,
        options.api_key,
        options.ngc_api_key_envvars,
        options.api_key_from_config,
    )

    result = FetchResult()
    artifacts: List[FetchedArtifact] = []

    def _dl(name: str, version: str, subdir: str) -> Path:
        dest = dl_root / subdir
        if options.force_update and dest.exists():
            print(f"--force-update: removing {dest}")
            _robust_rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {name} v{version} from {options.org_name}/{options.team_name} ...")
        download_resource(client, options.org_name, options.team_name, name, version, str(dest))
        print(f"  -> {dest}")
        return dest

    if not options.airgap_sdk_version or not options.registry_version:
        raise ValueError("airgap_sdk_version and registry_version must be set in [repo_airgap] or passed to fetch.")

    sdk_dest = _dl(options.airgap_sdk_resource, options.airgap_sdk_version, "airgap_sdk")
    artifacts.append(
        FetchedArtifact(
            resource_name=options.airgap_sdk_resource,
            version=options.airgap_sdk_version,
            download_root=sdk_dest,
        )
    )
    reg_dest = _dl(options.registry_resource, options.registry_version, "extensions_registry")
    artifacts.append(
        FetchedArtifact(
            resource_name=options.registry_resource,
            version=options.registry_version,
            download_root=reg_dest,
        )
    )
    result.artifacts = artifacts

    search_roots = [sdk_dest, reg_dest]
    result.sdk_zip = _find_kit_airgap_zip(search_roots)
    result.registry_dir = _find_registry_content_dir(search_roots)
    if result.registry_dir is None:
        result.registry_zip = _find_registry_zip(search_roots)
    return result


def _extract_archive(archive_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    extract_archive_to_folder(str(archive_path), str(dest))


def _merge_registry_into_kat(repo_toml: Path, registry_url: str) -> None:
    """Add or replace [repo_precache_exts] registries in the KAT project's repo.toml."""
    import tomllib

    text = repo_toml.read_text(encoding="utf-8")
    config = tomllib.loads(text)

    registry_toml = (
        "\n[repo_precache_exts]\n" "registries = [\n" f'    {{ name = "kit/airgap", url = "{registry_url}" }},\n' "]\n"
    )

    if "repo_precache_exts" in config:
        # Replace existing section — find and replace the line
        import re

        text = re.sub(
            r"\[repo_precache_exts\].*?(?=\n\[|\Z)",
            registry_toml.lstrip("\n"),
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        text += registry_toml

    repo_toml.write_text(text, encoding="utf-8")


def prepare_kat_project(
    options: PrepareOptions,
    source_test_file: Path,
    dev_eula_touch: bool = True,
) -> PrepareResult:
    """Extract airgap zip, inject tests, run new_project, merge registry, write state."""
    kit_root = options.kit_sdk_public_root
    staging = options.staging_dir
    staging.mkdir(parents=True, exist_ok=True)
    extract_root = staging / options.extract_subdir
    if extract_root.exists():
        _robust_rmtree(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)

    airgap_zip = options.airgap_zip or _find_kit_airgap_zip([staging / "ngc_downloads", staging])
    if not airgap_zip or not airgap_zip.is_file():
        raise FileNotFoundError(f"No {AIRGAP_ZIP_GLOB} found. Run `repo airgap fetch` or pass airgap_zip=.")

    print(f"Extracting airgap SDK: {airgap_zip.name} ...")
    _extract_archive(airgap_zip, extract_root)
    print(f"  -> {extract_root}")

    base_project = find_base_project_under_extract(extract_root)
    print("Injecting airgap test suite into base_project ...")
    inject_airgap_test_into_base_project(base_project, source_test_file)

    new_project_script = find_new_project_script(extract_root)
    dev_dir = extract_root / "dev"
    dev_dir.mkdir(parents=True, exist_ok=True)
    eula = dev_dir / ".omniverse_eula_accepted.txt"
    if dev_eula_touch:
        eula.write_text("EULA accepted\n", encoding="utf-8")

    kat_parent = staging
    kat_project = (kat_parent / options.kat_project_name).resolve()
    if kat_project.exists():
        _robust_rmtree(kat_project)

    np = Path(new_project_script)
    input_arg = "Repository>;[kit-repo-empty]: Kit-App-Template Repository/Project;" f"{kat_project.as_posix()};"
    if np.name.lower().startswith("new_project"):
        cmd = [str(np), f"--input={input_arg}"]
        cwd = str(np.parent)
    else:
        cmd = [str(np), "template", "new", f"--input={input_arg}"]
        cwd = str(dev_dir)

    print(f"Running new_project to scaffold KAT project at {kat_project} ...")
    env = os.environ.copy()
    env.setdefault("PM_DISABLE_PROGRESS_BAR", "1")
    subprocess.run(cmd, cwd=cwd, env=env, check=True)

    if not kat_project.is_dir():
        raise RuntimeError(f"new_project did not create {kat_project}")

    dl_roots = [staging / "ngc_downloads"]
    reg_extract = staging / "registry_extracted"
    if reg_extract.exists():
        print(f"Removing previous registry extraction: {reg_extract}")
        _robust_rmtree(reg_extract)
    reg_path = options.registry_dir or _find_registry_content_dir(dl_roots)
    if not reg_path or not reg_path.is_dir():
        reg_zip = _find_registry_zip(dl_roots)
        if reg_zip and reg_zip.is_file():
            print(f"Extracting registry zip: {reg_zip.name} (this may take a while) ...")
            _extract_archive(reg_zip, reg_extract)
            print(f"  -> {reg_extract}")
            reg_path = _find_registry_content_dir([reg_extract])
            if not reg_path:
                reg_path = reg_extract
        else:
            raise FileNotFoundError(
                "Registry directory or zip not found. Run fetch or pass registry_dir= to prepare_kat_project."
            )
    registry_url = reg_path.resolve().as_posix()

    print(f"Merging registry into KAT repo.toml: {registry_url}")
    _merge_registry_into_kat(kat_project / "repo.toml", registry_url)

    state_path = staging / STATE_FILENAME
    state = AirgapState(
        kat_project=str(kat_project),
        airgap_extract_root=str(extract_root),
        registry_path=str(reg_path),
        kit_sdk_public_root=str(kit_root),
    )
    state_path.write_text(json.dumps(state.to_json_dict(), indent=2), encoding="utf-8")

    return PrepareResult(
        extract_root=extract_root,
        kat_project=kat_project,
        state_path=state_path,
        registry_url_toml=registry_url,
    )


def clear_caches(options: ClearCacheOptions) -> ClearCacheResult:
    """Clear caches according to profile (see plan: airgap vs full)."""
    merged = ClearCacheOptions(
        profile=options.profile,
        preserve_packman=options.preserve_packman,
        session_env=dict(options.session_env or {}),
        interactive_confirm=options.interactive_confirm,
    )
    return clear_caches_impl(merged)


def run_airgap_tests(options: RunTestsOptions) -> int:
    """Run repo test --suite airgap from the KAT project root.

    Matches the Docker CI pattern: the test runner executes inside the prepared
    KAT project where repo-cache.json ensures all dependencies are pre-cached.

    When ``options.block_network`` is True, outbound network is blocked via OS
    firewall rules for the duration of the test run (requires admin/root).
    """
    kat: Optional[Path] = options.kat_project
    if kat is None and options.staging_dir:
        sp = options.staging_dir / STATE_FILENAME
        if sp.is_file():
            data = json.loads(sp.read_text(encoding="utf-8"))
            kat = Path(data["kat_project"])
    if kat is None:
        raise ValueError("kat_project or staging_dir with state.json is required")

    kat = kat.resolve()
    shell_ext = ".bat" if sys.platform == "win32" else ".sh"
    repo = kat / f"repo{shell_ext}"
    if not repo.is_file():
        raise FileNotFoundError(f"repo wrapper not found: {repo}")

    print(f"Running airgap tests from KAT project: {kat}")
    cmd = [str(repo), "test", "--suite", "airgap"]

    if options.block_network:
        from .network import blocked_network

        with blocked_network():
            p = subprocess.run(cmd, cwd=str(kat))
    else:
        p = subprocess.run(cmd, cwd=str(kat))

    return int(p.returncode)


def load_merged_airgap_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge [repo_ngc] and [repo_airgap] for fetch."""
    r_ngc = config.get("repo_ngc") or {}
    r_ag = config.get("repo_airgap") or {}
    return {"repo_ngc": r_ngc, "repo_airgap": r_ag}


def default_airgap_sdk_resource_name() -> str:
    return "kit-sdk-airgap-windows" if sys.platform == "win32" else "kit-sdk-airgap-linux"
