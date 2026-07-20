# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Tests for version_locks_common.py pure-logic functions."""

import pytest
from version_locks_common import (
    EtmFileConfig,
    VersionLocksConfig,
    _ext_name_from_id,
    check_etm_suite_exclusivity,
    check_version_conflicts,
    collect_all_extensions,
    collect_extensions_by_section,
    parse_master_lock_file,
    parse_team_toml,
    parse_team_toml_section,
)

# ---------------------------------------------------------------------------
# _ext_name_from_id
# ---------------------------------------------------------------------------


class TestExtNameFromId:
    def test_simple(self):
        assert _ext_name_from_id("omni.foo-1.2.3") == "omni.foo"

    def test_with_tag(self):
        assert _ext_name_from_id("omni.foo-tag-1.2.3") == "omni.foo-tag"

    def test_with_prerelease(self):
        assert _ext_name_from_id("omni.foo-1.2.3-rc.1") == "omni.foo"

    def test_no_version(self):
        assert _ext_name_from_id("omni.foo") == "omni.foo"

    def test_build_metadata(self):
        assert _ext_name_from_id("omni.foo-1.2.3+build.456") == "omni.foo"


# ---------------------------------------------------------------------------
# parse_team_toml
# ---------------------------------------------------------------------------


class TestParseTeamToml:
    def test_basic(self, tmp_team_file):
        f = tmp_team_file(
            "team_test.toml",
            """\
[team]
name = "TestTeam"
owner = "owner@test.com"

[extensions.default]
"omni.ext.a" = "1.0.0"
"omni.ext.b" = "2.0.0"

[extensions.sample_p1]
"omni.ext.c" = "3.0.0"
""",
        )
        team_info, kat, sample = parse_team_toml(f)
        assert team_info["name"] == "TestTeam"
        assert kat == {"omni.ext.a": "1.0.0", "omni.ext.b": "2.0.0"}
        assert sample == {"omni.ext.c": "3.0.0"}

    def test_empty_sections(self, tmp_team_file):
        f = tmp_team_file(
            "team_empty.toml",
            """\
[team]
name = "Empty"

[extensions.default]

[extensions.sample_p1]
""",
        )
        _, kat, sample = parse_team_toml(f)
        assert kat == {}
        assert sample == {}

    def test_missing_sample_p1(self, tmp_team_file):
        f = tmp_team_file(
            "team_nosp.toml",
            """\
[team]
name = "NoSample"

[extensions.default]
"omni.ext.a" = "1.0.0"
""",
        )
        _, kat, sample = parse_team_toml(f)
        assert kat == {"omni.ext.a": "1.0.0"}
        assert sample == {}


# ---------------------------------------------------------------------------
# parse_team_toml_section
# ---------------------------------------------------------------------------


class TestParseTeamTomlSection:
    def test_default_section(self, tmp_team_file):
        f = tmp_team_file(
            "team_sec.toml",
            """\
[team]
name = "Sec"

[extensions.default]
"omni.a" = "1.0.0"

[extensions.sample_p1]
"omni.b" = "2.0.0"
""",
        )
        assert parse_team_toml_section(f, "extensions.default") == {"omni.a": "1.0.0"}
        assert parse_team_toml_section(f, "extensions.sample_p1") == {"omni.b": "2.0.0"}

    def test_nonexistent_section(self, tmp_team_file):
        f = tmp_team_file("team_nosec.toml", '[team]\nname = "X"\n')
        assert parse_team_toml_section(f, "extensions.default") == {}


# ---------------------------------------------------------------------------
# check_version_conflicts
# ---------------------------------------------------------------------------


