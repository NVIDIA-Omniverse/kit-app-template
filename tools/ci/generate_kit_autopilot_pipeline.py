# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
"""Generate the child GitLab pipeline for Kit Autopilot handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

DEFAULT_CHILD_PIPELINE = ".gitlab/child-pipelines/kit-autopilot.yml"


def yaml_quote(value: Any) -> str:
    """Return a GitLab-safe single-quoted YAML scalar."""
    if value is None or value == "":
        return "''"
    text = str(value).replace("'", "''")
    return f"'{text}'"


def _require_env(env: Mapping[str, Any], key: str) -> str:
    value = env.get(key)
    if value is None or value == "":
        raise SystemExit(f"missing required environment variable: {key}")
    return str(value)


def _build_variables(env: Mapping[str, Any]) -> dict[str, str]:
    version = str(env.get("PUBLISH_NGC_VERSION", ""))
    version_base = str(env.get("PUBLISH_NGC_VERSION_BASE", ""))
    qualifier = str(env.get("PUBLISH_NGC_VERSION_QUALIFIER", ""))
    version_number = str(env.get("PUBLISH_NGC_VERSION_NUMBER", ""))
    kit_kernel_version = str(env.get("KIT_KERNEL_VERSION", ""))
    release_ref = str(env.get("CI_COMMIT_REF_NAME", ""))
    release_sha = str(env.get("CI_COMMIT_SHA", ""))
    pipeline_url = str(env.get("CI_PIPELINE_URL", ""))
    trigger_login = str(env.get("GITLAB_USER_LOGIN", ""))
    commit_title = str(env.get("CI_COMMIT_TITLE", ""))
    ngc_org = str(env.get("PUBLISH_NGC_ORG", ""))
    ngc_team = str(env.get("PUBLISH_NGC_TEAM", ""))

    return {
        "KIT_VERSION": version,
        "KIT_KERNEL_VERSION": kit_kernel_version,
        "KIT_SDK_PUBLIC_NGC_VERSION": version,
        "KIT_SDK_PUBLIC_VERSION_QUALIFIER": qualifier,
        "KIT_SDK_PUBLIC_KIT_KERNEL_VERSION": kit_kernel_version,
        "KIT_SDK_PUBLIC_NGC_ORG": ngc_org,
        "KIT_SDK_PUBLIC_NGC_TEAM": ngc_team,
        "KIT_SDK_PUBLIC_SHA": release_sha,
        "KIT_SDK_PUBLIC_REF": release_ref,
        "KIT_SDK_PUBLIC_PIPELINE_URL": pipeline_url,
        "KIT_SDK_PUBLIC_TRIGGERED_BY_LOGIN": trigger_login,
        "KIT_SDK_PUBLIC_COMMIT_TITLE": commit_title,
        "NGC_ORG": ngc_org,
        "NGC_TEAM": ngc_team,
        "PRODUCTION_RUN": "true",
        "KIT_SDK_PUBLIC_VERSION_BASE": version_base,
        "KIT_SDK_PUBLIC_VERSION_NUMBER": version_number,
    }


def generate_pipeline(env: Mapping[str, Any], root: str | Path) -> Path:
    """Generate the child GitLab pipeline and return the created path."""
    qualifier = str(env.get("PUBLISH_NGC_VERSION_QUALIFIER", "")).strip()
    if qualifier == "":
        raise SystemExit("missing required environment variable: PUBLISH_NGC_VERSION_QUALIFIER")
    if qualifier not in {"dev", "stage", "rc"}:
        raise SystemExit(f"unknown release qualifier: {qualifier}")

    root_path = Path(root)
    child = root_path / DEFAULT_CHILD_PIPELINE
    child.parent.mkdir(parents=True, exist_ok=True)

    if qualifier == "dev":
        version = str(env.get("PUBLISH_NGC_VERSION", ""))
        text = (
            "stages:\n"
            "  - qa-automation\n\n"
            "include:\n"
            "  - project: omniverse/devplat/gitlab/templates/runners\n\n"
            "skip-kit-autopilot-dev:\n"
            "  stage: qa-automation\n"
            "  extends:\n"
            "    - .omni_nvks_micro_runner\n"
            "  script:\n"
            f'    - echo "Skipping kit-autopilot for dev publish {version}"\n'
        )
        child.write_text(text, encoding="utf-8")
        return child

    trigger_project = "omniverse/qa/kit-autopilot"
    trigger_variables = _build_variables(env)
    variable_lines = []
    for key, value in trigger_variables.items():
        variable_lines.append(f"    {key}: {yaml_quote(value)}")

    text = (
        "stages:\n"
        "  - qa-automation\n\n"
        "trigger-kit-autopilot:\n"
        "  stage: qa-automation\n"
        "  trigger:\n"
        "    project: omniverse/qa/kit-autopilot\n"
        "    branch: main\n"
        "    strategy: depend\n"
        "  variables:\n"
        + "\n".join(variable_lines)
        + "\n"
    )
    child.write_text(text, encoding="utf-8")
    return child
