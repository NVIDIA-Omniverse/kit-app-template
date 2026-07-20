import base64
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tools" / "ci"))

import pipeline_release


def make_root(tmp_path: Path, version: str = "110.2.0-dev.4", kit_app_version: str | None = None) -> Path:
    root = tmp_path
    (root / "tools" / "deps").mkdir(parents=True)
    (root / "source" / "apps").mkdir(parents=True)
    (root / "VERSION.md").write_text(version + "\n")
    (root / "tools" / "deps" / "kit-sdk.packman.xml").write_text(
        '<project toolsVersion="5.0">\n'
        '  <dependency name="kit_sdk_${config}">\n'
        '    <package name="kit-kernel" version="110.2.0+master.1.abc.gl.${platform_target_abi}.${config}"/>\n'
        "  </dependency>\n"
        "</project>\n"
    )
    kit_app_version = kit_app_version or version
    (root / "source" / "apps" / "omni.app.editor.base.kit").write_text(
        "[package]\n"
        'title = "Kit Base Editor App"\n'
        f'version = "{kit_app_version}"\n'
        "\n"
        "[dependencies]\n"
        '"omni.some.extension" = { version = "=1.2.3" }\n'
    )
    (root / "source" / "apps" / "omni.app.editor.full.kit").write_text(
        "[dependencies]\n" '"omni.app.editor.base" = {}\n'
    )
    return root


@pytest.mark.parametrize("version", ["110.2.0-dev.1", "110.2.0-stage.12", "110.2.0-rc.3"])
def test_validate_release_version_accepts_supported_prereleases(version):
    assert pipeline_release.validate_release_version(version)[0] == "110.2.0"


@pytest.mark.parametrize("version", ["110.2.0", "110.2.0-beta.1", "110.2-stage.1"])
def test_validate_release_version_rejects_unsupported_versions(version):
    with pytest.raises(ValueError):
        pipeline_release.validate_release_version(version)


def test_next_release_number_uses_success_tags_only():
    tags = [
        "kit-sdk-public/v110.2.0-stage.0",
        "kit-sdk-public/v110.2.0-stage.4",
        "kit-sdk-public/v110.2.0-rc.9",
        "other/v110.2.0-stage.99",
    ]

    assert pipeline_release.next_release_number(tags, "kit-sdk-public/v", "110.2.0", "stage") == 5


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("master", "dev"),
        ("main", "dev"),
        ("feature/main", "dev"),
        ("feature/110.1", "stage"),
        ("production/110.1", "stage"),
        ("experimental/110.1", "stage"),
        ("release/110.1", "stage"),
        ("feature/my-change", None),
        ("workstream/kit-release", None),
    ],
)
def test_expected_branch_qualifier_keeps_feature_main_as_dev(branch, expected):
    assert pipeline_release.expected_branch_qualifier({"CI_COMMIT_REF_NAME": branch}) == expected


def test_feature_main_rejects_stage_branch_version(tmp_path):
    root = make_root(tmp_path, version="110.2.0-stage.7")

    with pytest.raises(ValueError, match="feature/main.*dev"):
        pipeline_release.resolve_release_inputs(
            root,
            {
                "CI_COMMIT_REF_NAME": "feature/main",
                "KIT_SDK_PUBLIC_PUBLISH": "true",
                "KIT_KERNEL_VERSION": "110.2.0",
            },
        )


def test_feature_main_accepts_dev_branch_version(tmp_path):
    root = make_root(tmp_path, version="110.2.0-dev.7")

    inputs = pipeline_release.resolve_release_inputs(
        root,
        {
            "CI_COMMIT_REF_NAME": "feature/main",
            "KIT_SDK_PUBLIC_PUBLISH": "true",
            "KIT_KERNEL_VERSION": "110.2.0",
        },
    )

    assert inputs.release_version == "110.2.0-dev.7"
    assert inputs.next_release_version == "110.2.0-dev.8"


