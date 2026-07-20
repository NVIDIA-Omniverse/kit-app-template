# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Tests for resolve_version_locks.py pure-logic functions."""

import pytest
from resolve_version_locks import (
    _apply_version_constraints_to_deps,
    _build_generated_block,
    _build_transitive_dep_lines,
    _check_direct_deps_in_lock,
    _compute_dep_chain,
    _find_settings_app_exts_ranges,
    _find_version_locks_comment_block,
    _parse_kit_dependencies,
    _update_kit_file_with_version_locks,
    _warn_missing_optional_deps,
)

# ---------------------------------------------------------------------------
# _parse_kit_dependencies
# ---------------------------------------------------------------------------


class TestParseKitDependencies:
    def test_basic(self, tmp_kit_file):
        f = tmp_kit_file(
            "app.kit",
            """\
[package]
title = "My App"

[dependencies]
"omni.kit.mainwindow" = {}
"omni.kit.viewport.window" = {}
"omni.physx.bundle" = { version = "110.1.1" }

[settings]
foo = "bar"
""",
        )
        deps = _parse_kit_dependencies(f)
        assert deps == ["omni.kit.mainwindow", "omni.kit.viewport.window", "omni.physx.bundle"]

    def test_no_dependencies_section(self, tmp_kit_file):
        f = tmp_kit_file("empty.kit", "[package]\ntitle = 'X'\n")
        assert _parse_kit_dependencies(f) == []

    def test_stops_at_next_section(self, tmp_kit_file):
        f = tmp_kit_file(
            "stop.kit",
            """\
[dependencies]
"omni.a" = {}

[settings]
"not.an.ext" = "value"
""",
        )
        deps = _parse_kit_dependencies(f)
        assert deps == ["omni.a"]


# ---------------------------------------------------------------------------
# _find_settings_app_exts_ranges
# ---------------------------------------------------------------------------


class TestFindSettingsAppExtsRanges:
    def test_single_block(self):
        lines = [
            "[settings]",
            "foo = 1",
            "[settings.app.exts]",
            'enabled = ["omni.a-1.0.0"]',
            "",
            "[other]",
        ]
        ranges = _find_settings_app_exts_ranges(lines)
        assert ranges == [(2, 4)]

    def test_no_block(self):
        lines = ["[settings]", "foo = 1", "[dependencies]", '"omni.a" = {}']
        assert _find_settings_app_exts_ranges(lines) == []


# ---------------------------------------------------------------------------
# _find_version_locks_comment_block
# ---------------------------------------------------------------------------


class TestFindVersionLocksCommentBlock:
    def test_standard_block(self):
        lines = [
            "[dependencies]",
            "",
            "########################################################################################################################",
            "# BEGIN GENERATED PART (Remove from 'BEGIN' to 'END' to regenerate)",
            "########################################################################################################################",
            "# content",
            "# END GENERATED PART",
        ]
        result = _find_version_locks_comment_block(lines)
        assert result == (2, 6)

    def test_legacy_block(self):
        lines = [
            "[dependencies]",
            "# --- BEGIN version locks (applied at build time, do not commit) ---",
            "stuff",
            "# --- END version locks ---",
        ]
        result = _find_version_locks_comment_block(lines)
        assert result == (1, 3)

    def test_no_block(self):
        lines = ["[dependencies]", '"omni.a" = {}']
        assert _find_version_locks_comment_block(lines) is None

    def test_missing_end_marker(self):
        lines = [
            "# BEGIN GENERATED PART (Remove from 'BEGIN' to 'END' to regenerate)",
            "content",
        ]
        assert _find_version_locks_comment_block(lines) is None


# ---------------------------------------------------------------------------
# _compute_dep_chain
# ---------------------------------------------------------------------------


class TestComputeDepChain:
    def test_direct_dep(self):
        chain = _compute_dep_chain(
            "omni.physx.gpu",
            direct_dep_names=["omni.physx.gpu"],
            deps_map={"omni.physx.gpu": []},
        )
        assert chain == ["omni.physx.gpu"]

    def test_one_hop(self):
        chain = _compute_dep_chain(
            "omni.physx.gpu",
            direct_dep_names=["omni.physx.foundation"],
            deps_map={"omni.physx.foundation": ["omni.physx.gpu"]},
        )
        assert chain == ["omni.physx.foundation", "omni.physx.gpu"]

    def test_two_hops(self):
        chain = _compute_dep_chain(
            "omni.gpu_foundation",
            direct_dep_names=["omni.physx.bundle"],
            deps_map={
                "omni.physx.bundle": ["omni.physx.foundation"],
                "omni.physx.foundation": ["omni.gpu_foundation"],
            },
        )
        assert chain == ["omni.physx.bundle", "omni.physx.foundation", "omni.gpu_foundation"]

    def test_unreachable(self):
        chain = _compute_dep_chain(
            "omni.unrelated",
            direct_dep_names=["omni.a"],
            deps_map={"omni.a": ["omni.b"]},
        )
        assert chain is None

    def test_no_deps_map(self):
        assert _compute_dep_chain("x", ["y"], None) is None

    def test_empty_deps_map(self):
        assert _compute_dep_chain("x", ["y"], {}) is None


