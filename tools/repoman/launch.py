import argparse
import logging
import sys
from glob import glob
from pathlib import Path
from typing import Callable, Dict, List, Optional

import omni.repo.man
from omni.repo.kit_template.frontend.template_tool import CLIInput
from omni.repo.man.configuration import add_config_arg
from omni.repo.man.exceptions import QuietExpectedError
from omni.repo.man.fileutils import rmtree
from omni.repo.man.guidelines import get_host_platform
from omni.repo.man.utils import find_and_extract_package, run_process

# These dependencies come from repo_kit_template
from rich.console import Console
from rich.theme import Theme

logger = logging.getLogger(__name__)

KIT_APP_PATH = Path(omni.repo.man.resolve_tokens("${root}/source/apps/"))

PACKAGE_ARG = "--package"

KIT_PACKAGE_DIR = Path(omni.repo.man.resolve_tokens("${root}/_packages/"))

# This should match repo_kit_template.palette
INFO_COLOR = "#3A96D9"
theme = Theme()
console = Console(theme=theme)


def _get_repo_cmd():
    repo_cmd = "${root}/repo${shell_ext}"
    return omni.repo.man.resolve_tokens(repo_cmd)


def _quiet_error(err_msg: str):
    # Need something like QuietExpectedError that just prints and exits 1.
    print(err_msg)
    raise QuietExpectedError(err_msg)


def _select(apps: list) -> str:
    cli_input = CLIInput()
    return cli_input.select(
        message="Select with arrow keys which App would you like to launch:", choices=apps, default=apps[0]
    )


def discover_kit_files(target_directory: Path) -> List:
    if not target_directory.is_dir():
        return []

    discovered_app_names = []
    for app in glob("**/*.kit", root_dir=target_directory, recursive=True):
        app_path = Path(app)
        app_name = app_path.name
        discovered_app_names.append(app_name)

    return discovered_app_names


def select_kit(target_directory: Path) -> str:
    # Get list of kit apps on filesystem.
    app_names = discover_kit_files(target_directory)
    if len(app_names) == 0:
        repo_cmd = Path(_get_repo_cmd()).name
        err_msg = f"There were no apps discovered in the default Kit App Path: {target_directory}. You must create an app first via `{repo_cmd} template new` and then build via `{repo_cmd} build`."
        _quiet_error(err_msg)
    else:
        # perform a select to set app_name
        app_name = _select(app_names)
        return app_name


def launch_kit(app_name, target_directory: Path, config: str = "release", dev_bundle: bool = False):
    # Some assumptions are being made on the folder structure of target_directory.
    # It should be the `_build/${host_platform}/${config}/` folder which contains entrypoint scripts
    # for the included kit apps.
    # It should contain an apps folder that contains various target kit apps.
    if app_name == None:
        # Select the kit App from the apps sub-dir.
        app_name = select_kit(target_directory / "apps")

    print(f"launching {app_name}!")

    # In target_directory there will be .sh/.bat scripts that launch the bundled version of kit
    # with the targeted kit app .kit file.
    app_build_path = Path(omni.repo.man.resolve_tokens(str(target_directory) + "/" + app_name + "${shell_ext}"))
    if not app_build_path.is_file():
        err_msg = f"Desired built Kit App: {app_name} is missing the built entrypoint script: {app_build_path}. Have you built your app via `{_get_repo_cmd()} build`?"
        _quiet_error(err_msg)

    # import os
    # This might not be necessary, we might not need to map in sys.stdin?
    # os.environ["repo_diagnostic"] = "1"
    kit_cmd = [str(app_build_path)]
    if dev_bundle:
        kit_cmd += ["--enable", "omni.kit.developer.bundle"]

    ret_code = run_process(kit_cmd, exit_on_error=False)
    # TODO: do something with this ret_code


