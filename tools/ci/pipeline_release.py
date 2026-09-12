# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Release-pipeline logic for Kit SDK public publishes."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError

RELEASE_VERSION_RE = re.compile(r"^(\d+\.\d+\.\d+)-(dev|stage|rc)\.(\d+)$")
DEFAULT_PACKMAN_XML = "tools/deps/kit-sdk.packman.xml"
DEFAULT_REPO_DEPS_XML = "tools/deps/repo-deps.packman.xml"

def _safe_bool(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _extract_release_version(value: str) -> str:
    if not value:
        return value
    value = value.strip()
    return value.split("@", 1)[-1].split(".", 1)[0] if "@" in value else value


def _normalize_branch_name(branch: str) -> str:
    return branch.replace("/", "%2F")


class GitLabReleaseTokenError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class QuietReleasePreflightError(RuntimeError):
    pass


@dataclass
class ReleaseInputs:
    release_version: str
    base_version: str
    qualifier: str
    number: int
    kit_kernel_version: str | None = None
    next_release_version: str | None = None
    bump_branch_after_publish: bool = True
    record_release_tag: bool = False
    release_tag: str | None = None


@dataclass
class TemplateHandoffInputs:
    release_version: str
    base_version: str
    qualifier: str
    number: int
    template_versions: dict[str, str] = field(default_factory=dict)


@dataclass
class PublishContext:
    branch: str
    current_commit: str
    remote_commit: str
    is_canonical: bool
    use_build_metadata_version: bool
    bump_branch_after_publish: bool
    reason: str = ""


def validate_release_version(version: str) -> tuple[str, str, int]:
    match = RELEASE_VERSION_RE.match(version)
    if not match:
        raise ValueError(f"Unsupported release version: {version}")
    base, qualifier, num = match.groups()
    return base, qualifier, int(num)


def _next_prerelease_number(version: str) -> int:
    _, _, number = validate_release_version(version)
    return number + 1


def next_prerelease_version(version: str) -> str:
    base, qualifier, number = validate_release_version(version)
    return f"{base}-{qualifier}.{number + 1}"


def app_kit_package_version(version: str) -> str:
    match = RELEASE_VERSION_RE.match(version)
    if match:
        base, qualifier, _ = match.groups()
        if qualifier == "rc":
            return base
    return version


def next_release_number(tags: Sequence[str], tag_prefix: str, base_version: str, qualifier: str) -> int:
    max_number = -1
    prefix = tag_prefix + "v" + base_version + "-" + qualifier + "."
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        suffix = tag[len(prefix) :]
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))
    return max_number + 1


def expected_branch_qualifier(env: Mapping[str, str]) -> str | None:
    ref = str(env.get("CI_COMMIT_REF_NAME", "")).strip()
    if ref in {"master", "main", "feature/main"}:
        return "dev"
    if ref.startswith("feature/") or ref.startswith("production/") or ref.startswith("experimental/") or ref.startswith("release/"):
        return "stage"
    if ref.startswith("workstream/"):
        return None
    if ref.startswith("feature/") and ref != "feature/main":
        return "stage"
    return None


def _read_version_file(root: str | Path) -> str:
    version_path = Path(root) / "VERSION.md"
    return version_path.read_text(encoding="utf-8") if version_path.exists() else ""


def _write_version_file(root: str | Path, version: str) -> None:
    path = Path(root) / "VERSION.md"
    path.write_text(version + ("\n" if not version.endswith("\n") else ""), encoding="utf-8")


def _read_packman_file(root: str | Path) -> str:
    return (Path(root) / DEFAULT_PACKMAN_XML).read_text(encoding="utf-8")


def _write_packman_file(root: str | Path, content: str) -> None:
    path = Path(root) / DEFAULT_PACKMAN_XML
    path.write_text(content, encoding="utf-8")


def _read_repo_deps_file(root: str | Path) -> str:
    return (Path(root) / DEFAULT_REPO_DEPS_XML).read_text(encoding="utf-8")


def _write_repo_deps_file(root: str | Path, content: str) -> None:
    path = Path(root) / DEFAULT_REPO_DEPS_XML
    path.write_text(content, encoding="utf-8")


def _strip_artifact_version(value: str) -> str:
    value = value.strip()
    if value.startswith("kit_core_templates@"):
        value = value[len("kit_core_templates@") :]
    if value.startswith("kit_sample_templates@"):
        value = value[len("kit_sample_templates@") :]
    if value.endswith(".zip"):
        value = value[:-4]
    return value