# ---------------------------------------------------------------------------
# _check_direct_deps_in_lock
# ---------------------------------------------------------------------------


class TestCheckDirectDepsInLock:
    def test_all_present(self):
        errors = _check_direct_deps_in_lock(
            all_direct={"omni.a": "1.0.0"},
            all_resolved=[("omni.a", "1.0.0"), ("omni.b", "2.0.0")],
            ext_to_team_files={"omni.a": ["team_test"]},
            deps_map={"omni.a": ["omni.b"]},
            skipped_names=set(),
        )
        assert errors == []

    def test_missing_dep_reported(self):
        errors = _check_direct_deps_in_lock(
            all_direct={"omni.a": "1.0.0"},
            all_resolved=[("omni.a", "1.0.0")],
            ext_to_team_files={"omni.a": ["team_test"]},
            deps_map={"omni.a": ["omni.missing"]},
            skipped_names=set(),
        )
        assert len(errors) == 1
        assert "omni.missing" in errors[0]
        assert "omni.a" in errors[0]

    def test_skipped_dep_allowed(self):
        errors = _check_direct_deps_in_lock(
            all_direct={"omni.a": "1.0.0"},
            all_resolved=[("omni.a", "1.0.0")],
            ext_to_team_files={"omni.a": ["team_test"]},
            deps_map={"omni.a": ["omni.kit.bundled"]},
            skipped_names={"omni.kit.bundled"},
        )
        assert errors == []

    def test_no_deps_map(self):
        errors = _check_direct_deps_in_lock(
            all_direct={"omni.a": "1.0.0"},
            all_resolved=[("omni.a", "1.0.0")],
            ext_to_team_files={},
            deps_map=None,
            skipped_names=set(),
        )
        assert errors == []


# ---------------------------------------------------------------------------
# _warn_missing_optional_deps
# ---------------------------------------------------------------------------


class TestWarnMissingOptionalDeps:
    def test_no_warnings_when_resolved(self, capsys):
        _warn_missing_optional_deps(
            all_direct={"omni.a": "1.0.0"},
            all_resolved=[("omni.a", "1.0.0"), ("omni.opt", "1.0.0")],
            ext_to_team_files={"omni.a": ["team_test"]},
            optional_deps_map={"omni.a": ["omni.opt"]},
            skipped_names=set(),
        )

    def test_no_warnings_when_skipped(self, capsys):
        _warn_missing_optional_deps(
            all_direct={"omni.a": "1.0.0"},
            all_resolved=[("omni.a", "1.0.0")],
            ext_to_team_files={"omni.a": ["team_test"]},
            optional_deps_map={"omni.a": ["omni.kit.window.viewport"]},
            skipped_names={"omni.kit.window.viewport"},
        )

    def test_no_crash_when_no_optional_deps(self):
        _warn_missing_optional_deps(
            all_direct={"omni.a": "1.0.0"},
            all_resolved=[("omni.a", "1.0.0")],
            ext_to_team_files={},
            optional_deps_map=None,
            skipped_names=set(),
        )


# ---------------------------------------------------------------------------
# _apply_version_constraints_to_deps
# ---------------------------------------------------------------------------