def test_explicit_publish_uses_checked_in_version_without_kernel_override(tmp_path):
    root = make_root(tmp_path, version="110.2.0-dev.7")

    inputs = pipeline_release.resolve_release_inputs(
        root,
        {
            "CI_COMMIT_REF_NAME": "feature/main",
            "KIT_SDK_PUBLIC_PUBLISH": "true",
        },
    )

    assert inputs.release_version == "110.2.0-dev.7"
    assert inputs.kit_kernel_version is None
    assert inputs.next_release_version == "110.2.0-dev.8"
    assert inputs.bump_branch_after_publish is True


@pytest.mark.parametrize(
    "env",
    [
        {"UPSTREAM_KIT_PUBLISH": "true"},
        {"KIT_KERNEL_VERSION": "110.2.0"},
        {"KIT_SDK_PUBLIC_RELEASE_VERSION": "110.2.0-rc.1"},
        {"KIT_SDK_PUBLIC_RELEASE_BASE_VERSION": "110.2.0"},
        {"KIT_SDK_PUBLIC_VERSION_QUALIFIER": "rc"},
    ],
)
def test_release_inputs_require_explicit_publish_switch(tmp_path, env):
    root = make_root(tmp_path)

    assert pipeline_release.resolve_release_inputs(root, env) is None


def test_upstream_kit_publish_uses_checked_in_branch_version(monkeypatch, tmp_path):
    root = make_root(tmp_path, version="110.2.0-stage.7")
    monkeypatch.setattr(
        pipeline_release,
        "list_release_tags",
        lambda *args: (_ for _ in ()).throw(AssertionError("stage/dev should not use tags")),
    )

    inputs = pipeline_release.resolve_release_inputs(
        root,
        {
            "KIT_SDK_PUBLIC_PUBLISH": "true",
            "UPSTREAM_KIT_PUBLISH": "true",
            "KIT_KERNEL_VERSION": "110.2.0+master.293874.016f63ce.gl",
        },
    )

    assert inputs.release_version == "110.2.0-stage.7"
    assert inputs.next_release_version == "110.2.0-stage.8"
    assert inputs.bump_branch_after_publish is True
    assert inputs.record_release_tag is False
    assert inputs.release_tag is None


def test_manual_web_pipeline_defaults_to_rc(monkeypatch, tmp_path):
    root = make_root(tmp_path, version="110.2.0-stage.7")
    monkeypatch.setattr(pipeline_release, "list_release_tags", lambda *args: ["kit-sdk-public/v110.2.0-rc.3"])

    inputs = pipeline_release.resolve_release_inputs(
        root,
        {
            "CI_PIPELINE_SOURCE": "web",
            "KIT_SDK_PUBLIC_PUBLISH": "true",
            "KIT_SDK_PUBLIC_RELEASE_BASE_VERSION": "110.2.0",
        },
    )

    assert inputs.release_version == "110.2.0-rc.4"
    assert inputs.record_release_tag is True
    assert inputs.bump_branch_after_publish is False
    assert inputs.release_tag == "kit-sdk-public/v110.2.0-rc.4"


def test_version_qualifier_only_supports_rc(tmp_path):
    root = make_root(tmp_path, version="110.2.0-stage.7")

    with pytest.raises(ValueError, match="only supports rc"):
        pipeline_release.resolve_release_inputs(
            root,
            {
                "KIT_SDK_PUBLIC_PUBLISH": "true",
                "KIT_SDK_PUBLIC_VERSION_QUALIFIER": "stage",
            },
        )


def test_apply_workspace_release_inputs_patches_files(tmp_path):
    root = make_root(tmp_path)

    inputs = pipeline_release.apply_workspace_release_inputs(
        root,
        {
            "KIT_SDK_PUBLIC_PUBLISH": "true",
            "KIT_SDK_PUBLIC_RELEASE_VERSION": "110.2.0-rc.1",
            "KIT_KERNEL_VERSION": "110.2.0+master.293874.016f63ce.gl",
        },
    )

    assert inputs.release_version == "110.2.0-rc.1"
    assert inputs.record_release_tag is True
    assert inputs.bump_branch_after_publish is False
    assert (root / "VERSION.md").read_text() == "110.2.0-rc.1\n"
    assert (
        'version="110.2.0+master.293874.016f63ce.gl.${platform_target_abi}.${config}"'
        in (root / "tools" / "deps" / "kit-sdk.packman.xml").read_text()
    )
    assert 'version = "110.2.0"' in (root / "source" / "apps" / "omni.app.editor.base.kit").read_text()


