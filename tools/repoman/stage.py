import argparse
import json
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Dict, Optional

from omni.repo.man.configuration import resolve_tokens
from omni.repo.man.exceptions import QuietExpectedError
from omni.repo.man.guidelines import get_host_platform
from omni.repo.man.log import print_log
from omni.repo.man.utils import change_cwd, extract_archive_to_folder

_PACKMAN_SHA1_FILE_NAME = ".packman.sha1"

# Packman Cache directory
PACKMAN_CACHE_DIR = os.getenv("PM_PACKAGES_ROOT")
# Kit-Kernel directory in the Packman Cache
KIT_KERNEL_PATH = Path(PACKMAN_CACHE_DIR) / "chk" / f"kit-kernel"
# Generated Packman XML file path
GENERATED_PACKMAN_XML_PATH = Path(resolve_tokens("${root}/_build/generated/kit-sdk.packman.xml"))

logger = logging.getLogger(__name__)


def _quiet_error(err_msg: str):
    # Need something like QuietExpectedError that just prints and exits 1.
    print(err_msg)
    raise QuietExpectedError(err_msg)


@dataclass
class NgcKitKernelInfo:
    """
    Data class to store the NGC Kit-Kernel info from the on-disk JSON file.
    """

    url: str
    org: str
    team: str
    resource: str
    version: str
    packman_version: str
    path: Path

    @classmethod
    def from_dict(cls, data: Dict, path: Path) -> "NgcKitKernelInfo":
        return cls(
            url=data.get("url", ""),
            org=data.get("org", ""),
            team=data.get("team", ""),
            resource=data.get("resource", ""),
            version=data.get("version", ""),
            packman_version=data.get("packman_version", ""),
            path=path,
        )

    def to_dict(self) -> Dict:
        data = asdict(self)
        # Don't return the path to the NGC-Kit-Kernel.json file.
        # This is just a convenience path for within this tool.
        data.pop("path", None)
        return data


def read_packman_xml_version(packman_kit_sdk_xml: Path) -> str:
    """
    Read the kit-kernel package version from the Packman XML file.

    Args:
        packman_kit_sdk_xml(Path): Path to the Packman XML file.

    Returns:
        The kit-kernel package version string from the Packman XML file.
    """
    # Parse the XML file and update the version
    tree = ET.parse(packman_kit_sdk_xml)
    root = tree.getroot()
    # Find the package element and retrieve its version attribute
    package_element = root.find(".//package")
    return package_element.get("version")


def write_generated_packman_xml(packman_kit_sdk_xml: Path, kit_kernel_version: str):
    """
    Write the generated Packman XML file.

    Args:
        packman_kit_sdk_xml(Path): Path to the Packman XML file.
        kit_kernel_version(str): The kit-kernel package version string to update.
    """
    packman_kit_sdk_xml.parent.mkdir(parents=True, exist_ok=True)
    with open(packman_kit_sdk_xml, "w") as f:
        f.write('<project toolsVersion="5.0">\n')
        f.write(
            '  <dependency name="kit_sdk_${config}" linkPath="../${platform_target}/${config}/kit" tags="${config} non-redist">\n'
        )
        f.write(f'    <package name="kit-kernel" version="{kit_kernel_version}"/>\n')
        f.write("  </dependency>\n")
        f.write("</project>\n")


def read_ngc_json(ngc_kit_kernel_json: Path, platform: str = None) -> NgcKitKernelInfo:
    """
    Read the NGC Kit-Kernel info from the on-disk JSON file.

    Args:
        ngc_kit_kernel_json(Path): Path to the NGC Kit-Kernel JSON file.
        platform(str): The platform to read the NGC Kit-Kernel info for.

    Returns:
        NgcKitKernelInfo: The NGC Kit-Kernel info from the on-disk JSON file.
    """
    with open(ngc_kit_kernel_json, "r") as f:
        data = json.load(f)
    if platform is None:
        platform = get_host_platform()
    return NgcKitKernelInfo.from_dict(data.get(platform), ngc_kit_kernel_json)


