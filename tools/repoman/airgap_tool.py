# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

"""repo airgap — fetch NGC artifacts, prepare a KAT project, clear caches, run tests offline."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import omni.repo.man
from airgap import api
from airgap.types import ClearCacheOptions, FetchOptions, PrepareOptions, RunTestsOptions
from omni.repo.man import resolve_tokens


def _staging_dir(config: Dict[str, Any]) -> Path:
    ag = config.get("repo_airgap") or {}
    raw = ag.get("staging_dir", "${root}/_build/airgap")
    return Path(resolve_tokens(raw)).resolve()


def _run_cli(options: argparse.Namespace, config: Dict[str, Any]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    root = Path(resolve_tokens("${root}")).resolve()
    r_ngc = config.get("repo_ngc") or {}
    r_ag = config.get("repo_airgap") or {}
    staging = _staging_dir(config)

    cmd = getattr(options, "airgap_cmd", None)
    if not cmd:
        return

    if cmd == "fetch":
        import os

        org = options.org_name or r_ag.get("org_name") or r_ngc.get("org_name") or os.environ.get("NGC_ORG")
        team = options.team_name or r_ag.get("team_name") or r_ngc.get("team_name") or os.environ.get("NGC_TEAM")
        sdk_name = (
            options.airgap_sdk_resource or r_ag.get("airgap_sdk_resource") or api.default_airgap_sdk_resource_name()
        )
        reg_name = options.registry_resource or r_ag.get("registry_resource", "kit-extensions-registry")
        sdk_ver = options.airgap_sdk_version or r_ag.get("airgap_sdk_version", "").strip()
        reg_ver = options.registry_version or r_ag.get("registry_version", "").strip()

        if not sdk_ver or not reg_ver:
            inferred = api.get_base_version()
            if not sdk_ver:
                sdk_ver = inferred
            if not reg_ver:
                reg_ver = inferred
            print(
                f"Inferred version {inferred} from VERSION.md (override with --airgap-sdk-version / --registry-version)"
            )

        api_key = getattr(options, "api_key", None) or r_ngc.get("api_key")
        api_key_from_config = bool(not getattr(options, "api_key", None) and r_ngc.get("api_key"))
        envvars = r_ngc.get("ngc_api_key_envvars", ["NGC_API_KEY"])

        fo = FetchOptions(
            staging_dir=staging,
            org_name=org,
            team_name=team,
            ngc_api_key_envvars=list(envvars),
            airgap_sdk_resource=sdk_name,
            airgap_sdk_version=sdk_ver,
            registry_resource=reg_name,
            registry_version=reg_ver,
            api_key=api_key,
            api_key_from_config=api_key_from_config,
            force_update=options.force_update,
        )
        result = api.fetch_assets(fo)
        print(f"Fetch complete.")
        print(f"  SDK zip: {result.sdk_zip}")
        if result.registry_dir:
            print(f"  Registry dir: {result.registry_dir}")
        else:
            print(f"  Registry zip: {result.registry_zip} (will be extracted during prepare)")

    elif cmd == "prepare":
        src_test = root / "source" / "tests" / "airgap" / "test_kat_airgap.py"
        if not src_test.is_file():
            print(f"error: missing {src_test}", file=sys.stderr)
            sys.exit(1)
        po = PrepareOptions(
            kit_sdk_public_root=root,
            staging_dir=staging,
            kat_project_name=options.kat_project_name or r_ag.get("kat_project_name", "my-kit-airgap-test"),
            airgap_zip=Path(options.airgap_zip).resolve() if options.airgap_zip else None,
            registry_dir=Path(options.registry_dir).resolve() if options.registry_dir else None,
        )
        pr = api.prepare_kat_project(po, src_test)
        print(f"Prepared KAT project: {pr.kat_project}")
        print(f"State written to: {pr.state_path}")

    elif cmd == "clear-cache":
        profile = options.profile or "airgap"
        cc = ClearCacheOptions(
            profile=profile,
            preserve_packman=not options.no_preserve_packman,
            interactive_confirm=False,
        )
        out = api.clear_caches(cc)
        print(f"Cleared {len(out.cleared_paths)} path(s).")

    elif cmd == "test":
        st = staging if options.use_state else None
        rc = api.run_airgap_tests(
            RunTestsOptions(
                kit_sdk_public_root=root,
                kat_project=Path(options.kat_project).resolve() if options.kat_project else None,
                staging_dir=st,
                block_network=options.block_network,
            )
        )
        sys.exit(rc)

    else:
        print(f"error: unknown subcommand {cmd}", file=sys.stderr)
        sys.exit(2)


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict[str, Any]) -> Optional[Callable]:
    """Entry point for `repo airgap`."""
    parser.description = (
        "Airgap local test workflow: fetch NGC artifacts, prepare a KAT project, clear caches, run tests offline."
    )
    omni.repo.man.add_config_arg(parser)

    sub = parser.add_subparsers(dest="airgap_cmd", help="subcommands")

    fetch_p = sub.add_parser("fetch", help="Download kit-sdk-airgap and kit-extensions-registry from NGC")
    fetch_p.add_argument("--org-name", default=None, help="Override [repo_ngc].org_name")
    fetch_p.add_argument("--team-name", default=None, help="Override [repo_ngc].team_name")
    fetch_p.add_argument("--api-key", default=None, dest="api_key", help="NGC API key override")
    fetch_p.add_argument("--airgap-sdk-resource", default=None, help="NGC resource name for airgap SDK zip")
    fetch_p.add_argument("--airgap-sdk-version", default=None, help="Resource version (default: from VERSION.md)")
    fetch_p.add_argument("--registry-resource", default=None, help="NGC resource name for extensions registry")
    fetch_p.add_argument(
        "--registry-version", default=None, help="Registry resource version (default: from VERSION.md)"
    )
    fetch_p.add_argument(
        "--force-update",
        action="store_true",
        default=False,
        help="Delete existing downloads before fetching (use when NGC content changed at same version)",
    )

    prep_p = sub.add_parser("prepare", help="Extract airgap zip, inject tests, run new_project, merge registry")
    prep_p.add_argument("--airgap-zip", default=None, help="Path to kit-sdk-airgap zip (default: search staging)")
    prep_p.add_argument("--registry-dir", default=None, help="Extracted kit-extensions-registry directory")
    prep_p.add_argument("--kat-project-name", default=None, dest="kat_project_name", help="Destination folder name")

    clr_p = sub.add_parser("clear-cache", help="Clear Omniverse caches (default profile: airgap-safe)")
    clr_p.add_argument(
        "--profile",
        choices=["airgap", "full"],
        default="airgap",
        help="airgap: OV caches only; full: also uv/packman (dangerous offline)",
    )
    clr_p.add_argument(
        "--no-preserve-packman",
        action="store_true",
        help="With --profile full, allow clearing packman roots",
    )

    test_p = sub.add_parser("test", help="Run repo test --suite airgap with KIT_AIRGAP_TEST_PROJECT set")
    test_p.add_argument("--kat-project", default=None, help="KAT project path (default: read staging state.json)")
    test_p.add_argument(
        "--use-state",
        action="store_true",
        default=True,
        help="Load kat project from _build/airgap/state.json (default: true)",
    )
    test_p.add_argument("--no-use-state", action="store_false", dest="use_state")
    test_p.add_argument(
        "--block-network",
        action="store_true",
        default=False,
        help="Block outbound network via OS firewall for the test run (requires admin/root)",
    )

    return _run_cli