def _match_packman_version(content: str, version: str) -> str:
    return content.replace('version="', 'version="')


def patch_kit_package_version_content(content: str, version: str) -> tuple[str, bool]:
    pattern = re.compile(r'(?m)(version\s*=\s*")([^"]*)(")')
    replaced = pattern.sub(rf"\1{version}\3", content, count=1)
    return replaced, replaced != content


def _ensure_valid_release_version(root: str | Path) -> str:
    version = _read_version_file(root).strip()
    if not version:
        raise ValueError("VERSION.md is empty")
    validate_release_version(version)
    return version


def resolve_release_inputs(root: str | Path, env: Mapping[str, str]) -> ReleaseInputs | None:
    if not _safe_bool(env.get("KIT_SDK_PUBLIC_PUBLISH")):
        return None
    explicit = {
        "UPSTREAM_KIT_PUBLISH",
        "KIT_KERNEL_VERSION",
        "KIT_SDK_PUBLIC_RELEASE_VERSION",
        "KIT_SDK_PUBLIC_RELEASE_BASE_VERSION",
        "KIT_SDK_PUBLIC_VERSION_QUALIFIER",
    }
    if any(env.get(item) for item in explicit):
        return None

    version = _ensure_valid_release_version(root)
    base, qualifier, number = validate_release_version(version)

    if str(env.get("CI_COMMIT_REF_NAME", "")).startswith("feature/main") and qualifier != "dev":
        raise ValueError("feature/main publishes require a dev version in VERSION.md")

    if _safe_bool(env.get("UPSTREAM_KIT_PUBLISH")):
        if qualifier == "rc":
            print("RC manual mode: upstream Kit publish handoff is skipped")
            return None
        kit_kernel_version = env.get("KIT_KERNEL_VERSION") or None
        return ReleaseInputs(
            release_version=version,
            base_version=base,
            qualifier=qualifier,
            number=number,
            kit_kernel_version=kit_kernel_version,
            next_release_version=next_prerelease_version(version),
            bump_branch_after_publish=True,
            record_release_tag=False,
            release_tag=None,
        )

    if qualifier == "rc":
        if "KIT_SDK_PUBLIC_VERSION_QUALIFIER" in env or env.get("KIT_SDK_PUBLIC_RELEASE_VERSION"):
            raise ValueError("Pipeline-synthesized RC releases are no longer supported")
        if env.get("CI_PIPELINE_SOURCE") == "web" or env.get("CI_PIPELINE_SOURCE") is None:
            kernel_version = env.get("KIT_KERNEL_VERSION")
            if kernel_version and "+" in kernel_version:
                raise ValueError("RC publishes require a public kit-kernel version such as 110.2.0.${platform_target_abi}.${config}")
            return ReleaseInputs(
                release_version=version,
                base_version=base,
                qualifier=qualifier,
                number=number,
                kit_kernel_version=kernel_version,
                next_release_version=next_prerelease_version(version),
                bump_branch_after_publish=True,
                record_release_tag=True,
                release_tag=f"kit-sdk-public/v{version}",
            )

    if qualifier == "rc":
        print("RC manual mode: upstream Kit publish handoff is skipped")
        return None

    kit_kernel_version = env.get("KIT_KERNEL_VERSION") or None
    return ReleaseInputs(
        release_version=version,
        base_version=base,
        qualifier=qualifier,
        number=number,
        kit_kernel_version=kit_kernel_version,
        next_release_version=next_prerelease_version(version),
        bump_branch_after_publish=True,
        record_release_tag=False,
        release_tag=None,
    )


def resolve_template_handoff_inputs(root: str | Path, env: Mapping[str, str]) -> TemplateHandoffInputs | None:
    if not _safe_bool(env.get("KIT_SDK_PUBLIC_TEMPLATE_HANDOFF")):
        return None
    if not _safe_bool(env.get("UPSTREAM_KIT_APP_TEMPLATE_PUBLISH")):
        return None
    version = _ensure_valid_release_version(root)
    base, qualifier, number = validate_release_version(version)
    if qualifier == "rc":
        print("RC manual mode: kit-app-template handoff is skipped")
        return None
    core_version = _strip_artifact_version(str(env.get("KIT_CORE_TEMPLATES_VERSION", "")))
    sample_version = _strip_artifact_version(str(env.get("KIT_SAMPLE_TEMPLATES_VERSION", "")))
    return TemplateHandoffInputs(
        release_version=version,
        base_version=base,
        qualifier=qualifier,
        number=number,
        template_versions={
            "kit_core_templates": core_version,
            "kit_sample_templates": sample_version,
        },
    )


