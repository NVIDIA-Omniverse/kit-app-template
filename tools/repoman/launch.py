import argparse
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from collections import defaultdict
from glob import glob
from pathlib import Path
from typing import Callable, Dict, List, Optional

import omni.repo.man
from omni.repo.kit_template.backend import read_toml
from omni.repo.kit_template.frontend import CLIInput, Separator
from omni.repo.man.exceptions import QuietExpectedError
from omni.repo.man.fileutils import rmtree
from omni.repo.man.guidelines import get_host_platform
from omni.repo.man.utils import find_and_extract_package, process_args_to_cmd, run_process, run_process_return_output

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
    repo_cmd = "repo${shell_ext}"
    return omni.repo.man.resolve_tokens(repo_cmd)


def _quiet_error(err_msg: str):
    # Need something like QuietExpectedError that just prints and exits 1.
    print(err_msg)
    raise QuietExpectedError(err_msg)


def _select(query: str, apps: list) -> str:
    cli_input = CLIInput()
    return cli_input.select(message=query, choices=apps, default=apps[0])


def _run_process(args: List, exit_on_error=False, timeout=None, **kwargs) -> int:
    """Run system process and wait for completion.

    This was copy/pasted out of omni.repo.man.utils to work around the KeyboardInterrupt error message.

    Args:
        args (List): List of arguments.
        exit_on_error (bool, optional): Exit if return code is non zero.
    """
    returncode = 0
    message = ""
    try:
        logger.info(f"running process: {process_args_to_cmd(args)}")
        # Optionally map in sys.stdin for local debugging via pdb.set_trace.
        # Otherwise use DEVNULL, prevents weird failures on Windows.
        stdin = subprocess.DEVNULL
        if os.environ.get("repo_diagnostic"):
            stdin = sys.stdin

        p = subprocess.run(args, stdin=stdin, stdout=sys.stdout, stderr=subprocess.STDOUT, timeout=timeout, **kwargs)
        returncode = p.returncode
    except subprocess.CalledProcessError as e:
        returncode = e.returncode
        message = e
    except subprocess.TimeoutExpired as e:
        returncode = -1
        message = e
    except (FileNotFoundError, OSError, Exception) as e:
        returncode = -1
        message = str(e)
    except KeyboardInterrupt:
        returncode = -1
        message = "KeyboardInterrupt"

    # Do not logger.error for a KeyboardInterrupt
    if returncode != 0 and message != "KeyboardInterrupt":
        logger.error(f'error running: {process_args_to_cmd(args)}, code: {returncode}, message: "{message}"')
        if exit_on_error:
            sys.exit(returncode)
    return returncode


def discover_kit_files(target_directory: Path) -> List:
    if not target_directory.is_dir():
        return []

    discovered_app_names = []
    for app in glob("**/*.kit", root_dir=target_directory, recursive=True):
        app_path = Path(app)
        app_name = app_path.name
        discovered_app_names.append(app_name)

    return discovered_app_names


def discover_typed_kit_files(target_directory: Path) -> Dict:
    """Discover .kit files in `target_directory` return the filenames including the repo template type metadata.

    Args:
        target_directory (Path): Path where .kit files exist to be read-in.

    Returns:
        Dict: keys == application type, values = list of application names of that type.
    """
    if not target_directory.is_dir():
        return {}

    discovered_apps = defaultdict(list)
    for app in glob("**/*.kit", root_dir=target_directory, recursive=True):
        app_path = target_directory / app
        try:
            app_data = read_toml(app_path)
            app_type = app_data.get("template", {}).get("type", "ApplicationTemplate")
            discovered_apps[app_type].append(app_path.name)
        except Exception as e:
            # For now broadly catching until repo_kit_template's read_toml can instead raise a omni.repo.man.exception
            err_msg = f"Failed to read kit file: {app_path.resolve()}. There might be a duplicate toml key: {e}"
            _quiet_error(err_msg)

    return discovered_apps


def get_kit_images() -> List[dict]:
    """Query Docker for images with the kit_app_template label.

    Raises:
        QuietExpectedError: If no images are found then raise with an alert.

    Returns:
        List[dict]: A list of container images created by `repo package --container`.
    """
    # Query docker for our images
    cmd = ["docker", "images", "--filter", "label=kit_app_template", "--format", "json"]
    _, output = run_process_return_output(cmd, exit_on_error=True, print_stdout=False, print_stderr=True, quiet=True)
    if len(output) == 0:
        msg = f"Failed to detect any container images built with `repo package --container`. You must package an application as a container before you can launch it."
        _quiet_error(msg)

    # Filter out container images to only present those with a latest tag to avoid
    # presenting iterations of the same container.
    processed_output = [json.loads(container) for container in output]
    discovered_images = [container for container in processed_output if container.get("Repository") != "<none>"]

    return discovered_images


