import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_publish_module(monkeypatch):
    omni = types.ModuleType("omni")
    repo = types.ModuleType("omni.repo")
    man = types.ModuleType("omni.repo.man")
    ngc = types.ModuleType("omni.repo.ngc")

    man.resolve_tokens = lambda value: value
    ngc.configure_client = lambda *args, **kwargs: object()
    ngc.upload_resource = lambda *args, **kwargs: None
    omni.repo = repo
    repo.man = man
    repo.ngc = ngc

    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.repo", repo)
    monkeypatch.setitem(sys.modules, "omni.repo.man", man)
    monkeypatch.setitem(sys.modules, "omni.repo.ngc", ngc)
    pipeline_release_stub = types.ModuleType("pipeline_release")
    pipeline_release_stub.RELEASE_VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+)-(dev|stage|rc)\.(\d+)$")
    monkeypatch.setitem(sys.modules, "pipeline_release", pipeline_release_stub)
    monkeypatch.setitem(sys.modules, "stage_kit_kernel", types.ModuleType("stage_kit_kernel"))

    spec = importlib.util.spec_from_file_location(
        "publish_under_test",
        REPO_ROOT / "tools" / "ci" / "publish.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("file_name", "platform"),
    [
        (
            "kit-sdk-public@110.2.0-dev.0+ompe-92313-release-pipeline.5087.ed7e918d.gl."
            "windows-x86_64.release.016f63ce.zip",
            "windows-x86_64",
        ),
        (
            "kit-sdk-airgap@110.2.0-dev.0+ompe-92313-release-pipeline.5087.ed7e918d.gl."
            "manylinux_2_35_aarch64.release.016f63ce.zip",
            "manylinux_2_35_aarch64",
        ),
        (
            "kit-sdk-public@110.2.0-dev.0+ompe-92313-release-pipeline.5087.ed7e918d.gl." "windows-x86_64.zip",
            "windows-x86_64",
        ),
    ],
)
def test_get_package_version_part_strips_platform_config_and_kit_hash(monkeypatch, file_name, platform):
    publish = load_publish_module(monkeypatch)

    assert (
        publish.get_package_version_part(file_name, platform, include_build_metadata=True)
        == "110.2.0-dev.0+ompe-92313-release-pipeline.5087.ed7e918d.gl"
    )
    assert publish.get_package_version_part(file_name, platform) == "110.2.0-dev.0"


def test_write_publish_dotenv_generates_generic_downstream_metadata(monkeypatch, tmp_path):
    publish = load_publish_module(monkeypatch)
    dotenv_path = tmp_path / "publish.env"

    publish.write_publish_dotenv(
        dotenv_path,
        org_name="0520191291295001",
        team_name="kit-dev",
        branch_type="feature",
        resource_suffix="",
        dry_run=True,
        records=[
            {
                "source_name": "kit-sdk-public@110.2.0-stage.7.linux-x86_64.zip",
                "version": "110.2.0-stage.7",
                "ngc_resource_name": "kit-sdk-linux",
                "resource_base_name": "kit-sdk",
            },
            {
                "source_name": "kit-sdk-airgap@110.2.0-stage.7.linux-x86_64.zip",
                "version": "110.2.0-stage.7",
                "ngc_resource_name": "kit-sdk-airgap-linux",
                "resource_base_name": "kit-sdk-airgap",
            },
        ],
    )

    dotenv = dict(line.split("=", 1) for line in dotenv_path.read_text(encoding="utf-8").splitlines())

    assert dotenv["PUBLISH_NGC_VERSION"] == "110.2.0-stage.7"
    assert dotenv["PUBLISH_NGC_VERSION_BASE"] == "110.2.0"
    assert dotenv["PUBLISH_NGC_VERSION_QUALIFIER"] == "stage"
    assert dotenv["PUBLISH_NGC_VERSION_NUMBER"] == "7"
    assert dotenv["PUBLISH_NGC_VERSIONS"] == "110.2.0-stage.7"
    assert dotenv["PUBLISH_NGC_ORG"] == "0520191291295001"
    assert dotenv["PUBLISH_NGC_TEAM"] == "kit-dev"
    assert dotenv["PUBLISH_NGC_RESOURCES"] == "kit-sdk-airgap-linux,kit-sdk-linux"
    assert dotenv["PUBLISH_NGC_RESOURCE_VERSIONS"] == (
        "kit-sdk-airgap-linux:110.2.0-stage.7,kit-sdk-linux:110.2.0-stage.7"
    )
    assert dotenv["PUBLISH_NGC_AIRGAP_RESOURCE_VERSIONS"] == "kit-sdk-airgap-linux:110.2.0-stage.7"
    assert dotenv["PUBLISH_DRY_RUN"] == "true"