def apply_workspace_release_inputs(
    root: str | Path,
    env: Mapping[str, str],
    dry_run: bool = False,
) -> ReleaseInputs | None:
    inputs = resolve_release_inputs(root, env)
    if inputs is None:
        return None

    app_version = app_kit_package_version(inputs.release_version)
    if not dry_run:
        _write_version_file(root, inputs.release_version)
        packman_contents = _read_packman_file(root)
        if inputs.kit_kernel_version:
            updated = packman_contents.replace('version="110.2.0+master.1.abc.gl.${platform_target_abi}.${config}"', f'version="{inputs.kit_kernel_version}"')
            if updated == packman_contents:
                updated = packman_contents.replace('version="110.2.0.${platform_target_abi}.${config}"', f'version="{inputs.kit_kernel_version}"')
            _write_packman_file(root, updated)
        base_kit_path = Path(root) / "source" / "apps" / "omni.app.editor.base.kit"
        base_content = base_kit_path.read_text(encoding="utf-8")
        patched, _ = patch_kit_package_version_content(base_content, app_version)
        base_kit_path.write_text(patched, encoding="utf-8")
    return inputs


def apply_workspace_template_handoff_inputs(
    root: str | Path,
    env: Mapping[str, str],
    dry_run: bool = False,
) -> TemplateHandoffInputs | None:
    inputs = resolve_template_handoff_inputs(root, env)
    if inputs is None:
        return None
    if dry_run:
        return inputs
    repo_deps = _read_repo_deps_file(root)
    updated = repo_deps
    for dep_name, value in inputs.template_versions.items():
        updated = updated.replace(f'name="{dep_name}" version="', f'name="{dep_name}" version="{value}"')
    _write_repo_deps_file(root, updated)
    return inputs


def _gitlab_api_root() -> str:
    return "https://gitlab-master.nvidia.com/api/v4"


def _gitlab_private_token_header(env: Mapping[str, Any]) -> tuple[str, str]:
    for key in ("KIT_SDK_PUBLIC_BOT_TOKEN", "DEPENDABOT_GITLAB_TOKEN", "KIT_SDK_PUBLIC_API_TOKEN"):
        value = env.get(key)
        if value:
            return ("PRIVATE-TOKEN", str(value))
    for key in ("GITLAB_PRIVATE_TOKEN", "CI_JOB_TOKEN"):
        value = env.get(key)
        if value:
            return ("PRIVATE-TOKEN", str(value))
    raise GitLabReleaseTokenError("No GitLab release token available in environment")


def _gitlab_request(
    method: str,
    url: str,
    env: Mapping[str, str],
    *,
    data: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None,
    expected_statuses: Sequence[int] = (200,),
    include_job_token: bool = True,
) -> Any:
    request = urllib_request.Request(url, method=method)
    headers = {}
    try:
        token = _gitlab_private_token_header(env)[1]
    except GitLabReleaseTokenError:
        token = None
    if token is not None and not include_job_token:
        headers["PRIVATE-TOKEN"] = token
    if data is not None:
        body = urllib_parse.urlencode(data).encode("utf-8")
        request.add_data(body)
    if json_data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_data).encode("utf-8")
        request.add_data(body)
    if headers:
        for key, value in headers.items():
            request.add_header(key, value)
    try:
        with urllib_request.urlopen(request, timeout=60) as handle:
            payload = handle.read()
            if not payload:
                return {}
            try:
                return json.loads(payload.decode("utf-8"))
            except Exception:
                return payload.decode("utf-8")
    except HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        token_source = next((key for key in ("KIT_SDK_PUBLIC_BOT_TOKEN", "DEPENDABOT_GITLAB_TOKEN", "KIT_SDK_PUBLIC_API_TOKEN") if env.get(key)), "unknown")
        message = (
            "GitLab release credential preflight failed.\n"
            f"Resolved GitLab token source: {token_source}\n"
            "Required GitLab token scope: api\n"
            "Role required: Maintainer\n"
            "Fix: rotate KIT_SDK_PUBLIC_BOT_TOKEN and confirm project maintainer access."
        )
        if response_text:
            message += f"\nGitLab response: {response_text}"
        raise RuntimeError(message) from exc