def get_image_template_mapping(discovered_images: List[dict]) -> Dict[str, str]:
    """Filter through the discovered images and extract the kit-app-template metadata to provide the user with context of what application is inside of the image.

    Args:
        discovered_images (List[dict]): A list of discovered container images.

    Raises:
        QuietExpectedError: Raise if a discovered image suddenly doesn't exist.

    Returns:
        Dict[str, str]: A dict where the first key contains the image repository/name + kit-app-template created application name. The value is the docker image ID.
    """
    available_images = {}
    for container in discovered_images:
        # Inspect each image
        cmd = ["docker", "image", "inspect", container.get("ID"), "--format=json"]
        _, output = run_process_return_output(
            cmd, exit_on_error=True, print_stdout=False, print_stderr=True, quiet=True
        )
        if len(output) != 1:
            msg = f"Failed to inspect docker image {container.get('ID')}."
            _quiet_error(msg)
        container_info = json.loads(output[0])[0]

        # Grab the kit_app_template label definining what application is inside.
        container_template = container_info.get("Config").get("Labels").get("kit_app_template")
        available_images[container.get("ID")] = {
            "container_name": container.get("Repository"),
            "container_tag": container.get("Tag"),
            "container_app_template": container_template,
            "container_select_name": f"{container.get('Repository')} - {container_template}",
        }

    return available_images


def run_selected_image(image_id: str, dev_bundle: bool, extra_args: List[str], verbose: bool):
    """Docker run the provided image_id, optionally enabling the developer bundle and passing in extra_args to the image entrypoint.

    Args:
        image_id (str): Docker image ID hash
        dev_bundle (bool): If true enable the kit developer bundle i
        extra_args (List[str]): List of arguments to feed into the container entrypoint, which likely feeds into Kit.
    """
    # TODO: Can we just assume the Dockerfile expose port ranges
    # and always map those in? Or should this be configurable via CLI args/toml file?
    nvda_kit_args = os.environ.get("NVDA_KIT_ARGS", "")
    nvda_kit_nucleus = os.environ.get("NVDA_KIT_NUCLEUS", "")
    docker_run_cmd = [
        "docker",
        "run",
        "--gpus=all",
        "--env",
        f"OM_KIT_VERBOSE={1 if verbose else 0}",
        "--env",
        f"NVDA_KIT_ARGS={nvda_kit_args}",
        "--env",
        f"NVDA_KIT_NUCLEUS={nvda_kit_nucleus}",
        "--mount",  # RTX Shader Cache
        "type=volume,src=omniverse_shader_cache,dst=/home/ubuntu/.cache/ov,volume-driver=local",
        "--mount",  # Kit Extension Cache
        "type=volume,src=omniverse_extension_cache,dst=/home/ubuntu/.local/share/ov,volume-driver=local",
        "--network=host",  # Host networking to simplify local testing of app streaming.
        image_id,
    ]

    # Set repo_diagnostic to map in stdin to prevent docker run from complaining.
    os.environ["repo_diagnostic"] = "1"
    # TODO: provide info on ctrl+c to exit out of this
    # TODO: mute the logger to hide the logger.error statement
    # due to a keyboardinterrupt event.

    # Enable the developer bundle
    if dev_bundle:
        docker_run_cmd += ["--enable", "omni.kit.developer.bundle"]

    # If extra arguments were passed into launch, directly feed them into the Kit binary.
    if extra_args:
        docker_run_cmd += extra_args

    _ = _run_process(
        docker_run_cmd,
        exit_on_error=False,
    )


def nvidia_driver_check():
    """Use nvidia-smi to check if a GPU is present on the host.

    Raises:
        QuietExpectedError: Raise if nvidia-smi is missing or no GPU is detected.
    """
    cmd = ["which", "nvidia-smi"]
    retcode, output = run_process_return_output(cmd, print_stdout=False, print_stderr=False, quiet=True)
    if retcode != 0:
        msg = "Failed to detect nvidia-smi on your host. Do you have the NVIDIA driver installed?"
        _quiet_error(msg)

    nvidia_smi = Path(output[0].strip())
    cmd = [str(nvidia_smi), "--list-gpus"]
    retcode, output = run_process_return_output(cmd, print_stdout=False, print_stderr=True, quiet=True)
    if retcode != 0:
        msg = "Failed to detect any NVIDIA gpus on your host. Do you have the NVIDIA driver installed?"
        _quiet_error(msg)


