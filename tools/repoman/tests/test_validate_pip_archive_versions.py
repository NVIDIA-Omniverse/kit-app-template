# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Tests for pip archive version consistency validation."""

import sys
from pathlib import Path

import omni.repo.man
import pytest

REPO_ROOT = Path(__file__).parents[3]
sys.path.insert(0, str(REPO_ROOT / "tools" / "ci"))

import check_pip_archive_versions
from validate_pip_archive_versions import find_version_mismatches, get_exact_extension_ids


def test_locked_pip_archives_compare_shared_normalized_packages_only(tmp_path):
    lock_path = tmp_path / "version_locks.kit"
    lock_path.write_text(
        "[dependencies]\n"
        '"omni.services.pip_archive" = { version = "=0.18.13" }\n'
        '"omni.other.pip_archive" = { version = "=1.2.3" }\n'
        '"omni.not.an.archive" = { version = "=4.5.6" }\n'
        "[settings.app.exts]\n"
        'enabled = ["omni.services.pip_archive-0.18.13", "omni.transitive.pip_archive-2.0.0"]\n'
    )
    assert get_exact_extension_ids(lock_path) == [
        "omni.services.pip_archive-0.18.13",
        "omni.transitive.pip_archive-2.0.0",
    ]

    archives = {
        "omni.kit.pip_archive": {
            "python_multipart": "0.0.32",
            "pillow": "12.3.0",
            "kit-only": "1.0",
        },
        "omni.services.pip_archive": {
            "python-multipart": "0.0.32",
            "Pillow": ["11.3.0", "12.3.0"],
            "services-only": "2.0",
        },
        "omni.other.pip_archive": {
            "pillow": "12.3.0",
        },
    }

    assert find_version_mismatches(archives) == {
        "pillow": {
            "12.3.0": [
                "omni.kit.pip_archive",
                "omni.services.pip_archive",
                "omni.other.pip_archive",
            ],
            "11.3.0": ["omni.services.pip_archive"],
        }
    }


def test_check_job_marks_version_drift_for_allowed_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(check_pip_archive_versions.omni.repo.ci, "get_repo_config", lambda: {})
    monkeypatch.setattr(check_pip_archive_versions, "set_config", lambda config: None)
    monkeypatch.setattr(check_pip_archive_versions, "get_root_dir", lambda: tmp_path)
    monkeypatch.setattr(check_pip_archive_versions, "fetch_kit_dependency", lambda: None)
    monkeypatch.setattr(check_pip_archive_versions, "get_master_lock_path", lambda: tmp_path / "version_locks.kit")
    monkeypatch.setattr(
        check_pip_archive_versions,
        "validate_pip_archive_versions",
        lambda lock_path: {"pillow": {"11.0": ["first"], "12.0": ["second"]}},
    )

    (tmp_path / "_repo").mkdir()
    with pytest.raises(omni.repo.man.RepoToolError, match="versions are inconsistent"):
        check_pip_archive_versions.main(None)

    assert (tmp_path / "_repo" / check_pip_archive_versions.MISMATCH_MARKER).is_file()


def test_check_job_keeps_operational_errors_blocking(monkeypatch, tmp_path):
    monkeypatch.setattr(check_pip_archive_versions.omni.repo.ci, "get_repo_config", lambda: {})
    monkeypatch.setattr(check_pip_archive_versions, "set_config", lambda config: None)
    monkeypatch.setattr(check_pip_archive_versions, "get_root_dir", lambda: tmp_path)
    monkeypatch.setattr(check_pip_archive_versions, "fetch_kit_dependency", lambda: None)
    monkeypatch.setattr(check_pip_archive_versions, "get_master_lock_path", lambda: tmp_path / "version_locks.kit")

    def fail_validation(lock_path):
        raise omni.repo.man.RepoToolError("registry unavailable")

    marker = tmp_path / "_repo" / check_pip_archive_versions.MISMATCH_MARKER
    marker.parent.mkdir()
    marker.write_text("stale")
    monkeypatch.setattr(check_pip_archive_versions, "validate_pip_archive_versions", fail_validation)

    with pytest.raises(omni.repo.man.RepoToolError, match="registry unavailable"):
        check_pip_archive_versions.main(None)

    assert not marker.exists()