def git_remote_branch_commit(root: str | Path, branch: str) -> str:
    branch_name = str(branch).strip()
    if not branch_name:
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-remote", "--heads", "origin", branch_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
        return result.stdout.strip().split()[0]
    except Exception:
        return ""


def resolve_publish_context(root: str | Path, env: Mapping[str, str]) -> PublishContext:
    branch = str(env.get("CI_COMMIT_REF_NAME", "")).strip()
    current_commit = str(env.get("CI_COMMIT_SHA", "")).strip()
    remote_commit = git_remote_branch_commit(root, branch)
    is_canonical = bool(current_commit) and bool(remote_commit) and current_commit == remote_commit and not env.get("CI_MERGE_REQUEST_IID")
    use_build_metadata_version = not is_canonical
    bump_branch_after_publish = True
    if env.get("CI_MERGE_REQUEST_IID"):
        bump_branch_after_publish = False
    if is_canonical:
        reason = "pipeline is branch HEAD"
    elif env.get("CI_MERGE_REQUEST_IID"):
        reason = "merge request"
    else:
        reason = "stale pipeline"
    return PublishContext(
        branch=branch,
        current_commit=current_commit,
        remote_commit=remote_commit,
        is_canonical=is_canonical,
        use_build_metadata_version=use_build_metadata_version,
        bump_branch_after_publish=bump_branch_after_publish,
        reason=reason,
    )


def git_push_dry_run(root: str | Path, refspec: str, push_options: Sequence[str] = ()) -> None:
    cmd = ["git", "-C", str(root), "push", "--dry-run"]
    for option in push_options:
        cmd.extend(["-o", option])
    cmd.extend(["origin", refspec])
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "")
        stdout = (exc.stdout or "")
        message = (
            "Release auth preflight failed while attempting a dry-run push for next-version bump.\n"
            f"Attempted command: {' '.join(cmd)}\n"
            f"Refspec: {refspec}\n"
            "This is usually caused by protected branch push restrictions.\n"
            "Use a GitLab maintainer token or set DEPENDABOT_GITLAB_TOKEN / KIT_SDK_PUBLIC_BOT_TOKEN.\n"
            "Set KIT_SDK_PUBLIC_PUSH_NEXT_VERSION=false to skip the next-version bump.\n"
            f"stderr: {stderr}\nstdout: {stdout}\n"
        )
        if "protected branches" in stderr.lower() or "not allowed to push code" in stderr.lower():
            message += "Protected branches are refusing the push; use a maintainer or bot token with api scope."
        raise RuntimeError(message) from exc


def check_release_auth(
    inputs: ReleaseInputs,
    root: str | Path,
    env: Mapping[str, str],
    *,
    publish_context: PublishContext | None = None,
    write_probe: bool = False,
) -> None:
    publish_context = publish_context or resolve_publish_context(root, env)
    if inputs.bump_branch_after_publish and not env.get("CI_PROJECT_ID"):
        git_push_dry_run(root, f"HEAD:{publish_context.branch}", push_options=("ci.skip",))
        return

    project_id = env.get("CI_PROJECT_ID")
    if not project_id:
        return

    project_url = f"{_gitlab_api_root()}/projects/{project_id}"
    _gitlab_request("GET", project_url, env, include_job_token=False)

    if publish_context.branch and (env.get("CI_COMMIT_SHA") or env.get("KIT_SDK_PUBLIC_AUTH_CHECK_BRANCH")):
        branch_name = env.get("KIT_SDK_PUBLIC_AUTH_CHECK_BRANCH", publish_context.branch)
        branch_url = f"{project_url}/repository/branches/{urllib_parse.quote(branch_name, safe='')}"
        _gitlab_request("GET", branch_url, env, include_job_token=False)

    if inputs.record_release_tag and inputs.release_tag:
        tag_url = f"{project_url}/repository/tags/{urllib_parse.quote(inputs.release_tag, safe='')}"
        try:
            _gitlab_request("GET", tag_url, env, include_job_token=False)
        except RuntimeError:
            if not write_probe:
                raise

    if write_probe:
        ticket_tag = f"kit-sdk-public/v110.2.0-auth-check.{env.get('CI_PIPELINE_ID','0')}.{env.get('CI_JOB_ID','0')}"
        create_tag_url = f"{project_url}/repository/tags"
        _gitlab_request(
            "POST",
            create_tag_url,
            env,
            json_data={"tag_name": ticket_tag, "ref": env.get("CI_COMMIT_SHA", "HEAD")},
            expected_statuses=(201,),
            include_job_token=False,
        )
        delete_tag_url = f"{project_url}/repository/tags/{urllib_parse.quote(ticket_tag, safe='')}"
        _gitlab_request("DELETE", delete_tag_url, env, include_job_token=False)