def launch_container(app_name: str, dev_bundle: bool = False, extra_args: List[str] = [], verbose: bool = False):
    """Discover kit_app_template created images and present them to the user to select and launch.

    Args:
        app_name (str): optional name for an image to launch, currently unused.
        dev_bundle (bool, optional): If true then enable the kit developer bundle. Defaults to False.
        extra_args (List[str], optional): List of args to feed into the container entrypoint. Defaults to [].
    """

    # Fetch the Docker container images that have been built via `repo package`
    discovered_images = get_kit_images()

    # Extract the kit_app_template tag from each container to present
    # some context for image selection by the user.
    available_images = get_image_template_mapping(discovered_images)

    selected_image_id = None
    if app_name:
        # Check if any of the images on the host match.
        # Checking against container name/repository:tag.
        for image_id, image in available_images.items():
            if app_name == f"{image.get('container_name')}:{image.get('container_tag')}":
                selected_image_id = image_id
                break

        if not selected_image_id:
            print(f"Unable to match user provided image name and tag: {app_name} to an image on the host.")

    if not selected_image_id:
        # User selects which docker image they want to launch
        selected_image_id = select_container(available_images)

    # Execute docker run with the selected image
    run_selected_image(selected_image_id, dev_bundle, extra_args, verbose)


def select_container(images: dict) -> dict:
    """Similar to `select_kit`, this optionally auto-selects a kit-app-template container image to launch if a single image exists, otherwise it queries the user for what they would like to launch.

    Args:
        images (dict): dictionary of images, keys == docker images with kit-app-template metadata, values == data out of docker image inspect.

    Returns:
        dict: the dict of docker image inspect data for the image the user has selected.
    """
    # Transform to enable a simpler select that humans understand.
    transformed_images = {
        f'{image.get("container_name")}:{image.get("container_tag")} - {image.get("container_app_template")}': image_id
        for image_id, image in images.items()
    }
    image_names = list(transformed_images.keys())

    if len(image_names) == 0:
        repo_cmd = Path(_get_repo_cmd()).name
        err_msg = f"There were no containerized apps discovered in your local Docker registry. You must create an app first via `{repo_cmd} template new`, build it via `{repo_cmd} build`, and package via `{repo_cmd} package --container`."
        _quiet_error(err_msg)
    elif len(image_names) == 1:
        selected_image_name = image_names[0]
    else:
        info_separator = Separator("Image Name:Image Tag - Containerized Kit Application")
        image_names.insert(0, info_separator)
        selected_image_name = _select(
            "Select with arrow keys which containerized App you would like to launch:", image_names
        )

    return transformed_images[selected_image_name]


class SeparatorIterator:
    # not a true iterator, a convenience class
    def __init__(self):
        self.current = 0

    def next(self):
        # When assembling a inquirerpy select list with separators, every separator
        # after the first is prepending with a newline operator to break up the
        # blocks of text.
        if self.current == 0:
            self.current += 1
            return ""
        else:
            return "\n"


def select_kit(target_directory: Path, config: dict) -> str:
    """Discover all kit files in `target_directory` and present user a sorted by type list of apps.

    The types are sorted per the repo.toml `repo_launch.type_ordering` list first, and then unsorted ordering afterwards.

    Args:
        target_directory (Path): path where .kit files are, typically in the _build folder.
        config (dict): repo.toml config file as a dict.

    Returns:
        str: the user selected kit application name to be launched
    """
    # Get a list of kit apps, sorted by base template type.
    type_sorted_apps = discover_typed_kit_files(target_directory)

    if len(type_sorted_apps.keys()) == 0:
        repo_cmd = Path(_get_repo_cmd()).name
        err_msg = f"There were no apps discovered in the default Kit App Path: {target_directory}. You must create an app first via `{repo_cmd} template new` and then build via `{repo_cmd} build`."
        _quiet_error(err_msg)

    elif sum(len(apps) for apps in type_sorted_apps.values()) == 1:
        # If a single app is present automatically select it.
        single_type = next(iter(type_sorted_apps))
        return type_sorted_apps[single_type][0]

    else:
        # perform a select to set app_name
        term_width, term_height = shutil.get_terminal_size()
        separator_string = int(term_width * 0.60) * "#"
        separator_iterator = SeparatorIterator()

        # Assemble the application select list.
        config_types_order = config.get("repo_launch", {}).get(
            "type_ordering", ["ApplicationTemplate", "ApplicationLayerTemplate"]
        )

        app_names = []
        unsorted_apps = []
        # First iterate over the config provided list of types.
        for app_type in config_types_order:
            if apps := type_sorted_apps.get(app_type):
                # Add the application type header in the select list
                app_names.append(Separator(f"{separator_iterator.next()}{app_type}\n{separator_string}"))
                # Add all of the applications of this time.
                app_names += apps
                # And remove this app type key
                type_sorted_apps.pop(app_type)

        # Append all the rest.
        for app_type, apps in type_sorted_apps.items():
            # Add the application type header in the select list
            app_names.append(Separator(f"{separator_iterator.next()}{app_type}\n{separator_string}"))
            # Add all of the applications of this time.
            app_names += apps

        app_name = _select("Select with arrow keys which App you would like to launch:", app_names)
        return app_name