def expand_package(package_path: str) -> Path:
    archive_path = Path(package_path)
    archive_timestamp = str(archive_path.stat().st_mtime)
    if not archive_path.is_file():
        raise Exception(
            f"Target archive {archive_path} is not a file. You can use `{PACKAGE_ARG}` to expand and launch an already packaged Kit application."
        )

    archive_name = archive_path.name
    destination = KIT_PACKAGE_DIR / archive_name
    timestamp_breadcrumb = destination / "timestamp.txt"

    # Check if already expanded/present.
    if destination.is_dir() and timestamp_breadcrumb.is_file():
        timestamp = timestamp_breadcrumb.read_text()
        if timestamp == archive_timestamp:
            print(f"Archive already expanded at {destination}")
            return destination
        else:
            print(f"Archive present at {destination} but does not match timestamp of {archive_path}. Removing.")
            rmtree(destination)

    elif destination.is_dir():
        # For some reason we didn't get to the point of adding the breadcrumb.
        # Delete it and start over.
        print(f"Deleting unknown directory at destination: {destination}")
        rmtree(destination)

    # Extract the archive with selective longpath path manipulation for Windows.
    folder_to_extract, archive_path = find_and_extract_package(str(archive_path))
    # `find_and_extract_package` does some windows longpath magic and returns a shortened directory
    # Create our desired destination, and then move the extracted archive to it.
    destination.parent.mkdir(parents=True, exist_ok=True)
    Path(folder_to_extract).rename(destination)

    if not destination.is_dir():
        raise Exception(f"Failure on archive extraction for archive: {archive_path} to destination: {destination}")

    # Add breadcrumb file.
    timestamp_breadcrumb.write_text(archive_timestamp)
    return destination


def add_dev_bundle_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-d",
        "--dev-bundle",
        dest="dev_bundle",
        required=False,
        action="store_true",
        help="Enable the developer debugging extension bundle.",
    )


def from_package_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-p",
        PACKAGE_ARG,
        dest="from_package",
        required=False,
        type=str,
        help="Path to a kit app package that you want to launch",
    )


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Optional[Callable]:
    """Entry point for 'repo_launch' tool"""

    parser.description = "Simple tool to launch Kit applications"
    # --dev-bundle
    add_dev_bundle_arg(parser)
    # --package
    from_package_arg(parser)

    # Get list of kit apps on filesystem.
    app_names = discover_kit_files(KIT_APP_PATH)

    subparsers = parser.add_subparsers()
    for app in app_names:
        subparser = subparsers.add_parser(app, help="Some blob that comes out of the USD explorer kit app?")
        subparser.set_defaults(app_name=app)
        # Add --config/--release support
        add_config_arg(subparser)
        # Add --dev-bundle support
        add_dev_bundle_arg(subparser)

    # tool_config = config.get("repo_launch", {})

    # Config
    # enabled = tool_config.get("enabled", False)

    def run_repo_tool(options: argparse.Namespace, config: Dict):

        app_name = None
        config = "release"
        dev_bundle = False

        # Providing a kit file is optional, otherwise we present a select
        if hasattr(options, "app_name"):
            app_name = options.app_name

        # If a kit file was selected then a config value was optionally set.
        if hasattr(options, "config"):
            config = options.config

        if hasattr(options, "dev_bundle"):
            dev_bundle = options.dev_bundle

        try:
            # Launching from a distributed package
            console.print("\[ctrl+c to Exit]", style=INFO_COLOR)
            if options.from_package:
                package_path = expand_package(options.from_package)
                launch_kit(None, package_path, config, dev_bundle)

            # Launching a locally built application
            else:
                # Launch the thing, or query the user and then launch the thing.
                build_path = Path(f"_build/{get_host_platform()}/{config}/")
                launch_kit(app_name, build_path, config, dev_bundle)

        except (KeyboardInterrupt, SystemExit):
            console.print("Exiting", style=INFO_COLOR)
            # exit(0) for now due to non-zero exit reporting.
            sys.exit(0)

    return run_repo_tool
