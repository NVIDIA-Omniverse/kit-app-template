"""
Tool to build a Docker container for a specified K-A-T project.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from time import strftime
from zipfile import ZIP_DEFLATED, ZipFile

# Import kit artifact helper
sys.path.insert(0, str(Path(__file__).parent))
import kit_artifact

# Setup kit from artifact if running from kit CI
kit_artifact.setup_kit_from_artifact()


SHELL_EXT = "sh" if platform.system() == "Linux" else "bat"
UNDERLINE = "-" * 80
DISPLAY_NAME_MAP = {
    "usd_composer": "USD Composer",
    "usd_explorer": "USD Explorer",
    "usd_viewer": "USD Viewer",
}
KIT_GITLAB_PROJECT_ID = 6510
GITLAB_API_URL = "https://gitlab-master.nvidia.com/api/v4"
BUILD_FOR_OVC2 = os.getenv("OVC2")


def _generate_playback_file(template_name: str) -> None:
    """Generates a PLAYBACK file with dynamic content based on the template name and OVC2 flag."""

    playback_template_path = Path("tools/ci/PLAYBACK.template")
    playback_output_path = Path("tools/ci/PLAYBACK")

    if not playback_template_path.exists():
        print(f"Error: {playback_template_path} does not exist.")
        return

    with open(playback_template_path, "r", encoding="utf-8") as template_file:
        content = template_file.read()

    # Replace placeholders with actual values
    with open(f"tools/VERSION.md", "r", encoding="utf-8") as version_file:
        version_content = version_file.read().strip()
    content = content.replace("{version}", f"{version_content}.{os.getenv('CI_JOB_ID')}")
    content = content.replace("{template_name}", template_name)
    content = content.replace("{template_display_name}", DISPLAY_NAME_MAP[template_name])
    content = content.replace("{ovc_streaming_option}", "[nvcf_streaming]: NVCF Streaming")
    content = content.replace("{ovc_streaming_option_name}", "nvcf")

    with open(playback_output_path, "w", encoding="utf-8") as output_file:
        output_file.write(content)


def _make_project(arg_parser: argparse.ArgumentParser, repo_path: Path, template_name: str) -> None:
    """
    Generates the project from the template name and replays the template using the PLAYBACK file.
    """

    repo_tools_path = repo_path.joinpath(f"repo.{SHELL_EXT}")
    playback_file_path = repo_path.joinpath("tools/ci/PLAYBACK")

    if not repo_tools_path.exists():
        arg_parser.error(f"Could not find the repo tools at the following path: {repo_tools_path}")
        sys.exit(1)

    if not playback_file_path.exists():
        arg_parser.error(f"Error: {playback_file_path} does not exist.")
        sys.exit(1)

    print(f"\n{UNDERLINE}")
    print(f"*** Generating the {DISPLAY_NAME_MAP.get(template_name)} template...")
    print(UNDERLINE)

    try:
        subprocess.run(f"yes | {repo_tools_path} template replay {str(playback_file_path)}", shell=True, check=True)
    except subprocess.CalledProcessError as e:
        arg_parser.error(f"Error replaying the template: {e}")
        sys.exit(1)


def _build_project(arg_parser: argparse.ArgumentParser, repo_path: Path, template_name: str) -> None:
    """Builds the project."""

    repo_tools_path = repo_path.joinpath(f"repo.{SHELL_EXT}")
    if not repo_tools_path.exists():
        arg_parser.error(f"Could not find the repo tools at the following path: {repo_tools_path}")
        sys.exit(1)

    print(f"\n{UNDERLINE}")
    print(f"*** Building {DISPLAY_NAME_MAP.get(template_name)}...")
    print(f"{UNDERLINE}\n")
    subprocess.run([f"{repo_tools_path}", "build", "-r"], check=False)


def _get_version_str(repo_path: Path) -> str:
    """Gets the version string from the VERSION.md file."""

    version_path = repo_path.joinpath("tools", "VERSION.md")
    if not version_path.exists():
        return ""
    with open(version_path, "r", encoding="utf-8") as version_file:
        version_str = version_file.read().strip().replace(".", "-")
    return version_str


def _get_commit_hash_str(project_id, branch="master") -> str:
    """Fetches the short hash of the latest commit from the master branch of a project."""

    api_endpoint = f"{GITLAB_API_URL}/projects/{project_id}/repository/branches/{branch}"

    command = ["curl", "-s", api_endpoint]
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        output = result.stdout
        data = json.loads(output)

        short_id = data["commit"]["short_id"]
        return short_id
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error fetching commit hash: {e.stderr}")


def _package_container(arg_parser: argparse.ArgumentParser, repo_path: Path, template_name: str) -> None:
    """Packages the project as a container."""

    repo_tools_path = repo_path.joinpath(f"repo.{SHELL_EXT}")
    if not repo_tools_path.exists():
        arg_parser.error(f"Could not find the repo tools at the following path: {repo_tools_path}")
        sys.exit(1)

    print(f"\n{UNDERLINE}")
    print(f"*** Packaging {DISPLAY_NAME_MAP.get(template_name)} as a container...")
    print(f"{UNDERLINE}\n")
    version_str = _get_version_str(repo_path)
    if not version_str:
        print("Could not find the version string in the VERSION.md file.")
        sys.exit(1)

    if BUILD_FOR_OVC2 == "true":
        ovc2_postfix = "_ovc2"
    else:
        ovc2_postfix = ""
    target_app = f"source/apps/{template_name}_nvcf.kit"
    kit_commit_hash = _get_commit_hash_str(KIT_GITLAB_PROJECT_ID)
    kat_commit_hash = os.getenv("CI_COMMIT_SHORT_SHA")

    # Add MR tag if building for MR with checkbox enabled
    mr_tag = os.getenv("CONTAINER_TAG", "")
    if mr_tag:
        container_name = f"{template_name}{ovc2_postfix}:{version_str}_{kit_commit_hash}_{kat_commit_hash}_{mr_tag}"
        print(f"Building MR container with tag: {mr_tag}")
    else:
        container_name = f"{template_name}{ovc2_postfix}:{version_str}_{kit_commit_hash}_{kat_commit_hash}"
        print("Building standard container (no MR tag)")

    # This will still return with a return code of 0 even if the packaging fails.
    # Since there is no (easy) way to check for failure and halt the script here,
    # instead the zip process will check for the existence of the container and
    # halt the script if it is not found.
    subprocess.run(
        [
            f"{repo_tools_path}",
            "package_container",
            "--image-tag",
            container_name,
            "--app",
            target_app,
        ],
        check=True,
    )


def _save_container(repo_path: Path, template_name: str, output_dir: Path, make_zip: bool = True) -> None:
    """
    Saves the container to the output directory.
    Optionally, compresses it as a Zip file.
    """

    print(f"\n{UNDERLINE}")
    print("*** Saving the container...")
    print(f"{UNDERLINE}\n")
    version_str = _get_version_str(repo_path)
    if not version_str:
        print("Could not find the version string in the VERSION.md file.")
        sys.exit(1)

    kit_commit_hash = _get_commit_hash_str(KIT_GITLAB_PROJECT_ID)
    kat_commit_hash = os.getenv("CI_COMMIT_SHORT_SHA")
    output_dir.mkdir(parents=True, exist_ok=True)
    ovc2_postfix = "_ovc2" if BUILD_FOR_OVC2 == "true" else ""

    # Add MR tag if building for MR with checkbox enabled
    mr_tag = os.getenv("CONTAINER_TAG", "")
    if mr_tag:
        name = f"{template_name}{ovc2_postfix}:{version_str}_{kit_commit_hash}_{kat_commit_hash}_{mr_tag}"
        print(f"Saving MR container with tag: {mr_tag}")
    else:
        name = f"{template_name}{ovc2_postfix}:{version_str}_{kit_commit_hash}_{kat_commit_hash}"
        print("Saving standard container (no MR tag)")
    filepath = output_dir.joinpath(name)

    try:
        subprocess.run(
            [
                "docker",
                "image",
                "save",
                "-o",
                str(filepath.with_suffix(".tar")),
                f"{name}",
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        print("\tCould not find the container. Container packaging may have failed.")
        print("\tCleaning up unlabelled Docker images...")
        subprocess.run(
            ["docker", "images", "-f", '"dangling=true" -q | xargs docker rmi'],
            check=False,
        )
        print("\tExiting...")
        sys.exit(1)

    if make_zip:
        print("\tCompressing the container as a Zip file...")
        with ZipFile(str(filepath.with_suffix(".zip")), "w", compression=ZIP_DEFLATED) as z:
            z.write(str(filepath.with_suffix(".tar")))


parser = argparse.ArgumentParser(description="""This will build a K-A-T template, package it as a
    container, and Zip compress that container to a provided
    output directory.""")

repo_path = Path.cwd()
template_name = os.getenv("APP")
output_dir = Path.cwd().joinpath("_containers")

_generate_playback_file(template_name)
_make_project(parser, repo_path, template_name)
_build_project(parser, repo_path, template_name)
_package_container(parser, repo_path, template_name)
_save_container(repo_path, template_name, output_dir)

print(f"\n{UNDERLINE}")
print("\n*** Done!")
print(UNDERLINE)