class TestCheckVersionConflicts:
    def test_no_conflicts(self, tmp_team_file):
        f1 = tmp_team_file(
            "team_a.toml",
            '[team]\nname="A"\n[extensions.default]\n"omni.x" = "1.0.0"\n',
        )
        f2 = tmp_team_file(
            "team_b.toml",
            '[team]\nname="B"\n[extensions.default]\n"omni.y" = "2.0.0"\n',
        )
        assert check_version_conflicts([f1, f2]) == []

    def test_detects_conflict(self, tmp_team_file):
        f1 = tmp_team_file(
            "team_a.toml",
            '[team]\nname="A"\n[extensions.default]\n"omni.shared" = "1.0.0"\n',
        )
        f2 = tmp_team_file(
            "team_b.toml",
            '[team]\nname="B"\n[extensions.default]\n"omni.shared" = "2.0.0"\n',
        )
        conflicts = check_version_conflicts([f1, f2])
        assert len(conflicts) == 1
        assert "omni.shared" in conflicts[0]

    def test_same_version_no_conflict(self, tmp_team_file):
        f1 = tmp_team_file(
            "team_a.toml",
            '[team]\nname="A"\n[extensions.default]\n"omni.shared" = "1.0.0"\n',
        )
        f2 = tmp_team_file(
            "team_b.toml",
            '[team]\nname="B"\n[extensions.default]\n"omni.shared" = "1.0.0"\n',
        )
        assert check_version_conflicts([f1, f2]) == []

    def test_placeholder_version_skipped(self, tmp_team_file):
        f1 = tmp_team_file(
            "team_a.toml",
            '[team]\nname="A"\n[extensions.default]\n"omni.x" = "0.0.0"\n',
        )
        f2 = tmp_team_file(
            "team_b.toml",
            '[team]\nname="B"\n[extensions.default]\n"omni.x" = "1.0.0"\n',
        )
        assert check_version_conflicts([f1, f2]) == []


# ---------------------------------------------------------------------------
# check_etm_suite_exclusivity
# ---------------------------------------------------------------------------


class TestCheckEtmSuiteExclusivity:
    ETM_CONFIGS = [
        EtmFileConfig(name="kat", title="", description="", section="extensions.default"),
        EtmFileConfig(name="sp1", title="", description="", section="extensions.sample_p1"),
    ]

    def test_no_duplicates(self, tmp_team_file):
        f = tmp_team_file(
            "team_ok.toml",
            """\
[team]
name = "OK"

[extensions.default]
"omni.a" = "1.0.0"

[extensions.sample_p1]
"omni.b" = "2.0.0"
""",
        )
        errors = check_etm_suite_exclusivity([f], self.ETM_CONFIGS)
        assert errors == []

    def test_detects_duplicate_in_same_file(self, tmp_team_file):
        f = tmp_team_file(
            "team_dup.toml",
            """\
[team]
name = "Dup"

[extensions.default]
"omni.shared" = "1.0.0"

[extensions.sample_p1]
"omni.shared" = "1.0.0"
""",
        )
        errors = check_etm_suite_exclusivity([f], self.ETM_CONFIGS)
        assert len(errors) == 1
        assert "omni.shared" in errors[0]
        assert "multiple ETM suites" in errors[0]

    def test_detects_multiple_duplicates(self, tmp_team_file):
        f = tmp_team_file(
            "team_multi.toml",
            """\
[team]
name = "Multi"

[extensions.default]
"omni.a" = "1.0.0"
"omni.b" = "2.0.0"
"omni.c" = "3.0.0"

[extensions.sample_p1]
"omni.a" = "1.0.0"
"omni.c" = "3.0.0"
""",
        )
        errors = check_etm_suite_exclusivity([f], self.ETM_CONFIGS)
        assert len(errors) == 2
        ext_names = [e.split(" appears")[0].strip() for e in errors]
        assert "omni.a" in ext_names
        assert "omni.c" in ext_names


# ---------------------------------------------------------------------------
# collect_all_extensions
# ---------------------------------------------------------------------------


