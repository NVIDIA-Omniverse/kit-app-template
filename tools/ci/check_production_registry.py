import json
import os
import sys
from pathlib import Path

import omni.repo.ci
from omni.repo.man import resolve_tokens

_ROOT = Path(resolve_tokens("${root}"))
_PLATFORM = "windows" if sys.platform == "win32" else "linux"
_KIT_CORE_JSON_PATH = str(_ROOT / f"_build/{_PLATFORM}-x86_64/release/kit/kernel/config/kit-core.json")
_REPO_TOML_PATH = str(_ROOT / "repo.toml")


def get_kit_registry_dict() -> dict:
    # Check if the path exists, display error otherwise.
    if not os.path.exists(_KIT_CORE_JSON_PATH):
        print("kit-core.json file was not found. Can not evaluate assigned production registry.")
        sys.exit(1)

    with open(_KIT_CORE_JSON_PATH, "r") as f:
        data = json.load(f)
        return data["exts"]["omni.kit.registry.nucleus"]["registries"]


def get_repo_registry_dict() -> dict:
    import tomli

    # Check if the repo toml exists, display error otherwise.
    if not os.path.exists(_REPO_TOML_PATH):
        print("Could not locate repo.toml. Can not evaluate the assigned production registry.")
        sys.exit(1)

    with open(_REPO_TOML_PATH, "rb") as f:
        data = tomli.load(f)
        return data["repo_precache_exts"]["registries"]


def compare_registry_data(kit_registry, repo_registry) -> bool:
    missing_urls = []
    # Get all kit urls
    kit_urls = [k["url"] for k in kit_registry]
    repo_urls = [r["url"] for r in repo_registry if r["name"] != "kit/community"]

    for url in repo_urls:
        if url not in kit_urls:
            missing_urls.append(url)

    if has_missing := len(missing_urls) > 0:
        for url in missing_urls:
            print(f"{url} is missing from Kit's regsitry urls.")

    return has_missing


# Fetch Kit and generate the project.
# source/apps is required before running `repo build -r -g`
source_apps_path = _ROOT / "source/apps"
os.makedirs(str(source_apps_path), exist_ok=True)
omni.repo.ci.launch(["${root}/repo${shell_ext}", "build", "-r", "-g"])

kit_registry = get_kit_registry_dict()
repo_registry = get_repo_registry_dict()
has_missing_registry_entries: bool = compare_registry_data(kit_registry, repo_registry)

sys.exit(has_missing_registry_entries)
