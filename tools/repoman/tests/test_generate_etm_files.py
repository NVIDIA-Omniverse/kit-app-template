# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Tests for generate_etm_files.py pure-logic functions."""

import pytest
from generate_etm_files import _generate_etm_file_content
from version_locks_common import EtmFileConfig, run_solve_extensions

# ---------------------------------------------------------------------------
# _generate_etm_file_content
# ---------------------------------------------------------------------------


class TestGenerateEtmFileContent:
    ETM_CFG = EtmFileConfig(
        name="omni.etm.list.test",
        title="ETM Test",
        description="Test ETM file",
        section="extensions.default",
    )

    def test_basic_output(self):
        content = _generate_etm_file_content(
            etm_cfg=self.ETM_CFG,
            direct_extensions=["omni.a", "omni.b"],
            all_resolved=[("omni.a", "1.0.0"), ("omni.b", "2.0.0"), ("omni.c", "3.0.0")],
            version="110.1.0",
        )
        assert "[package]" in content
        assert 'title = "ETM Test"' in content
        assert 'version = "110.1.0"' in content
        assert '"omni.a" = { version = "1.0.0" }' in content
        assert '"omni.b" = { version = "2.0.0" }' in content
        assert '"omni.c" = { version = "3.0.0" }  # transitive' in content

    def test_marks_transitive(self):
        content = _generate_etm_file_content(
            etm_cfg=self.ETM_CFG,
            direct_extensions=["omni.direct"],
            all_resolved=[("omni.direct", "1.0.0"), ("omni.transitive", "2.0.0")],
            version="110.0.0",
        )
        lines = content.split("\n")
        direct_line = [l for l in lines if "omni.direct" in l][0]
        transitive_line = [l for l in lines if "omni.transitive" in l][0]
        assert "# transitive" not in direct_line
        assert "# transitive" in transitive_line

    def test_sorted_output(self):
        content = _generate_etm_file_content(
            etm_cfg=self.ETM_CFG,
            direct_extensions=["omni.z", "omni.a"],
            all_resolved=[("omni.z", "1.0.0"), ("omni.a", "2.0.0"), ("omni.m", "3.0.0")],
            version="110.0.0",
        )
        lines = [l for l in content.split("\n") if "omni." in l and "version" in l]
        ext_names = [l.split('"')[1] for l in lines]
        assert ext_names == sorted(ext_names)


# ---------------------------------------------------------------------------
# run_solve_extensions return value contract
# ---------------------------------------------------------------------------


class TestRunSolveExtensionsContract:
    def test_return_annotation_is_5_tuple(self):
        """Ensures callers unpacking 2 values (the bug) will be caught."""
        import inspect

        sig = inspect.signature(run_solve_extensions)
        ann = sig.return_annotation
        assert hasattr(ann, "__args__"), "return annotation must be a generic Tuple"
        assert len(ann.__args__) == 5, (
            f"run_solve_extensions must return a 5-tuple, got {len(ann.__args__)}-tuple. "
            "All callers must unpack 5 values."
        )