def launch_kit(
    app_name, target_directory: Path, config: dict = {}, dev_bundle: bool = False, extra_args: List[str] = []
):
    # Some assumptions are being made on the folder structure of target_directory.
    # It should be the `_build/${host_platform}/${config}/` folder which contains entrypoint scripts
    # for the included kit apps.
    # It should contain an apps folder that contains various target kit apps.
    if app_name == None:
        # Select the kit App from the apps sub-dir.
        app_name = select_kit(target_directory / "apps", config)

    print(f"launching {app_name}!")

    # In target_directory there will be .sh/.bat scripts that launch the bundled version of kit
    # with the targeted kit app .kit file.
    app_build_path = Path(omni.repo.man.resolve_tokens(str(target_directory) + "/" + app_name + "${shell_ext}"))
    if not app_build_path.is_file():
        err_msg = f"\nDesired built Kit App: {app_name} is missing the built entrypoint script: {app_build_path}. Have you built your app via `{_get_repo_cmd()} build`?"
        _quiet_error(err_msg)

    # Enable the developer bundle
    kit_cmd = [str(app_build_path)]
    if dev_bundle:
        kit_cmd += ["--enable", "omni.kit.developer.bundle"]

    # If extra arguments were passed into launch, directly feed them into the Kit binary.
    if extra_args:
        kit_cmd += extra_args

    _ = _run_process(
        kit_cmd,
        exit_on_error=False,
    )


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


def add_args(parser: argparse.ArgumentParser):
    """Add all the argparse CLI arguments.

    Args:
        parser (argparse.ArgumentParser): main CLI parser for `repo launch`.
    """
    parser.add_argument(
        "--container",
        dest="container",
        help="Generate a Docker container image rather than package archive.",
        required=False,
        action="store_true",
    )

    parser.add_argument(
        "-d",
        "--dev-bundle",
        dest="dev_bundle",
        required=False,
        action="store_true",
        help="Enable the developer debugging extension bundle.",
    )


def add_package_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-p",
        PACKAGE_ARG,
        dest="from_package",
        required=False,
        type=str,
        help="Path to a kit app package that you want to launch",
    )


def add_name_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-n",
        "--name",
        dest="app_name",
        help="Launch the provided application. This should be the name of the .kit file e.g. `my_company.my_usd_explorer_streaming.kit`. If used `--container` this value should be the container image name you want to launch e.g. `my_container:106.0`.",
        required=False,
    )


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Optional[Callable]:
    """Entry point for 'repo_launch' tool"""

    parser.description = "Simple tool to launch Kit applications"
    add_args(parser)
    add_package_arg(parser)
    add_name_arg(parser)

    # Currently unused
    # tool_config = config.get("repo_launch", {})

    # Get list of kit apps on filesystem.
    app_names = discover_kit_files(KIT_APP_PATH)

    subparsers = parser.add_subparsers()
    for app in app_names:
        subparser = subparsers.add_parser(app)
        subparser.set_defaults(app_name=app)
        # Add --dev-bundle and --container args
        add_args(subparser)

    def run_repo_tool(options: argparse.Namespace, config_dict: Dict):
        app_name = None
        config = "release"
        dev_bundle = False

        # Providing a kit file is optional, otherwise we present a select
        app_name = options.app_name
        dev_bundle = options.dev_bundle

        try:
            # Launching from a distributed package
            console.print("\[ctrl+c to Exit]", style=INFO_COLOR)
            if options.from_package:
                package_path = expand_package(options.from_package)
                launch_kit(app_name, package_path, config_dict, dev_bundle, options.extra_args)

            # Launching a locally built application
            else:
                repo_folders = config_dict["repo"]["folders"]
                build_path = Path(repo_folders.get("build", "_build"))
                build_path = Path(f"{build_path}/{get_host_platform()}/{config}/")

                # Launch a containerized app
                if options.container:
                    if platform.system() != "Linux":
                        error_message = "Currently container launch workflows are only supported on Linux hosts."
                        print(error_message)
                        raise QuietExpectedError(error_message)
                    # Check if the host is correctly configured. We require a NVIDIA GPU to be present.
                    nvidia_driver_check()
                    launch_container(app_name, dev_bundle, options.extra_args, options.verbose)
                    return

                # Launch the thing, or query the user and then launch the thing.
                launch_kit(app_name, build_path, config_dict, dev_bundle, options.extra_args)

        except (KeyboardInterrupt, SystemExit):
            console.print("Exiting", style=INFO_COLOR)
            # exit(0) for now due to non-zero exit reporting.
            sys.exit(0)

    return run_repo_tool
