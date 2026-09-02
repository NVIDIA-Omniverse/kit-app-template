# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import zipfile
from pathlib import Path

import verify_package_pythons


def _write_archive(path: Path, members: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for member in members:
            archive.writestr(member, "test")
    return path


def test_one_python_revision_passes(tmp_path, capsys):
    archive = _write_archive(
        tmp_path / "airgap.zip",
        [
            "kit-sdk-airgap/_cache/packman/python/3.12.13-nv6-windows-x86_64/python.exe",
            "kit-sdk-airgap/_cache/packman/python/3.12.13-nv6-windows-x86_64/python312.dll",
        ],
    )

    assert verify_package_pythons.main([str(archive)]) == 0
    assert "PASS: the package contains one Packman Python revision" in capsys.readouterr().out


def test_multiple_python_revisions_fail_with_actionable_diagnostic(tmp_path, capsys):
    archive = _write_archive(
        tmp_path / "airgap.zip",
        [
            "_cache/packman/python/3.12.13-nv3-windows-x86_64/python.exe",
            "_cache/packman/python/3.12.13-nv6-windows-x86_64/python.exe",
        ],
    )

    assert verify_package_pythons.main([str(archive)]) == 1
    output = capsys.readouterr().out
    assert "3.12.13-nv3-windows-x86_64" in output
    assert "3.12.13-nv6-windows-x86_64" in output
    assert "multiple top-level Packman Python revisions" in output
    assert "Align those pins" in output


def test_same_revision_for_multiple_platforms_passes(tmp_path):
    archive = _write_archive(
        tmp_path / "airgap.zip",
        [
            "_cache/packman/python/3.12.13-nv6-windows-x86_64/python.exe",
            "_cache/packman/python/3.12.13-nv6-manylinux_2_35_x86_64/bin/python3",
        ],
    )

    assert verify_package_pythons.main([str(archive)]) == 0


def test_carbonite_scripting_python_variants_are_ignored(tmp_path, capsys):
    archive = _write_archive(
        tmp_path / "airgap.zip",
        [
            "carb_sdk/plugins/scripting-python-3.10/carb.scripting-python.plugin.dll",
            "carb_sdk/plugins/scripting-python-3.11/carb.scripting-python.plugin.dll",
            "carb_sdk/plugins/scripting-python-3.12/carb.scripting-python.plugin.dll",
        ],
    )

    assert verify_package_pythons.main([str(archive)]) == 0
    assert "no top-level _cache/packman/python packages" in capsys.readouterr().out


def test_missing_archive_fails_clearly(tmp_path, capsys):
    missing = tmp_path / "missing.zip"

    assert verify_package_pythons.main([str(missing)]) == 1
    assert f"package archive does not exist: {missing}" in capsys.readouterr().err