def test_apply_workspace_release_inputs_patches_dev_app_kit_version(tmp_path):
    root = make_root(tmp_path, version="110.2.0-dev.7", kit_app_version="110.2.0-dev.6")

    inputs = pipeline_release.apply_workspace_release_inputs(
        root,
        {
            "CI_COMMIT_REF_NAME": "feature/main",
            "KIT_SDK_PUBLIC_PUBLISH": "true",
        },
    )

    assert inputs.release_version == "110.2.0-dev.7"
    base_kit = (root / "source" / "apps" / "omni.app.editor.base.kit").read_text()
    assert 'version = "110.2.0-dev.7"' in base_kit
    assert '"omni.some.extension" = { version = "=1.2.3" }' in base_kit
    assert 'version = "110.2.0-dev.7"\n\n[dependencies]' in base_kit


def test_patch_kit_package_version_content_preserves_following_line():
    content = (
        "[package]\n" 'description = "Refreshed Base Editor App"\n' 'version = "110.2.0-dev.2"\n' 'keywords = ["app"]\n'
    )

    patched, changed = pipeline_release.patch_kit_package_version_content(content, "110.2.0-dev.3")

    assert changed is True
    assert 'version = "110.2.0-dev.3"\nkeywords = ["app"]' in patched
    assert '"110.2.0-dev.3"keywords' not in patched


def test_apply_workspace_release_inputs_dry_run_does_not_patch_files(tmp_path):
    root = make_root(tmp_path)
    original_version = (root / "VERSION.md").read_text()
    original_packman_xml = (root / "tools" / "deps" / "kit-sdk.packman.xml").read_text()
    original_base_kit = (root / "source" / "apps" / "omni.app.editor.base.kit").read_text()

    inputs = pipeline_release.apply_workspace_release_inputs(
        root,
        {
            "KIT_SDK_PUBLIC_PUBLISH": "true",
            "KIT_SDK_PUBLIC_RELEASE_VERSION": "110.2.0-rc.1",
            "KIT_KERNEL_VERSION": "110.2.0+master.293874.016f63ce.gl",
        },
        dry_run=True,
    )

    assert inputs.release_version == "110.2.0-rc.1"
    assert (root / "VERSION.md").read_text() == original_version
    assert (root / "tools" / "deps" / "kit-sdk.packman.xml").read_text() == original_packman_xml
    assert (root / "source" / "apps" / "omni.app.editor.base.kit").read_text() == original_base_kit


def test_app_kit_package_version_strips_rc_prerelease():
    assert pipeline_release.app_kit_package_version("110.2.0-dev.4") == "110.2.0-dev.4"
    assert pipeline_release.app_kit_package_version("110.2.0-stage.4") == "110.2.0-stage.4"
    assert pipeline_release.app_kit_package_version("110.2.0-rc.4") == "110.2.0"


def test_next_prerelease_version_preserves_qualifier():
    assert pipeline_release.next_prerelease_version("110.2.0-dev.4") == "110.2.0-dev.5"
    assert pipeline_release.next_prerelease_version("110.1.1-stage.7") == "110.1.1-stage.8"


def test_resolve_publish_context_marks_stale_pipeline_noncanonical(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline_release, "git_remote_branch_commit", lambda root, branch: "newer")

    context = pipeline_release.resolve_publish_context(
        tmp_path,
        {
            "CI_COMMIT_REF_NAME": "release/110.1",
            "CI_COMMIT_SHA": "older",
        },
    )

    assert context.is_canonical is False
    assert context.use_build_metadata_version is True
    assert context.bump_branch_after_publish is True


def test_resolve_publish_context_marks_branch_head_canonical(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline_release, "git_remote_branch_commit", lambda root, branch: "same")

    context = pipeline_release.resolve_publish_context(
        tmp_path,
        {
            "CI_COMMIT_REF_NAME": "release/110.1",
            "CI_COMMIT_SHA": "same",
        },
    )

    assert context.is_canonical is True
    assert context.use_build_metadata_version is False
    assert context.bump_branch_after_publish is True


