# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Tests for public dependency verification output."""

from verify_deps import MissingDependency, format_missing_dependencies, gitlab_log_section


def test_missing_dependency_summary_deduplicates_packages_across_checks():
    missing = [
        MissingDependency(
            deps_file="tools/deps/public-deps.packman.xml",
            platform="linux-x86_64",
            build_config="release",
            remote="packman:cloudfront",
            package_name="repo_man",
            package_version="2.6.4",
        ),
        MissingDependency(
            deps_file="tools/deps/public-deps.packman.xml",
            platform="windows-x86_64",
            build_config="release",
            remote="packman:cloudfront",
            package_name="repo_man",
            package_version="2.6.4",
        ),
    ]

    summary = format_missing_dependencies(missing)

    assert "1 unique package(s)" in summary
    assert summary.count("  repo_man\n") == 1
    assert "version: 2.6.4" in summary
    assert "linux-x86_64 / release" in summary
    assert "windows-x86_64 / release" in summary
    assert "_repo/missing_deps.csv" in summary


def test_gitlab_log_section_collapses_verbose_details(monkeypatch, capsys):
    monkeypatch.setenv("GITLAB_CI", "true")
    monkeypatch.setattr("verify_deps.time.time", lambda: 1234)

    with gitlab_log_section("verify_deps_linux", "Packman details"):
        print("verbose URL")

    output = capsys.readouterr().out
    assert "section_start:1234:verify_deps_linux[collapsed=true]" in output
    assert "Packman details" in output
    assert "verbose URL" in output
    assert "section_end:1234:verify_deps_linux" in output
