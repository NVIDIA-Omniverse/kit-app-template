import importlib.util
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
    monkeypatch.setitem(sys.modules, "pipeline_release", types.ModuleType("pipeline_release"))
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