def test_resolve_publish_context_marks_mr_noncanonical(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline_release, "git_remote_branch_commit", lambda root, branch: "same")

    context = pipeline_release.resolve_publish_context(
        tmp_path,
        {
            "CI_COMMIT_REF_NAME": "release/110.1",
            "CI_COMMIT_SHA": "same",
            "CI_MERGE_REQUEST_IID": "123",
        },
    )

    assert context.is_canonical is False
    assert context.use_build_metadata_version is True
    assert context.bump_branch_after_publish is False


def test_check_release_auth_branch_push_dry_run(monkeypatch, tmp_path):
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-dev.7",
        base_version="110.2.0",
        qualifier="dev",
        number=7,
        kit_kernel_version="110.2.0",
        next_release_version="110.2.0-dev.8",
        bump_branch_after_publish=True,
    )
    context = pipeline_release.PublishContext(
        branch="feature/main",
        current_commit="same",
        remote_commit="same",
        is_canonical=True,
        reason="pipeline is branch HEAD",
    )
    pushes = []
    monkeypatch.setattr(
        pipeline_release,
        "git_push_dry_run",
        lambda root, refspec, push_options=(): pushes.append((refspec, push_options)),
    )

    pipeline_release.check_release_auth(inputs, tmp_path, {"CI_COMMIT_SHA": "same"}, publish_context=context)

    assert pushes == [("HEAD:feature/main", ("ci.skip",))]


def test_check_release_auth_branch_bump_uses_gitlab_api_token(monkeypatch, tmp_path):
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-dev.7",
        base_version="110.2.0",
        qualifier="dev",
        number=7,
        kit_kernel_version="110.2.0",
        next_release_version="110.2.0-dev.8",
        bump_branch_after_publish=True,
    )
    context = pipeline_release.PublishContext(
        branch="feature/main",
        current_commit="same",
        remote_commit="same",
        is_canonical=True,
        reason="pipeline is branch HEAD",
    )
    calls = []

    def fake_gitlab_request(
        method,
        url,
        env,
        data=None,
        json_data=None,
        expected_statuses=(200,),
        include_job_token=True,
    ):
        calls.append((method, url, include_job_token))
        if url.endswith("/projects/42"):
            return {"permissions": {"project_access": {"access_level": 40}}}
        return {}

    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)
    monkeypatch.setattr(
        pipeline_release,
        "git_push_dry_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("git push should not be used")),
    )

    pipeline_release.check_release_auth(
        inputs,
        tmp_path,
        {"CI_PROJECT_ID": "42", "CI_COMMIT_SHA": "same", "DEPENDABOT_GITLAB_TOKEN": "token"},
        publish_context=context,
    )

    assert calls == [
        ("GET", "https://gitlab-master.nvidia.com/api/v4/projects/42", False),
        ("GET", "https://gitlab-master.nvidia.com/api/v4/projects/42/repository/branches/feature%2Fmain", False),
    ]


def test_gitlab_private_token_prefers_project_bot_token_over_dependabot_alias():
    assert pipeline_release._gitlab_private_token_header(
        {
            "DEPENDABOT_GITLAB_TOKEN": "dependabot-token",
            "KIT_SDK_PUBLIC_BOT_TOKEN": "project-token",
        }
    ) == ("PRIVATE-TOKEN", "project-token")


