# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Tests for dump_resolved_dependencies.py pure-logic helpers.

The dump script runs inside Kit (via --exec) and calls main() at module level,
so we cannot import it directly in a test environment.  Instead we load only
the helper functions by parsing the source AST and compiling them in an
isolated namespace.
"""

import ast
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Load helper functions from the dump script without executing main()
# ---------------------------------------------------------------------------

_DUMP_SCRIPT = Path(__file__).resolve().parent.parent.parent / "ci" / "dump_resolved_dependencies.py"


def _load_helpers():
    """Extract top-level function defs from the dump script and compile them."""
    source = _DUMP_SCRIPT.read_text()
    tree = ast.parse(source)

    # Keep only function definitions (skip the bare main() call and imports)
    func_defs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

    module = ast.Module(body=func_defs, type_ignores=[])
    ast.fix_missing_locations(module)
    code = compile(module, str(_DUMP_SCRIPT), "exec")
    ns: dict = {"sys": sys, "print": print}
    exec(code, ns)
    return ns


_helpers = _load_helpers()
_get_extension_name = _helpers["_get_extension_name"]
_ext_id_to_name_and_version = _helpers["_ext_id_to_name_and_version"]
_extension_has_kit_hash_in_registry = _helpers["_extension_has_kit_hash_in_registry"]
_find_kit_bundled_dep_names = _helpers["_find_kit_bundled_dep_names"]


# ---------------------------------------------------------------------------
# _get_extension_name
# ---------------------------------------------------------------------------


class TestGetExtensionName:
    def test_simple(self):
        assert _get_extension_name("omni.foo-1.2.3") == "omni.foo"

    def test_with_tag(self):
        assert _get_extension_name("omni.foo-tag-1.2.3") == "omni.foo-tag"

    def test_with_prerelease(self):
        assert _get_extension_name("omni.foo-1.2.3-rc.1") == "omni.foo"

    def test_tag_with_prerelease(self):
        assert _get_extension_name("omni.foo-tag-1.2.3-rc.1") == "omni.foo-tag"

    def test_bare_name(self):
        assert _get_extension_name("omni.foo") == "omni.foo"

    def test_build_metadata(self):
        assert _get_extension_name("omni.foo-1.0.0+build.abc") == "omni.foo"


# ---------------------------------------------------------------------------
# _ext_id_to_name_and_version
# ---------------------------------------------------------------------------


class TestExtIdToNameAndVersion:
    def test_simple(self):
        assert _ext_id_to_name_and_version("omni.foo-1.2.3") == ("omni.foo", "1.2.3")

    def test_with_tag(self):
        assert _ext_id_to_name_and_version("omni.foo-tag-1.2.3") == ("omni.foo-tag", "1.2.3")

    def test_build_suffix(self):
        name, version = _ext_id_to_name_and_version("omni.foo-1.0.0+build.123")
        assert name == "omni.foo"
        assert version == "1.0.0+build.123"


# ---------------------------------------------------------------------------
# _extension_has_kit_hash_in_registry / _find_kit_bundled_dep_names
#
# These tests expose a bug: extensions that are Kit SDK bundled LOCALLY
# (have kitHash in get_extension_dict) but are NOT in the registry are not
# detected.  _extension_has_kit_hash_in_registry only calls
# get_registry_extension_dict; it should fall back to get_extension_dict
# (mirroring the pattern in get_resolved_extensions).
# ---------------------------------------------------------------------------


def _make_mock_manager(registry=None, local=None, versions=None):
    """Build a mock Kit extension manager.

    Args:
        registry: dict mapping ext_id -> info dict (or None) for get_registry_extension_dict.
        local: dict mapping ext_id -> info dict for get_extension_dict.
        versions: dict mapping ext_name -> list of {"id": ext_id} for fetch_extension_versions.
    """
    registry = registry or {}
    local = local or {}
    versions = versions or {}
    mgr = MagicMock()
    mgr.get_registry_extension_dict.side_effect = lambda eid: registry.get(eid)
    mgr.get_extension_dict.side_effect = lambda eid: local.get(eid)
    mgr.fetch_extension_versions.side_effect = lambda name: versions.get(name, [])
    return mgr


class TestExtensionHasKitHashInRegistry:
    def test_found_in_registry(self):
        mgr = _make_mock_manager(
            versions={"omni.foo": [{"id": "omni.foo-1.0.0"}]},
            registry={"omni.foo-1.0.0": {"package/target/kitHash": "110.0"}},
        )
        assert _extension_has_kit_hash_in_registry(mgr, "omni.foo") is True

    def test_not_in_registry_at_all(self):
        mgr = _make_mock_manager(versions={"omni.foo": []})
        assert _extension_has_kit_hash_in_registry(mgr, "omni.foo") is False

    def test_in_registry_without_kit_hash(self):
        mgr = _make_mock_manager(
            versions={"omni.foo": [{"id": "omni.foo-1.0.0"}]},
            registry={"omni.foo-1.0.0": {}},
        )
        assert _extension_has_kit_hash_in_registry(mgr, "omni.foo") is False

    def test_local_only_kit_bundled_extension_detected(self):
        """Extension exists locally with kitHash but NOT in the registry.

        This simulates omni.iray.settings.core which ships with Kit SDK
        and has kitHash locally, but may not appear in the registry.
        """
        mgr = _make_mock_manager(
            versions={"omni.iray.settings.core": [{"id": "omni.iray.settings.core-0.6.5"}]},
            registry={},
            local={"omni.iray.settings.core-0.6.5": {"package/target/kitHash": "110.0"}},
        )
        assert _extension_has_kit_hash_in_registry(mgr, "omni.iray.settings.core") is True


class TestFindKitBundledDepNames:
    def test_registry_kit_bundled_detected(self):
        """Deps in the registry with kitHash are returned."""
        mgr = _make_mock_manager(
            versions={"omni.kit.core": [{"id": "omni.kit.core-1.0.0"}]},
            registry={"omni.kit.core-1.0.0": {"package/target/kitHash": "110.0"}},
        )
        result = {
            "resolved_extensions": [
                {"name": "omni.a", "version": "1.0.0", "dependencies": ["omni.kit.core"], "optional_dependencies": []},
            ],
            "skipped_kit_bundled": [],
            "skipped_core": [],
            "skipped_local": [],
        }
        assert _find_kit_bundled_dep_names(mgr, result) == ["omni.kit.core"]

    def test_local_only_kit_bundled_dep_detected(self):
        """A dep that is Kit-bundled locally (not in registry) should be detected.

        This is the omni.iray.settings.core scenario: the extension is an
        optional dep of a resolved extension, ships with Kit SDK (has kitHash
        locally), but is not available in the extension registry.
        """
        mgr = _make_mock_manager(
            versions={"omni.iray.settings.core": [{"id": "omni.iray.settings.core-0.6.5"}]},
            registry={},
            local={"omni.iray.settings.core-0.6.5": {"package/target/kitHash": "110.0"}},
        )
        result = {
            "resolved_extensions": [
                {
                    "name": "omni.rtx.window.settings",
                    "version": "1.0.0",
                    "dependencies": [],
                    "optional_dependencies": ["omni.iray.settings.core"],
                },
            ],
            "skipped_kit_bundled": [],
            "skipped_core": [],
            "skipped_local": [],
        }
        found = _find_kit_bundled_dep_names(mgr, result)
        assert "omni.iray.settings.core" in found