def write_ngc_json(ngc_kit_kernel: NgcKitKernelInfo, platform: str = None):
    """
    Write the NGC Kit-Kernel info to the on-disk JSON file.

    Args:
        ngc_kit_kernel_json(Path): Path to the NGC Kit-Kernel JSON file.
        ngc_kit_kernel(NgcKitKernelInfo): The NGC Kit-Kernel info to write.
        platform(str): The platform to write the NGC Kit-Kernel info for.
    """
    with open(str(ngc_kit_kernel.path), "r") as f:
        data = json.load(f)
    if platform is None:
        platform = get_host_platform()
    data[platform] = ngc_kit_kernel.to_dict()
    with open(str(ngc_kit_kernel.path), "w") as f:
        json.dump(data, f, indent=4)


def _check_if_kit_kernel_is_present_on_disk(ngc_kit_kernel_info: NgcKitKernelInfo) -> bool:
    if ngc_kit_kernel_info.packman_version:
        ngc_kit_kernel_path = KIT_KERNEL_PATH / ngc_kit_kernel_info.packman_version
        if ngc_kit_kernel_path.exists() and ngc_kit_kernel_path.is_dir():
            logger.info(f"Kit-Kernel {ngc_kit_kernel_info.packman_version} is already present on disk.")
            return True
    return False


def _update_kit_kernel_timestamp(ngc_kit_kernel_info: NgcKitKernelInfo):
    # Create the .packman.sha1 file so Packman doesn't consider this package corrupt.
    # If the file already exists touch it to update the timestamp for Packman timestamp pruning.
    ngc_kit_kernel_path = KIT_KERNEL_PATH / ngc_kit_kernel_info.packman_version
    packman_file = ngc_kit_kernel_path / _PACKMAN_SHA1_FILE_NAME
    packman_file.touch(exist_ok=True)

    # Force filesystem sync to ensure file is written to disk
    with open(packman_file, "r+b") as f:
        os.fsync(f.fileno())


def _check_if_kit_kernel_already_downloaded(ngc_kit_kernel_info: NgcKitKernelInfo) -> bool:
    from omni.repo.ngc import configure_client, list_resource_files

    ngc_client = configure_client()
    try:
        resource_files = list_resource_files(
            ngc_client=ngc_client,
            resource_org_name=ngc_kit_kernel_info.org,
            resource_team_name=ngc_kit_kernel_info.team,
            resource_name=ngc_kit_kernel_info.resource,
            resource_version=ngc_kit_kernel_info.version,
        )

    except QuietExpectedError as e:
        if "AuthenticationException" in str(e):
            # User is not authenticated with NGC, and NGC is requiring an NGC API key for list_resource_files
            # for this resource.
            raise
        return False

    except Exception as e:
        logger.info(f"Error listing resource files from NGC: {e}")
        return False

    # The expectation is there is a single archive per kit-kernel version.
    if len(resource_files) == 1:
        archive_file = Path(resource_files[0])
        kit_kernel_version = archive_file.stem.split("@")[1]
        kit_kernel_version_path = KIT_KERNEL_PATH / kit_kernel_version
        if kit_kernel_version_path.exists() and kit_kernel_version_path.is_dir():
            logger.info(
                f"Kit-Kernel {kit_kernel_version} is already present on disk. Skipping download, updating {ngc_kit_kernel_info.path}."
            )
            ngc_kit_kernel_info.packman_version = kit_kernel_version
            # Update the NGC-Kit-Kernel.json file to prevent future downloads.
            write_ngc_json(ngc_kit_kernel_info)
            # Generate kit-sdk.packman.xml to match the on-disk Kit-Kernel version
            write_generated_packman_xml(GENERATED_PACKMAN_XML_PATH, ngc_kit_kernel_info.packman_version)
            # Update the timestamp of the Kit-Kernel on disk for Packman timestamp pruning.
            _update_kit_kernel_timestamp(ngc_kit_kernel_info)
            return True
    return False