@pytest.mark.parametrize(
    ("release_version", "expected_base", "expected_qualifier", "expected_number"),
    [
        ("110.2.0-stage.7", "110.2.0", "stage", "7"),
        ("110.3.0-dev.12", "110.3.0", "dev", "12"),
        ("110.1.1-rc.2", "110.1.1", "rc", "2"),
    ],
)
def test_write_publish_dotenv_parses_version_qualifier(
    monkeypatch, tmp_path, release_version, expected_base, expected_qualifier, expected_number
):
    publish = load_publish_module(monkeypatch)
    dotenv_path = tmp_path / "publish.env"

    publish.write_publish_dotenv(
        dotenv_path,
        org_name="0520191291295001",
        team_name="kit-dev",
        branch_type="feature",
        resource_suffix="",
        dry_run=False,
        records=[
            {
                "source_name": f"kit-sdk-public@{release_version}.linux-x86_64.zip",
                "version": release_version,
                "ngc_resource_name": "kit-sdk-linux",
                "resource_base_name": "kit-sdk",
            },
        ],
    )

    dotenv = dict(line.split("=", 1) for line in dotenv_path.read_text(encoding="utf-8").splitlines())

    assert dotenv["PUBLISH_NGC_VERSION"] == release_version
    assert dotenv["PUBLISH_NGC_VERSION_BASE"] == expected_base
    assert dotenv["PUBLISH_NGC_VERSION_QUALIFIER"] == expected_qualifier
    assert dotenv["PUBLISH_NGC_VERSION_NUMBER"] == expected_number


def test_write_publish_dotenv_leaves_qualifier_fields_empty_for_mixed_versions(monkeypatch, tmp_path):
    publish = load_publish_module(monkeypatch)
    dotenv_path = tmp_path / "publish.env"

    publish.write_publish_dotenv(
        dotenv_path,
        org_name="0520191291295001",
        team_name="kit-dev",
        branch_type="feature",
        resource_suffix="",
        dry_run=False,
        records=[
            {
                "source_name": "kit-sdk-public@110.2.0-stage.7.linux-x86_64.zip",
                "version": "110.2.0-stage.7",
                "ngc_resource_name": "kit-sdk-linux",
                "resource_base_name": "kit-sdk",
            },
            {
                "source_name": "kit-sdk-public@110.2.0-stage.8.windows-x86_64.zip",
                "version": "110.2.0-stage.8",
                "ngc_resource_name": "kit-sdk-windows",
                "resource_base_name": "kit-sdk",
            },
        ],
    )

    dotenv = dict(line.split("=", 1) for line in dotenv_path.read_text(encoding="utf-8").splitlines())

    assert dotenv["PUBLISH_NGC_VERSION"] == "110.2.0-stage.7,110.2.0-stage.8"
    assert dotenv["PUBLISH_NGC_VERSION_BASE"] == ""
    assert dotenv["PUBLISH_NGC_VERSION_QUALIFIER"] == ""
    assert dotenv["PUBLISH_NGC_VERSION_NUMBER"] == ""