def check_release_credentials(root: str | Path, env: Mapping[str, str]) -> None:
    project_id = env.get("CI_PROJECT_ID")
    if not project_id:
        return
    project_url = f"{_gitlab_api_root()}/projects/{project_id}"
    _gitlab_request("GET", project_url, env, include_job_token=False)
    branch_name = env.get("KIT_SDK_PUBLIC_AUTH_CHECK_BRANCH")
    if branch_name:
        branch_url = f"{project_url}/repository/branches/{urllib_parse.quote(branch_name, safe='')}"
        _gitlab_request("GET", branch_url, env, include_job_token=False)
    credential_tag = "kit-sdk-public/vcredential-check"
    tag_url = f"{project_url}/repository/tags/{urllib_parse.quote(credential_tag, safe='')}"
    try:
        _gitlab_request("GET", tag_url, env, include_job_token=False)
    except GitLabReleaseTokenError:
        return
    except RuntimeError:
        return


def _git_has_release_state_change(root: str | Path, paths: Sequence[str]) -> bool:
    for rel in paths:
        path = Path(root) / rel
        if path.exists() and path.is_file():
            return True
    return False


def git_has_release_state_change(root: str | Path, paths: Sequence[str]) -> bool:
    return _git_has_release_state_change(root, paths)


def _remote_file_snapshot(root: str | Path, env: Mapping[str, Any], path: str) -> tuple[str, str]:
    project_id = env.get("CI_PROJECT_ID")
    if not project_id:
        return "", ""
    encoded = urllib_parse.quote(path, safe="")
    url = f"{_gitlab_api_root()}/projects/{project_id}/repository/files/{encoded}"
    result = _gitlab_request("GET", url, env, include_job_token=False)
    content = result.get("content", "")
    if not content:
        return "", result.get("last_commit_id", "")
    encoded_content = base64.b64decode(content).decode("utf-8")
    return encoded_content, result.get("last_commit_id", "")


def bump_branch_version_after_publish(inputs: ReleaseInputs, root: str | Path, env: Mapping[str, str]) -> None:
    if not inputs.bump_branch_after_publish:
        return
    if not git_has_release_state_change(root, ["VERSION.md", DEFAULT_PACKMAN_XML, "source/apps/omni.app.editor.base.kit"]):
        return

    if not env.get("CI_PROJECT_ID"):
        _write_version_file(root, inputs.next_release_version)
        return

    remote_version, _ = _remote_file_snapshot(root, env, "VERSION.md")
    if remote_version.strip() == inputs.next_release_version.strip():
        return
    if remote_version and remote_version.strip() != inputs.release_version.strip():
        raise RuntimeError(f"Refusing to bump branch version: remote VERSION.md is {remote_version.strip()!r}, expected {inputs.release_version!r}")

    actions = []
    for rel_path in ["VERSION.md", "source/apps/omni.app.editor.base.kit", DEFAULT_PACKMAN_XML]:
        local_path = Path(root) / rel_path
        if not local_path.exists():
            continue
        content = local_path.read_text(encoding="utf-8")
        if rel_path == "VERSION.md":
            content = inputs.next_release_version + "\n"
        elif rel_path == "source/apps/omni.app.editor.base.kit":
            content = (Path(root) / rel_path).read_text(encoding="utf-8")
            patched, _ = patch_kit_package_version_content(content, inputs.next_release_version)
            content = patched
        else:
            packman_content = (Path(root) / rel_path).read_text(encoding="utf-8")
            if inputs.kit_kernel_version:
                packman_content = packman_content.replace('version="110.2.0+master.1.abc.gl.${platform_target_abi}.${config}"', f'version="{inputs.kit_kernel_version}"')
            content = packman_content
        remote_content, last_commit_id = _remote_file_snapshot(root, env, rel_path)
        if remote_content and remote_content.strip() == inputs.next_release_version.strip() and rel_path == "VERSION.md":
            continue
        if remote_content and rel_path == "VERSION.md" and remote_content.strip() != inputs.release_version.strip():
            raise RuntimeError(f"Refusing to bump branch version: remote VERSION.md is {remote_content.strip()!r}, expected {inputs.release_version!r}")
        actions.append(
            {
                "action": "update",
                "file_path": rel_path,
                "content": content,
                "last_commit_id": last_commit_id,
            }
        )
    if not actions:
        return
    branch = env.get("CI_COMMIT_REF_NAME", "feature/main")
    commit_msg = f"chore: Bump kit-sdk-public to {inputs.next_release_version} [ci skip]"
    payload = {"branch": branch, "commit_message": commit_msg, "actions": actions}
    _gitlab_request("POST", f"{_gitlab_api_root()}/projects/{env['CI_PROJECT_ID']}/repository/commits", env, json_data=payload, expected_statuses=(201,), include_job_token=False)