class TestCollectAllExtensions:
    def test_merges_team_files(self, tmp_team_file):
        f1 = tmp_team_file(
            "team_a.toml",
            '[team]\nname="A"\n[extensions.default]\n"omni.a" = "1.0.0"\n[extensions.sample_p1]\n"omni.s1" = "1.0.0"\n',
        )
        f2 = tmp_team_file(
            "team_b.toml",
            '[team]\nname="B"\n[extensions.default]\n"omni.b" = "2.0.0"\n',
        )
        kat, sample = collect_all_extensions([f1, f2])
        assert "omni.a" in kat
        assert "omni.b" in kat
        assert "omni.s1" in sample


# ---------------------------------------------------------------------------
# collect_extensions_by_section
# ---------------------------------------------------------------------------


class TestCollectExtensionsBySection:
    def test_groups_by_section(self, tmp_team_file):
        etm = [
            EtmFileConfig(name="kat", title="", description="", section="extensions.default"),
            EtmFileConfig(name="sp1", title="", description="", section="extensions.sample_p1"),
        ]
        f = tmp_team_file(
            "team_x.toml",
            """\
[team]
name = "X"

[extensions.default]
"omni.d" = "1.0.0"

[extensions.sample_p1]
"omni.s" = "2.0.0"
""",
        )
        result = collect_extensions_by_section([f], etm)
        assert result["extensions.default"] == {"omni.d": "1.0.0"}
        assert result["extensions.sample_p1"] == {"omni.s": "2.0.0"}


# ---------------------------------------------------------------------------
# parse_master_lock_file
# ---------------------------------------------------------------------------


class TestParseMasterLockFile:
    def test_parses_enabled_list(self, tmp_kit_file):
        f = tmp_kit_file(
            "version_locks.kit",
            """\
[package]
title = "Version Locks"

[dependencies]
"omni.a" = { version = "=1.0.0" }

[settings.app.exts]
enabled = [
\t"omni.a-1.0.0",
\t"omni.b-2.3.4",  # transitive
\t"omni.physx.gpu-110.1.1",
]
""",
        )
        exts = parse_master_lock_file(f)
        assert ("omni.a", "1.0.0") in exts
        assert ("omni.b", "2.3.4") in exts
        assert ("omni.physx.gpu", "110.1.1") in exts

    def test_empty_enabled(self, tmp_kit_file):
        f = tmp_kit_file(
            "empty_locks.kit",
            "[settings.app.exts]\nenabled = [\n]\n",
        )
        assert parse_master_lock_file(f) == []


# ---------------------------------------------------------------------------
# VersionLocksConfig
# ---------------------------------------------------------------------------


class TestVersionLocksConfig:
    def test_defaults(self):
        cfg = VersionLocksConfig.from_repo_config({})
        assert len(cfg.etm_files) == 2
        assert cfg.etm_files[0].section == "extensions.default"
        assert cfg.etm_files[1].section == "extensions.sample_p1"

    def test_custom_etm_files(self):
        cfg = VersionLocksConfig.from_repo_config(
            {
                "repo_version_locks": {
                    "etm_files": [
                        {
                            "name": "custom",
                            "title": "Custom",
                            "description": "desc",
                            "section": "extensions.custom",
                        }
                    ]
                }
            }
        )
        assert len(cfg.etm_files) == 1
        assert cfg.etm_files[0].name == "custom"

    def test_run_solve_extensions_returns_5_tuple(self):
        """Verify the return type annotation of run_solve_extensions is a 5-tuple.

        This is a static contract test: if someone changes the return count,
        tests like test_generate_etm_files.py will also break at import time.
        """
        import inspect

        from version_locks_common import run_solve_extensions

        sig = inspect.signature(run_solve_extensions)
        # Return annotation is a Tuple with 5 elements
        ann = sig.return_annotation
        assert hasattr(ann, "__args__"), "return annotation should be a Tuple"
        assert len(ann.__args__) == 5, f"Expected 5-tuple return, got {len(ann.__args__)}"