def stage_kit_kernel(config: Dict):
    """
    Stage the NGC Kit-Kernel into the Packman cache as a repo build pre-fetch step.
    """

    # Note: Print statements reference Kit-SDK but internally we reference Kit-Kernel. The expectation is that
    # we will swap to using Kit-Kernel exclusively from NGC with Kit-SDK 109.0.

    # Get the NGC Kit-Kernel JSON file path from the repo.toml file.
    stage_config = config.get("repo_stage", {})
    ngc_kit_kernel_json = Path(stage_config.get("stage_file", resolve_tokens("${root}/deps/NGC-Kit-Kernel.json")))

    # Create the kit-sdk directory in the Packman Cache
    KIT_KERNEL_PATH.mkdir(parents=True, exist_ok=True)

    # Grab NGC Kit-Kernel info from the on-disk JSON file.
    ngc_kit_kernel_info = read_ngc_json(ngc_kit_kernel_json)

    # First check if the NGC-Kit-Kernel.json information is up-to-date.
    if _check_if_kit_kernel_is_present_on_disk(ngc_kit_kernel_info):
        # Generate kit-sdk.packman.xml to match the on-disk Kit-Kernel version
        write_generated_packman_xml(GENERATED_PACKMAN_XML_PATH, ngc_kit_kernel_info.packman_version)
        # Update the timestamp of the Kit-Kernel on disk.
        _update_kit_kernel_timestamp(ngc_kit_kernel_info)
        return
    else:
        logger.info(
            f"Kit-Kernel Packman path is not set in {ngc_kit_kernel_info.path}. Checking NGC for Kit-Kernel version."
        )

    # Query NGC to get the Kit-Kernel archive name. It is possible that Kit-Kernel is already present on disk
    # but the NGC-Kit-Kernel.json file is not updated.
    if _check_if_kit_kernel_already_downloaded(ngc_kit_kernel_info):
        return
    else:
        print_log(f"Kit-Kernel {ngc_kit_kernel_info.version} is not present on disk. Downloading from NGC.")

    # Download Kit-Kernel from NGC
    with TemporaryDirectory() as temp_dir:
        try:
            from omni.repo.ngc import configure_client, download_resource

            ngc_client = configure_client()
            resource_info = download_resource(
                ngc_client=ngc_client,
                resource_org_name=ngc_kit_kernel_info.org,
                resource_team_name=ngc_kit_kernel_info.team,
                resource_name=ngc_kit_kernel_info.resource,
                resource_version=ngc_kit_kernel_info.version,
                target_path=temp_dir,
            )
        except Exception as e:
            _quiet_error(
                f"Error downloading Kit-Kernel from NGC: {e}"
                + "\nAs of Kit 109.0, Kit-Kernel is fetched from NGC and requires an NGC API key for Production builds."
                + "\nPlease reference the NGC User Guide for instructions on configuring the API key -> "
                + "https://docs.nvidia.com/ngc/latest/ngc-user-guide.html"
            )

        resource_path = Path(temp_dir) / f"{ngc_kit_kernel_info.resource}_v{ngc_kit_kernel_info.version}"
        # Expand the retrieved archive into the Packman cache.
        with change_cwd(resource_path):
            # Discover the archive file.
            archive_file = next(resource_path.glob("*.zip"))
            kit_kernel_version = archive_file.stem.split("@")[1]
            kit_kernel_version_path = KIT_KERNEL_PATH / kit_kernel_version

            # Extract the archive file.
            if kit_kernel_version_path.exists() and kit_kernel_version_path.is_dir():
                # This is awkward but the NGC SDK resource info function does not return the list of files associated with a resource.
                # of the resource.
                logger.info(f"Kit-Kernel {kit_kernel_version} is already present on disk. Not expanding archive.")
            else:
                extract_archive_to_folder(archive_file, kit_kernel_version_path)

            # Update the timestamp of the Kit-Kernel on disk for Packman timestamp pruning.
            _update_kit_kernel_timestamp(ngc_kit_kernel_info)

            # Write out the NGC Kit-Kernel package version string into the JSON file
            # for future short-circuiting of the download.
            ngc_kit_kernel_info.packman_version = kit_kernel_version
            write_ngc_json(ngc_kit_kernel_info)

            # Generate kit-sdk.packman.xml to match the on-disk Kit-Kernel version
            write_generated_packman_xml(GENERATED_PACKMAN_XML_PATH, kit_kernel_version)

    print_log(f"Kit-Kernel {kit_kernel_version} has been staged into the Packman cache.")


def run_repo_tool(options: argparse.Namespace, config: Dict):
    stage_kit_kernel(config)


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Optional[Callable]:
    """Entry point for 'repo_stage' tool"""

    parser.description = "Tool to stage Kit-Kernel into the Packman Cache for Repo Build"

    return run_repo_tool