def test_check_release_credentials_validates_branch_and_tag_api(monkeypatch, tmp_path):
    calls = []

    def fake_gitlab_request(
        method,
        url,
        env,
        data=None,
        json_data=None,
        expected_statuses=(200,),
        include_job_token=True,
    ):
        calls.append((method, url, expected_statuses, include_job_token))
        if url.endswith("/projects/42"):
            return {"permissions": {"project_access": {"access_level": 40}}}
        if "/repository/tags/" in url:
            raise RuntimeError("GitLab API GET failed with HTTP 404: {}")
        return {}

    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)

    pipeline_release.check_release_credentials(
        tmp_path,
        {
            "CI_PROJECT_ID": "42",
            "CI_COMMIT_SHA": "abc",
            "KIT_SDK_PUBLIC_BOT_TOKEN": "token",
            "KIT_SDK_PUBLIC_AUTH_CHECK_BRANCH": "feature/main",
        },
    )

    assert calls == [
        ("GET", "https://gitlab-master.nvidia.com/api/v4/projects/42", (200,), False),
        (
            "GET",
            "https://gitlab-master.nvidia.com/api/v4/projects/42/repository/branches/feature%2Fmain",
            (200,),
            False,
        ),
        (
            "GET",
            "https://gitlab-master.nvidia.com/api/v4/projects/42/repository/tags/kit-sdk-public%2Fvcredential-check",
            (200,),
            False,
        ),
    ]


def test_git_push_dry_run_reports_clear_push_auth_failure(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            128,
            cmd,
            output="",
            stderr="remote: GitLab: You are not allowed to push code to protected branches on this project.",
        )

    monkeypatch.setattr(pipeline_release.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        pipeline_release.git_push_dry_run(tmp_path, "HEAD:feature/main", push_options=("ci.skip",))

    message = str(exc_info.value)
    assert "Release auth preflight failed" in message
    assert "next-version bump" in message
    assert "HEAD:feature/main" in message
    assert "git push --dry-run -o ci.skip origin HEAD:feature/main" in message
    assert "protected branches" in message
    assert "DEPENDABOT_GITLAB_TOKEN" in message
    assert "KIT_SDK_PUBLIC_PUSH_NEXT_VERSION=false" in message


def test_bump_branch_version_records_kernel_override(monkeypatch, tmp_path):
    root = make_root(tmp_path, version="110.2.0-dev.7")
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-dev.7",
        base_version="110.2.0",
        qualifier="dev",
        number=7,
        kit_kernel_version="110.2.0+feature.308318.87b254c7.gl",
        next_release_version="110.2.0-dev.8",
        bump_branch_after_publish=True,
    )
    calls = []

    monkeypatch.setattr(pipeline_release, "git_has_release_state_change", lambda root, paths: True)
    monkeypatch.setattr(pipeline_release, "_run_git", lambda root, args: calls.append(args) or [])

    pipeline_release.bump_branch_version_after_publish(
        inputs,
        root,
        {"CI_COMMIT_REF_NAME": "feature/main", "KIT_SDK_PUBLIC_PUSH_NEXT_VERSION": "false"},
    )

    assert (root / "VERSION.md").read_text() == "110.2.0-dev.8\n"
    assert (
        'version="110.2.0+feature.308318.87b254c7.gl.${platform_target_abi}.${config}"'
        in (root / "tools" / "deps" / "kit-sdk.packman.xml").read_text()
    )
    assert 'version = "110.2.0-dev.8"' in (root / "source" / "apps" / "omni.app.editor.base.kit").read_text()
    assert calls == []


