"""
Tool to publish a Docker container for a specified K-A-T project to NGC.
"""

import os
import subprocess
from pathlib import Path

from ngcsdk import Client
from registry.api.image import ImageAPI

UNDERLINE = "-" * 80
NGC_API_KEY = os.getenv("NGC_API_KEY")
NGC_ORG_NAME = os.getenv("NGC_ORG_NAME")
NGC_DOMAIN = "nvcr.io"
MR_TRIGGER_BUILD = os.getenv("_MR_KIT_APP_TEMPLATE")
TRIGGER_BRANCH = os.getenv("CI_COMMIT_BRANCH")
BUILD_FOR_OVC2 = os.getenv("OVC2")
# Create Client and configure with NGC_API_KEY, org_name, and team_name
client = Client()
client.configure(api_key=NGC_API_KEY, org_name=NGC_ORG_NAME, team_name="no-team")
image_api = ImageAPI(client)


def _announce_meesage(message: str):
    print(f"\n{UNDERLINE}")
    print(f"*** {message}")
    print(UNDERLINE)


def _get_image_tags(image_name: str) -> list:
    """Fetches NGC Container tags and returns as a list"""

    print(f"Searching for {image_name}...")
    try:
        repository, image_scan_details = image_api.info(image_name)
        _announce_meesage(f"""Name: {repository.name}\n\tTags: {", ".join(repository.tags)}""")
    except AttributeError as err:
        print(f"Not able to get Image info: {err}")
    return repository.tags


def _load_and_push_main_tags(repo_path: Path) -> list:
    """Loads all container images from the _containers/ folder, tags them with the desired name, and NGC registry."""

    folder_path = repo_path / "_containers"

    if not folder_path.is_dir():
        print(f"Error: {folder_path} does not exist or is not a directory.")
        return []

    loaded_images = []  # List to store base names of successfully loaded images

    for image_file in folder_path.iterdir():
        if image_file.is_file() and image_file.suffix == ".tar":
            image_file = Path(image_file)
            print(f"Loading Docker image: {image_file.name}")
            command = f"docker load < {image_file}"
            try:
                subprocess.run(command, shell=True, text=True, check=True)

                base_name, tag = image_file.stem.split(":", 1)
                tag = tag.replace(":", "-")
                full_image_name = f"{NGC_DOMAIN}/{NGC_ORG_NAME}/{base_name}:{tag}"

                tag_command = f"docker tag {base_name}:{tag} {full_image_name}"
                subprocess.run(tag_command, shell=True, text=True, check=True)
                image_api.push(full_image_name, output=True)

                loaded_images.append(full_image_name)  # Add the tagged image to the list
                _announce_meesage(f"Loaded and tagged image: {full_image_name}")
            except subprocess.CalledProcessError as err:
                print(f"Failed to load or tag image {image_file}: {err}")
    return loaded_images


def _manage_latest_tags(image_name: str, max_versions: int = 7) -> None:
    """
    Renames 'latest' to 'latest-1', 'latest-1' to 'latest-2', and so on up to `latest-max_versions`.
    """
    image_name = image_name.split(":")[0]
    current_tags = _get_image_tags(image_name)

    # renaming tags in reverse order to avoid conflicts
    for version in range(max_versions, 0, -1):
        old_tag = f"latest-{version - 1}" if version > 1 else "latest"
        new_tag = f"latest-{version}"

        if old_tag in current_tags:
            try:
                image_api.pull(f"{image_name}:{old_tag}")
                _announce_meesage(f"Pulled {image_name}:{old_tag}")
                rename_command = f"docker tag {image_name}:{old_tag} {image_name}:{new_tag}"
                subprocess.run(rename_command, shell=True, text=True, check=True)
                _announce_meesage(f"Renamed {old_tag} to {new_tag}")
                image_api.push(f"{image_name}:{new_tag}", output=True)
                _announce_meesage(f"Pushed {image_name}:{new_tag}")
            except subprocess.CalledProcessError as err:
                print(f"Error renaming {old_tag} to {new_tag}: {err}")


def _push_latest_tags(image_names: list):
    """
    Pushes images to NGC as latest
    """
    for image_name in image_names:
        _manage_latest_tags(image_name)

        image_base_name = image_name.split(":")[0]
        try:
            tag_latest_command = f"docker tag {image_name} {image_base_name}:latest"
            subprocess.run(tag_latest_command, shell=True, text=True, check=True)
            image_api.push(f"{image_base_name}:latest", output=True)
            _announce_meesage(f"Pushed {image_base_name}:latest")
        except subprocess.CalledProcessError as err:
            print(f"Error tagging the image as latest: {err}")


repo_path = Path.cwd()
images = _load_and_push_main_tags(repo_path)

# Only push as 'latest' for main/master branch builds, not for MR builds
is_mr_build = bool(os.getenv("CONTAINER_TAG"))  # MR builds have CONTAINER_TAG set
if (
    MR_TRIGGER_BUILD == "false"
    and TRIGGER_BRANCH in ["master", "main"]
    and BUILD_FOR_OVC2 != "true"
    and not is_mr_build
):
    _push_latest_tags(images)
elif is_mr_build:
    _announce_meesage("MR build detected - skipping 'latest' tag push")

_announce_meesage("Done!")