class TestApplyVersionConstraintsToDeps:
    def test_pins_matching_deps(self):
        lines = [
            "[dependencies]",
            '"omni.warp.core" = {} # Warp support',
            '"omni.graph.core" = {}',
            "",
            "[settings]",
        ]
        out, modified, deps_end = _apply_version_constraints_to_deps(lines, {"omni.warp.core": "1.11.0"})
        assert out[1] == '"omni.warp.core" = { version = "=1.11.0" } # Warp support'
        assert out[2] == '"omni.graph.core" = {}'
        assert modified == {"omni.warp.core"}
        assert deps_end == 4

    def test_preserves_comment(self):
        lines = [
            "[dependencies]",
            '"omni.physx" = { version = "110.1.1" } # Physics runtime',
            "[settings]",
        ]
        out, modified, _ = _apply_version_constraints_to_deps(lines, {"omni.physx": "110.1.1"})
        assert "# Physics runtime" in out[1]
        assert 'version = "=110.1.1"' in out[1]

    def test_unresolved_dep_unchanged(self):
        lines = [
            "[dependencies]",
            '"omni.hydra.rtx" = {}  # Viewport renderer',
            "[settings]",
        ]
        out, modified, _ = _apply_version_constraints_to_deps(lines, {})
        assert out[1] == '"omni.hydra.rtx" = {}  # Viewport renderer'
        assert modified == set()

    def test_no_dependencies_section(self):
        lines = ["[package]", 'title = "X"']
        out, modified, deps_end = _apply_version_constraints_to_deps(lines, {"omni.a": "1.0.0"})
        assert out == lines
        assert modified == set()
        assert deps_end is None

    def test_deps_at_end_of_file(self):
        lines = [
            "[dependencies]",
            '"omni.a" = {}',
        ]
        out, modified, deps_end = _apply_version_constraints_to_deps(lines, {"omni.a": "2.0.0"})
        assert out[1] == '"omni.a" = { version = "=2.0.0" }'
        assert deps_end == 2

    def test_multiple_deps_pinned(self):
        lines = [
            "[dependencies]",
            '"omni.a" = {}',
            '"omni.b" = {} # B ext',
            '"omni.c" = {}',
            "[settings]",
        ]
        version_map = {"omni.a": "1.0.0", "omni.c": "3.0.0"}
        out, modified, _ = _apply_version_constraints_to_deps(lines, version_map)
        assert 'version = "=1.0.0"' in out[1]
        assert out[2] == '"omni.b" = {} # B ext'
        assert 'version = "=3.0.0"' in out[3]
        assert modified == {"omni.a", "omni.c"}

    def test_does_not_mutate_input(self):
        lines = ["[dependencies]", '"omni.a" = {}', "[settings]"]
        original = list(lines)
        _apply_version_constraints_to_deps(lines, {"omni.a": "1.0.0"})
        assert lines == original


# ---------------------------------------------------------------------------
# _build_transitive_dep_lines
# ---------------------------------------------------------------------------


class TestBuildTransitiveDepLines:
    def test_excludes_already_modified(self):
        resolved = [("omni.a", "1.0.0"), ("omni.b", "2.0.0"), ("omni.c", "3.0.0")]
        result = _build_transitive_dep_lines(resolved, already_modified={"omni.a", "omni.c"})
        assert len(result) == 1
        assert '"omni.b"' in result[0]
        assert 'version = "=2.0.0"' in result[0]
        assert "# transitive" in result[0]

    def test_empty_when_all_modified(self):
        resolved = [("omni.a", "1.0.0")]
        assert _build_transitive_dep_lines(resolved, already_modified={"omni.a"}) == []

    def test_sorted_output(self):
        resolved = [("omni.z", "1.0.0"), ("omni.a", "2.0.0"), ("omni.m", "3.0.0")]
        result = _build_transitive_dep_lines(resolved, already_modified=set())
        names = [line.split('"')[1] for line in result]
        assert names == ["omni.a", "omni.m", "omni.z"]

    def test_all_unmodified(self):
        resolved = [("omni.x", "1.0.0"), ("omni.y", "2.0.0")]
        result = _build_transitive_dep_lines(resolved, already_modified=set())
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _build_generated_block
# ---------------------------------------------------------------------------


class TestBuildGeneratedBlock:
    def test_contains_begin_end_markers(self):
        block = _build_generated_block([("omni.a", "1.0.0")], direct_deps=["omni.a"])
        text = "\n".join(block)
        assert "# BEGIN GENERATED PART" in text
        assert "# END GENERATED PART" in text

    def test_direct_dep_no_marker(self):
        block = _build_generated_block([("omni.a", "1.0.0")], direct_deps=["omni.a"])
        text = "\n".join(block)
        assert '"omni.a-1.0.0",' in text
        assert "# transitive" not in text

    def test_transitive_dep_marked(self):
        block = _build_generated_block(
            [("omni.a", "1.0.0"), ("omni.b", "2.0.0")],
            direct_deps=["omni.a"],
        )
        text = "\n".join(block)
        assert '"omni.a-1.0.0",' in text
        assert '"omni.b-2.0.0",  # transitive' in text

    def test_sorted(self):
        block = _build_generated_block(
            [("omni.z", "1.0.0"), ("omni.a", "2.0.0")],
            direct_deps=["omni.z", "omni.a"],
        )
        text = "\n".join(block)
        assert text.index("omni.a") < text.index("omni.z")


# ---------------------------------------------------------------------------
# _update_kit_file_with_version_locks (integration)
# ---------------------------------------------------------------------------