def test_bump_branch_version_uses_gitlab_api_token(monkeypatch, tmp_path):
    root = make_root(tmp_path, version="110.2.0-dev.7")
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-dev.7",
        base_version="110.2.0",
        qualifier="dev",
        number=7,
        kit_kernel_version="110.2.0+feature.308318.87b254c7.gl",
        next_release_version="110.2.0-dev.8",
        bump_branch_after_publish=True,
    )
    calls = []

    def encode_file(content, last_commit_id):
        return {
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "encoding": "base64",
            "last_commit_id": last_commit_id,
        }

    remote_files = {
        "VERSION.md": encode_file("110.2.0-dev.7\n", "version-commit"),
        "source/apps/omni.app.editor.base.kit": encode_file(
            (root / "source" / "apps" / "omni.app.editor.base.kit").read_text(), "base-kit-commit"
        ),
        "tools/deps/kit-sdk.packman.xml": encode_file(
            (root / "tools" / "deps" / "kit-sdk.packman.xml").read_text(), "packman-commit"
        ),
    }

    def fake_gitlab_request(
        method,
        url,
        env,
        data=None,
        json_data=None,
        expected_statuses=(200,),
        include_job_token=True,
    ):
        calls.append((method, url, json_data, expected_statuses, include_job_token))
        if method == "GET" and "/repository/files/" in url:
            encoded_path = url.split("/repository/files/", 1)[1].split("?", 1)[0]
            path = pipeline_release.urllib.parse.unquote(encoded_path)
            return remote_files[path]
        return {}

    monkeypatch.setattr(pipeline_release, "git_has_release_state_change", lambda root, paths: True)
    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)
    monkeypatch.setattr(
        pipeline_release,
        "_run_git",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("git push should not be used")),
    )

    pipeline_release.bump_branch_version_after_publish(
        inputs,
        root,
        {
            "CI_PROJECT_ID": "42",
            "CI_COMMIT_REF_NAME": "feature/main",
            "DEPENDABOT_GITLAB_TOKEN": "token",
        },
    )

    assert len(calls) == 4
    method, url, json_data, expected_statuses, include_job_token = calls[-1]
    assert method == "POST"
    assert url == "https://gitlab-master.nvidia.com/api/v4/projects/42/repository/commits"
    assert json_data["branch"] == "feature/main"
    assert json_data["commit_message"] == "chore: Bump kit-sdk-public to 110.2.0-dev.8 [ci skip]"
    assert expected_statuses == (201,)
    assert include_job_token is False
    assert json_data["actions"][0] == {
        "action": "update",
        "file_path": "VERSION.md",
        "content": "110.2.0-dev.8\n",
        "last_commit_id": "version-commit",
    }
    actions_by_path = {action["file_path"]: action for action in json_data["actions"]}
    assert 'version = "110.2.0-dev.8"' in actions_by_path["source/apps/omni.app.editor.base.kit"]["content"]
    assert actions_by_path["source/apps/omni.app.editor.base.kit"]["last_commit_id"] == "base-kit-commit"
    assert actions_by_path[pipeline_release.DEFAULT_PACKMAN_XML]["file_path"] == pipeline_release.DEFAULT_PACKMAN_XML
    assert actions_by_path[pipeline_release.DEFAULT_PACKMAN_XML]["last_commit_id"] == "packman-commit"
    assert (
        "110.2.0+feature.308318.87b254c7.gl.${platform_target_abi}.${config}"
        in actions_by_path[pipeline_release.DEFAULT_PACKMAN_XML]["content"]
    )


def test_bump_branch_version_noops_when_branch_already_advanced(monkeypatch, tmp_path):
    root = make_root(tmp_path, version="110.2.0-stage.14")
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-stage.14",
        base_version="110.2.0",
        qualifier="stage",
        number=14,
        kit_kernel_version=None,
        next_release_version="110.2.0-stage.15",
        bump_branch_after_publish=True,
    )
    calls = []

    def fake_gitlab_request(
        method,
        url,
        env,
        data=None,
        json_data=None,
        expected_statuses=(200,),
        include_job_token=True,
    ):
        calls.append((method, url, json_data))
        assert method == "GET"
        return {
            "content": base64.b64encode(b"110.2.0-stage.15\n").decode("ascii"),
            "encoding": "base64",
            "last_commit_id": "version-commit",
        }

    monkeypatch.setattr(pipeline_release, "git_has_release_state_change", lambda root, paths: True)
    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)

    pipeline_release.bump_branch_version_after_publish(
        inputs,
        root,
        {
            "CI_PROJECT_ID": "42",
            "CI_COMMIT_REF_NAME": "feature/110.2",
            "DEPENDABOT_GITLAB_TOKEN": "token",
        },
    )

    assert len(calls) == 1


