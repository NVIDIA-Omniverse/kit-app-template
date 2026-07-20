"""Tests for release-readiness pure-logic helpers."""

import verify_release_readiness


def test_extract_version_scopes_from_branches_supports_minor_and_patch_scopes():
    branches = ["prod-110", "integ-110.2", "prod-110.2.0", "scratch"]

    assert verify_release_readiness.extract_version_scopes_from_branches(branches) == [
        "110",
        "110.2",
        "110.2.0",
    ]


def test_validate_deploy_exts_branch_compatibility_accepts_110_2_scoped_branches(monkeypatch):
    monkeypatch.setattr(verify_release_readiness, "get_kit_kernel_version", lambda: "110.2.0")

    errors = verify_release_readiness.validate_deploy_exts_branch_compatibility(
        {
            "repo_deploy_exts": {
                "pipeline_repo": {
                    "branch": {
                        "prod-110.2": {},
                        "integ-110.2": {},
                    }
                }
            }
        }
    )

    assert errors == []


def test_validate_deploy_exts_branch_compatibility_rejects_wrong_minor(monkeypatch):
    monkeypatch.setattr(verify_release_readiness, "get_kit_kernel_version", lambda: "110.2.0")

    errors = verify_release_readiness.validate_deploy_exts_branch_compatibility(
        {
            "repo_deploy_exts": {
                "pipeline_repo": {
                    "branch": {
                        "prod-110.1": {},
                        "integ-110.1": {},
                    }
                }
            }
        }
    )

    assert errors
    assert "110.2.0" in errors[0]
    assert "110.1" in errors[0]
