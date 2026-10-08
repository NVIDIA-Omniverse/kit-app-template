"""Tests for release-readiness pure-logic helpers."""

from pathlib import Path

import toml
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


def test_validate_stage_registry_compatibility_accepts_matching_minor():
    errors = verify_release_readiness.validate_stage_registry_compatibility(
        {
            "repo_deploy_exts": {"pipeline_repo": {"branch": {"integ-110.4": {}}}},
            "registry_mapping": {
                "stage": {
                    "registries": [
                        {
                            "name": "kit/stage/sdk",
                            "url": "https://example.test/exts/kit/integ/${kit_version_short}/slug/sdk",
                        }
                    ]
                }
            },
        },
        "110.4.0",
    )

    assert errors == []


def test_validate_stage_registry_compatibility_rejects_stale_minor():
    errors = verify_release_readiness.validate_stage_registry_compatibility(
        {
            "repo_deploy_exts": {"pipeline_repo": {"branch": {"integ-110.4": {}}}},
            "registry_mapping": {
                "stage": {
                    "registries": [
                        {
                            "name": "kit/stage/sdk",
                            "url": "https://example.test/exts/kit/integ/110.0/old-slug/sdk",
                        }
                    ]
                }
            },
        },
        "110.5.0",
    )

    assert len(errors) == 1
    assert "kit/stage/sdk" in errors[0]
    assert "110.0" in errors[0]
    assert "integ-110.4" in errors[0]


def test_repo_stage_registry_matches_deploy_exts_branch():
    repo_root = Path(__file__).resolve().parents[3]
    config = toml.load(repo_root / "repo.toml")

    deploy_errors = verify_release_readiness.validate_deploy_exts_branch_compatibility(config)
    registry_errors = verify_release_readiness.validate_stage_registry_compatibility(
        config, verify_release_readiness.get_kit_kernel_version()
    )

    assert deploy_errors + registry_errors == []
