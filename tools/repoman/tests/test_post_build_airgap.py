# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#
"""Tests for air-gap packaging behaviour in post_build.

Covers two things that reach customers directly:

- The air-gap overview doc is staged into the package root, with NGC-only
  markup normalized so no dead links ship.
- The packaged app excludes build-time content. In air-gapped projects the Kit
  SDK is linked in as ``kit/``, so its packman cache appears as ``kit/_cache``
  and would otherwise be packaged and containerized with the app.
"""

import re
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
REPOMAN_DIR = REPO_ROOT / "tools" / "repoman"
if str(REPOMAN_DIR) not in sys.path:
    sys.path.insert(0, str(REPOMAN_DIR))


# --------------------------------------------------------------------------------------
# Air-gap overview staging
# --------------------------------------------------------------------------------------


@pytest.fixture()
def stage_overview(monkeypatch, tmp_path):
    """Return a callable that stages the given doc content and yields the result."""
    import post_build

    def _stage(content: str, filename: str = "KIT_AIRGAP_OVERVIEW.md"):
        src = tmp_path / "src" / filename
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(content, encoding="utf-8")

        monkeypatch.setattr(post_build, "AIRGAP_OVERVIEW_SRC", str(src))

        dest_dir = tmp_path / "package"
        dest_dir.mkdir(exist_ok=True)
        post_build._stage_airgap_overview(str(dest_dir))
        return dest_dir / post_build.AIRGAP_OVERVIEW_NAME

    return _stage


def test_overview_is_staged_into_package_root(stage_overview):
    dest = stage_overview("# Kit Air Gap Overview\n\nSome guidance.\n")
    assert dest.exists()
    assert "Kit Air Gap Overview" in dest.read_text(encoding="utf-8")


def test_resource_suffix_token_is_resolved(stage_overview):
    """${resource_suffix} is substituted at publish time, so it must not ship verbatim."""
    dest = stage_overview("See [Registry](../resources/kit-extensions-registry${resource_suffix})\n")
    assert "${resource_suffix}" not in dest.read_text(encoding="utf-8")


def test_ngc_resource_links_are_not_left_dead(stage_overview):
    """../resources/ links only resolve on the NGC catalog page, not inside the package."""
    dest = stage_overview("- [Kit Extension Registry](../resources/kit-extensions-registry)\n")
    text = dest.read_text(encoding="utf-8")
    assert "../resources/" not in text
    assert "Kit Extension Registry" in text


def test_external_links_are_preserved(stage_overview):
    """Only NGC-relative links are rewritten; real documentation links must survive."""
    url = "https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/configuring.html"
    dest = stage_overview(f"See [Configuring Kit]({url}) for details.\n")
    assert url in dest.read_text(encoding="utf-8")


def test_missing_source_is_not_fatal(monkeypatch, tmp_path):
    """A missing doc must warn rather than break the build."""
    import post_build

    monkeypatch.setattr(post_build, "AIRGAP_OVERVIEW_SRC", str(tmp_path / "does-not-exist.md"))
    dest_dir = tmp_path / "package"
    dest_dir.mkdir()

    post_build._stage_airgap_overview(str(dest_dir))

    assert not (dest_dir / post_build.AIRGAP_OVERVIEW_NAME).exists()


def test_shipped_overview_documents_registry_setup():
    """The doc we ship must actually cover the step air-gapped builds fail without."""
    doc = REPO_ROOT / "source" / "docs" / "KIT_AIRGAP_OVERVIEW.md"
    assert doc.exists(), f"air-gap overview missing: {doc}"

    text = doc.read_text(encoding="utf-8")
    assert "repo_precache_exts" in text
    assert "registries" in text


# --------------------------------------------------------------------------------------
# Packaged app excludes
# --------------------------------------------------------------------------------------


def _fat_package_excludes() -> list:
    repo_toml = REPO_ROOT / "base_project" / "repo.toml"
    config = tomllib.loads(repo_toml.read_text(encoding="utf-8"))
    return config["repo_package"]["packages"]["fat_package"]["files_exclude"]


@pytest.mark.parametrize(
    "pattern",
    [
        "**/_cache/**",
        "kit/dev/**",
        "kit/base_project/**",
        "kit/kit-gcov",
        "dev/**",
        "compile_commands.json",
    ],
)
def test_build_time_content_is_excluded(pattern):
    """Build-time content must not ship in the packaged app or any container built from it."""
    excludes = [entry for group in _fat_package_excludes() for entry in group]
    assert pattern in excludes, f"{pattern} missing from base_project fat_package files_exclude"


def test_cache_exclude_is_recursive():
    """A root-anchored pattern would miss kit/_cache, which is where the SDK cache lands.

    This is the regression that shipped ~956 MB of build tooling into customer
    containers: "_*/**" was present but only matches the package root.
    """
    excludes = [entry for group in _fat_package_excludes() for entry in group]
    cache_patterns = [p for p in excludes if "_cache" in p]

    assert cache_patterns, "no _cache exclude present"
    assert any(
        p.startswith("**/") for p in cache_patterns
    ), f"_cache exclude must be recursive to match kit/_cache, got: {cache_patterns}"


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a repo_package glob to a regex.

    Deliberately escapes everything that is not a glob wildcard - notably ``.``,
    so the ``.*/**`` dotfile pattern is not mistaken for "match anything".
    """
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out))


def test_cache_exclude_matches_the_sdk_cache():
    """The pattern must actually match where the SDK cache lands in an air-gapped project."""
    regex = _glob_to_regex("**/_cache/**")
    assert regex.fullmatch("kit/_cache/packman/chk/repo_kit_template/2.4.1/uv.lock")
    assert regex.fullmatch("_cache/packman/chk/premake/premake5")


def test_excludes_do_not_drop_runtime_paths():
    """Guard against an over-broad pattern removing something Kit needs at runtime."""
    excludes = [entry for group in _fat_package_excludes() for entry in group]
    runtime_paths = [
        "kit/kernel/plugins/libpython3.12.so.1.0",
        "kit/python/bin/python3.12",
        "kit/exts/omni.usd/omni/usd/_impl/__init__.py",
        "kit/exts/omni.kit.pip_archive/pip_prebundle/numpy/_core/numeric.py",
        "kit/extscore/omni.kit.registry.nucleus/extension.toml",
        "extscache/omni.kit.window.file-1.0.0/extension.toml",
        "apps/my_app.kit",
    ]
    for pattern in excludes:
        regex = _glob_to_regex(pattern)
        for path in runtime_paths:
            assert not regex.fullmatch(path), f"exclude {pattern!r} would drop runtime path {path!r}"


def test_cache_exclude_is_not_widened_to_all_underscore_dirs():
    """ "**/_*/**" would look like a tidier pattern but breaks the runtime.

    The SDK contains ~113 nested underscore-prefixed directories that are real
    runtime code - omni/usd/_impl, numpy/_core, pydantic/_internal and friends -
    14 of them _impl packages that Kit imports on startup. Keep the cache
    exclusion explicit.
    """
    excludes = [entry for group in _fat_package_excludes() for entry in group]
    assert "**/_*/**" not in excludes, "'**/_*/**' also matches runtime packages such as omni/usd/_impl and numpy/_core"

    regex = _glob_to_regex("**/_*/**")
    assert regex.fullmatch(
        "kit/exts/omni.usd/omni/usd/_impl/__init__.py"
    ), "sanity check: this pattern really does match runtime code"