SAMPLE_KIT_FILE = """\
[package]
title = "Test App"

[dependencies]
"omni.a" = {} # Alpha
"omni.b" = {}

[settings]
foo = "bar"

[[test]]
args = ["--no-window"]
"""


class TestUpdateKitFileWithVersionLocks:
    def test_pins_direct_deps_in_dependencies_section(self, tmp_path):
        kit_file = tmp_path / "app.kit"
        kit_file.write_text(SAMPLE_KIT_FILE)

        _update_kit_file_with_version_locks(
            kit_file,
            resolved_extensions=[("omni.a", "1.0.0"), ("omni.b", "2.0.0")],
            direct_deps=["omni.a", "omni.b"],
        )

        content = kit_file.read_text()
        assert '"omni.a" = { version = "=1.0.0" } # Alpha' in content
        assert '"omni.b" = { version = "=2.0.0" }' in content

    def test_inserts_transitive_deps(self, tmp_path):
        kit_file = tmp_path / "app.kit"
        kit_file.write_text(SAMPLE_KIT_FILE)

        _update_kit_file_with_version_locks(
            kit_file,
            resolved_extensions=[("omni.a", "1.0.0"), ("omni.t", "3.0.0")],
            direct_deps=["omni.a"],
        )

        content = kit_file.read_text()
        assert '"omni.a" = { version = "=1.0.0" } # Alpha' in content
        assert '"omni.t" = { version = "=3.0.0" }  # transitive (version lock)' in content
        # Transitive deps should be inside [dependencies], before [settings]
        lines = content.split("\n")
        t_idx = next(i for i, l in enumerate(lines) if "omni.t" in l)
        settings_idx = next(i for i, l in enumerate(lines) if l.strip() == "[settings]")
        assert t_idx < settings_idx

    def test_appends_generated_block(self, tmp_path):
        kit_file = tmp_path / "app.kit"
        kit_file.write_text(SAMPLE_KIT_FILE)

        _update_kit_file_with_version_locks(
            kit_file,
            resolved_extensions=[("omni.a", "1.0.0")],
            direct_deps=["omni.a"],
        )

        content = kit_file.read_text()
        assert "# BEGIN GENERATED PART" in content
        assert "# END GENERATED PART" in content
        assert "app.exts.enabled" in content

    def test_idempotent_rerun(self, tmp_path):
        kit_file = tmp_path / "app.kit"
        kit_file.write_text(SAMPLE_KIT_FILE)

        args = dict(
            resolved_extensions=[("omni.a", "1.0.0"), ("omni.b", "2.0.0")],
            direct_deps=["omni.a", "omni.b"],
        )
        _update_kit_file_with_version_locks(kit_file, **args)
        first_run = kit_file.read_text()
        _update_kit_file_with_version_locks(kit_file, **args)
        second_run = kit_file.read_text()

        assert first_run == second_run

    def test_preserves_settings_and_test_sections(self, tmp_path):
        kit_file = tmp_path / "app.kit"
        kit_file.write_text(SAMPLE_KIT_FILE)

        _update_kit_file_with_version_locks(
            kit_file,
            resolved_extensions=[("omni.a", "1.0.0")],
            direct_deps=["omni.a"],
        )

        content = kit_file.read_text()
        assert "[settings]" in content
        assert 'foo = "bar"' in content
        assert "[[test]]" in content
        assert 'args = ["--no-window"]' in content

    def test_unresolved_dep_left_unconstrained(self, tmp_path):
        kit_file = tmp_path / "app.kit"
        kit_file.write_text(SAMPLE_KIT_FILE)

        _update_kit_file_with_version_locks(
            kit_file,
            resolved_extensions=[("omni.a", "1.0.0")],
            direct_deps=["omni.a"],
        )

        content = kit_file.read_text()
        assert '"omni.b" = {}' in content

    def test_replaces_old_generated_block(self, tmp_path):
        kit_file = tmp_path / "app.kit"
        kit_file.write_text(SAMPLE_KIT_FILE)

        _update_kit_file_with_version_locks(
            kit_file,
            resolved_extensions=[("omni.a", "1.0.0")],
            direct_deps=["omni.a"],
        )
        # Now re-apply with version 2.0.0
        _update_kit_file_with_version_locks(
            kit_file,
            resolved_extensions=[("omni.a", "2.0.0")],
            direct_deps=["omni.a"],
        )

        content = kit_file.read_text()
        assert 'version = "=2.0.0"' in content
        assert 'version = "=1.0.0"' not in content
        assert content.count("# BEGIN GENERATED PART") == 1