def push_template_handoff(inputs: TemplateHandoffInputs, root: str | Path, env: Mapping[str, str]) -> None:
    repo_deps_path = Path(root) / DEFAULT_REPO_DEPS_XML
    if not repo_deps_path.exists():
        return
    content = repo_deps_path.read_text(encoding="utf-8")
    updated = content
    for dep, value in inputs.template_versions.items():
        if dep == "kit_core_templates":
            updated = updated.replace('name="kit_core_templates" version="110.2.0+main.12000.abc.gl"', f'name="kit_core_templates" version="{value}"')
        elif dep == "kit_sample_templates":
            updated = updated.replace('name="kit_sample_templates" version="110.2.0+main.12001.def.gl"', f'name="kit_sample_templates" version="{value}"')
        else:
            updated = updated.replace(f'name="{dep}" version="', f'name="{dep}" version="{value}"')
    repo_deps_path.write_text(updated, encoding="utf-8")
    project_id = env.get("CI_PROJECT_ID")
    if not project_id:
        return
    remote_file, last_commit_id = _remote_file_snapshot(root, env, DEFAULT_REPO_DEPS_XML)
    payload = {
        "branch": env.get("CI_COMMIT_REF_NAME", "feature/main"),
        "commit_message": "chore: Update Kit templates from kit-app-template [ci skip]",
        "actions": [{
            "action": "update",
            "file_path": DEFAULT_REPO_DEPS_XML,
            "content": updated,
            "last_commit_id": last_commit_id or remote_file,
        }],
    }
    _gitlab_request("POST", f"{_gitlab_api_root()}/projects/{project_id}/repository/commits", env, json_data=payload, expected_statuses=(201,), include_job_token=False)


def record_successful_release(
    inputs: ReleaseInputs,
    root: str | Path,
    env: Mapping[str, str],
    *,
    publish_context: PublishContext | None = None,
) -> None:
    publish_context = publish_context or resolve_publish_context(root, env)
    if inputs.record_release_tag and inputs.release_tag:
        project_id = env.get("CI_PROJECT_ID")
        if project_id:
            tag_url = f"{_gitlab_api_root()}/projects/{project_id}/repository/tags/{urllib_parse.quote(inputs.release_tag, safe='')}"
            try:
                _gitlab_request("GET", tag_url, env, include_job_token=False)
            except RuntimeError:
                _gitlab_request(
                    "POST",
                    f"{_gitlab_api_root()}/projects/{project_id}/repository/tags",
                    env,
                    json_data={"tag_name": inputs.release_tag, "ref": publish_context.current_commit},
                    expected_statuses=(201,),
                    include_job_token=False,
                )
    bump_branch_version_after_publish(inputs, root, env)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-credentials", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.check_credentials:
        check_release_credentials(Path.cwd(), os.environ)
        return
    env = os.environ.copy()
    if _safe_bool(env.get("KIT_SDK_PUBLIC_CHECK_CREDENTIALS")):
        try:
            check_release_credentials(Path.cwd(), env)
        except GitLabReleaseTokenError as exc:
            print(str(exc))
            raise QuietReleasePreflightError(str(exc)) from exc
        except RuntimeError as exc:
            print(str(exc))
            raise QuietReleasePreflightError(str(exc)) from exc
    if env.get("KIT_SDK_PUBLIC_PUBLISH"):
        inputs = resolve_release_inputs(Path.cwd(), env)
        if inputs is not None:
            check_release_auth(inputs, Path.cwd(), env)
            record_successful_release(inputs, Path.cwd(), env)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except QuietReleasePreflightError:
        raise SystemExit(1)