def test_bump_branch_version_rejects_unexpected_branch_version(monkeypatch, tmp_path):
    root = make_root(tmp_path, version="110.2.0-stage.14")
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-stage.14",
        base_version="110.2.0",
        qualifier="stage",
        number=14,
        kit_kernel_version=None,
        next_release_version="110.2.0-stage.15",
        bump_branch_after_publish=True,
    )

    def fake_gitlab_request(
        method,
        url,
        env,
        data=None,
        json_data=None,
        expected_statuses=(200,),
        include_job_token=True,
    ):
        assert method == "GET"
        return {
            "content": base64.b64encode(b"110.2.0-stage.12\n").decode("ascii"),
            "encoding": "base64",
            "last_commit_id": "version-commit",
        }

    monkeypatch.setattr(pipeline_release, "git_has_release_state_change", lambda root, paths: True)
    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)

    with pytest.raises(RuntimeError, match="Refusing to bump"):
        pipeline_release.bump_branch_version_after_publish(
            inputs,
            root,
            {
                "CI_PROJECT_ID": "42",
                "CI_COMMIT_REF_NAME": "feature/110.2",
                "DEPENDABOT_GITLAB_TOKEN": "token",
            },
        )


def test_check_release_auth_rc_checks_gitlab_tag(monkeypatch, tmp_path):
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-rc.4",
        base_version="110.2.0",
        qualifier="rc",
        number=4,
        kit_kernel_version="110.2.0",
        release_tag="kit-sdk-public/v110.2.0-rc.4",
        record_release_tag=True,
    )
    calls = []

    def fake_gitlab_request(method, url, env, data=None, expected_statuses=(200,)):
        calls.append((method, url, data, expected_statuses))
        if method == "GET" and "/repository/tags/" in url:
            raise RuntimeError("GitLab API GET failed with HTTP 404: {}")
        return {}

    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)

    pipeline_release.check_release_auth(
        inputs,
        tmp_path,
        {"CI_PROJECT_ID": "42", "CI_COMMIT_SHA": "abc", "KIT_SDK_PUBLIC_API_TOKEN": "token"},
    )

    assert [call[0] for call in calls] == ["GET", "GET"]
    assert calls[0][1].endswith("/projects/42")
    assert "/repository/tags/kit-sdk-public%2Fv110.2.0-rc.4" in calls[1][1]


def test_check_release_auth_rc_rejects_conflicting_existing_tag(monkeypatch, tmp_path):
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-rc.4",
        base_version="110.2.0",
        qualifier="rc",
        number=4,
        kit_kernel_version="110.2.0",
        release_tag="kit-sdk-public/v110.2.0-rc.4",
        record_release_tag=True,
    )

    def fake_gitlab_request(method, url, env, data=None, expected_statuses=(200,)):
        if method == "GET" and "/repository/tags/" in url:
            return {"target": "other"}
        return {}

    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)

    with pytest.raises(RuntimeError, match="already exists"):
        pipeline_release.check_release_auth(
            inputs,
            tmp_path,
            {"CI_PROJECT_ID": "42", "CI_COMMIT_SHA": "abc", "KIT_SDK_PUBLIC_API_TOKEN": "token"},
        )


def test_check_release_auth_write_probe_creates_and_deletes_temp_tag(monkeypatch, tmp_path):
    inputs = pipeline_release.ReleaseInputs(
        release_version="110.2.0-rc.4",
        base_version="110.2.0",
        qualifier="rc",
        number=4,
        kit_kernel_version="110.2.0",
        release_tag="kit-sdk-public/v110.2.0-rc.4",
        record_release_tag=True,
    )
    calls = []

    def fake_gitlab_request(method, url, env, data=None, expected_statuses=(200,)):
        calls.append((method, url, data, expected_statuses))
        if method == "GET" and "/repository/tags/" in url:
            raise RuntimeError("GitLab API GET failed with HTTP 404: {}")
        return {}

    monkeypatch.setattr(pipeline_release, "_gitlab_request", fake_gitlab_request)

    pipeline_release.check_release_auth(
        inputs,
        tmp_path,
        {
            "CI_PROJECT_ID": "42",
            "CI_COMMIT_SHA": "abc",
            "CI_PIPELINE_ID": "123",
            "CI_JOB_ID": "456",
            "KIT_SDK_PUBLIC_API_TOKEN": "token",
        },
        write_probe=True,
    )

    assert [call[0] for call in calls] == ["GET", "GET", "POST", "DELETE"]
    assert calls[2][2]["tag_name"] == "kit-sdk-public/v110.2.0-auth-check.123.456"
    assert calls[2][2]["ref"] == "abc"
