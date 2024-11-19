# SPDX-FileCopyrightText: Copyright (c) 2023-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#
import argparse
import logging
import os
import pathlib
import re
import shutil
import sys
import time
from glob import glob
from string import Template
from tempfile import TemporaryDirectory
from typing import List

import omni.repo.man
from omni.repo.kit_template.frontend.template_tool import CLIInput
from omni.repo.man import resolve_tokens
from omni.repo.man.exceptions import QuietExpectedError, StorageError
from omni.repo.man.utils import change_cwd

# These dependencies come from repo_kit_template
from rich.console import Console
from rich.theme import Theme

logger = logging.getLogger(os.path.basename(__file__))

# This should match repo_kit_template.palette
INFO_COLOR = "#3A96D9"
WARN_COLOR = "#FFD700"

theme = Theme()
console = Console(theme=theme)

# temporary values, these might come from repo.toml or something
DOCKERFILE = pathlib.Path("tools/containers/Dockerfile.j2")
ENTRYPOINT_DEFAULT = pathlib.Path("tools/containers/entrypoint.sh.j2")
ENTRYPOINT_MEMCACHED = pathlib.Path("tools/containers/entrypoint_memcached.sh.j2")
STREAM_SDK_TIMEOUT = pathlib.Path("tools/containers/stream_sdk.txt")
KIT_ARGS = pathlib.Path("tools/containers/kit_args.txt")

# Breadcrumb temporarily used to replace .kit name until
# jinja2 templating is done for the entrypoint.sh.
KIT_FILE_NAME_BREADCRUMB = "KIT_FILE_NAME_BREADCRUMB"
KIT_ARGS_BREADCRUMB = "KIT_ARGS_BREADCRUMB"

DEFAULT_ARCHIVE_NAME = "kit-app-template"


def _get_repo_cmd():
    repo_cmd = "${root}/repo${shell_ext}"
    return omni.repo.man.resolve_tokens(repo_cmd)


def _quiet_error(err_msg: str):
    # Need something like QuietExpectedError that just prints and exits 1.
    print(err_msg)
    raise QuietExpectedError(err_msg)


def _run_command(command):
    console.print("\[ctrl+c to Exit]", style=INFO_COLOR)
    try:
        omni.repo.man.run_process(resolve_tokens(command), exit_on_error=True)
    except (KeyboardInterrupt, SystemExit):
        console.print("Exiting", style=INFO_COLOR)
        # exit(0) for now due to non-zero exit reporting.
        sys.exit(0)


def package_container(options: argparse.Namespace, config: dict, build_path: pathlib.Path):
    """Package up a kit application into a Docker container.

    Args:
        options (argparse.Namespace): CLI args
        config (dict): repo.toml configuration
        build_path (pathlib.Path): Path to the _build directory
    """
    container_name = options.name or "kit_app_template"

    # Target a specific kit file
    target_kit = options.target_app
    if not target_kit:
        target_kit = select_kit(build_path, options.config)
    print(f"Packaging up app: {target_kit} in a container.")

    with TemporaryDirectory() as tmpdir:
        # repo_package but stage the package in a tmpdir.
        console.print(f"Staging fat package in tempdir: {tmpdir}")
        package_subdir = tmpdir + "/package"
        # Fat package into a tempdir to pull everything needed to run Kit
        # into a directory we can shove into the Docker build context.
        command = [
            "${root}/repo${shell_ext}",
            "_package",
            "-m",
            "fat_package",
            "-c",
            options.config,
            f"--temp-dir={package_subdir}",
            "--stage-only",
        ]
        _run_command(command)

        # Copy over the Dockerfile, set the kit_file_name label via _in_place_replace
        tmpdir_dockerfile = pathlib.Path(tmpdir + "/" + DOCKERFILE.with_suffix("").name)
        shutil.copy(DOCKERFILE.resolve(), tmpdir_dockerfile)
        replacements = {
            KIT_FILE_NAME_BREADCRUMB: target_kit,
        }
        _in_place_replace(tmpdir_dockerfile, replacements)

        # Render out our entrypoint templates
        for file in [ENTRYPOINT_MEMCACHED, ENTRYPOINT_DEFAULT]:
            # path to entrypoint template within staging directory:
            tmpdir_entrypoint = pathlib.Path(tmpdir + "/" + file.with_suffix("").name)
            shutil.copy(file.resolve(), tmpdir_entrypoint)

            # Tokens that will be replaced in the entrypoint template.
            replacements = {
                KIT_FILE_NAME_BREADCRUMB: target_kit,
                KIT_ARGS_BREADCRUMB: KIT_ARGS.read_text(),
            }

            # In-place replace the known tokens
            _in_place_replace(tmpdir_entrypoint, replacements)

        # Stream-SDK needs a timeout set a bit higher for now.
        shutil.copy(STREAM_SDK_TIMEOUT.resolve(), tmpdir)

        # Now build the container image.
        # Set repo_diagnostic to map in stdin to prevent docker build from complaining.
        os.environ["repo_diagnostic"] = "1"
        console.print(f"Packaging container image with Docker within tempdir: {tmpdir}")
        with change_cwd(tmpdir):
            docker_command = [
                "docker",
                "build",
                "-t",
                container_name,
                ".",
            ]
            _run_command(docker_command)


def _in_place_replace(file: pathlib.Path, replacements: dict):
    """Swap out tokens within `file` with values defined in `replacements`

    Args:
        file (pathlib.Path): Path to template to be modified.
        replacements (dict): dict of replacement tokens and associated values.
    """
    contents = file.read_text()
    template = Template(contents)
    result = template.substitute(replacements)
    file.write_text(result)


def _select(apps: list) -> str:
    cli_input = CLIInput()
    return cli_input.select(
        message="Select with arrow keys which App would you like to containerize:", choices=apps, default=apps[0]
    )


def discover_kit_files(target_directory: pathlib.Path) -> List:
    if not target_directory.is_dir():
        return []

    discovered_app_names = []
    for app in glob("**/*.kit", root_dir=target_directory, recursive=True):
        app_path = pathlib.Path(app)
        app_name = app_path.name
        discovered_app_names.append(app_name)

    return discovered_app_names


def _apps_folder(build_directory: pathlib.Path, config: str) -> pathlib.Path:
    """Cobble together the expected build directory apps sub-directory path.

    Args:
        build_directory (pathlib.Path): Typically _build within the root directory.
        config (str): release or debug

    Returns:
        pathlib.Path: expected path where repo_build shoves Kit apps based on the default repo_build Premake lua boilerplate code.
    """
    return pathlib.Path(omni.repo.man.resolve_tokens(f"{build_directory}/${{platform}}/{config}/apps"))


def select_kit(target_directory: pathlib.Path, config: str) -> str:
    """Discover the .kit files in the _build apps folder and let the user select which they want.

    Args:
        target_directory (pathlib.Path): Typically the _build directory.
        config (str): release or debug

    Returns:
        str: The .kit file the user selected.
    """
    # Get list of kit apps on filesystem.
    apps_folder = _apps_folder(target_directory, config)
    app_names = discover_kit_files(apps_folder)
    if len(app_names) == 0:
        repo_cmd = pathlib.Path(_get_repo_cmd()).name
        err_msg = f"There were no apps discovered in the default Kit App Path: {apps_folder}. You must create an app first via `{repo_cmd} template new` and then build via `{repo_cmd} build`."
        _quiet_error(err_msg)
    else:
        # perform a select to set app_name
        app_name = _select(app_names)
        return app_name


def package_name_check(package_name: str):
    ALPHANUM_PERIOD_REGEX = r"^[A-Za-z0-9._]+(?<!\.)$"
    if re.match(ALPHANUM_PERIOD_REGEX, package_name):
        return
    print(
        f"package --name input '{package_name}' : Invalid - name is limited to alphanumeric, period, and underscore characters."
    )
    sys.exit(0)


def run_repo_tool(options, config):
    repo_folders = config["repo"]["folders"]
    root = repo_folders["root"]

    # build folder:
    build_path = pathlib.Path(repo_folders.get("build", "_build"))
    repo_cmd = pathlib.Path(_get_repo_cmd()).name
    if not build_path.exists():
        # Short circuit out cleanly if the user has not built their app yet.
        error_message = f"The expected build directory: {build_path} is not present. You must build your app first via `{repo_cmd} build`."
        _quiet_error(error_message)

    if options.container:
        # Short circuit to the containerization path.
        package_container(options, config, build_path)
        return

    package_name = "thin_package" if options.thin else "fat_package"
    command = ["${root}/repo${shell_ext}", "_package", "-m", package_name, "-c", options.config]

    if options.name:
        package_name_check(options.name)
        command += ["--name", options.name]
    else:
        # If --name is not provided and the archive name is the default, emit an
        # alert informing the user they can change it.
        config_archive_name = config["repo"].get("name")
        if config_archive_name == DEFAULT_ARCHIVE_NAME:
            warning_message = f"The default package name {DEFAULT_ARCHIVE_NAME} has not been changed. You can change this value by changing the `repo.name` value within your repo.toml configuration file or by passing in the `--name` argument to `{repo_cmd} package`."
            console.print(warning_message, style=WARN_COLOR)
            # 1 second sleep so this message is visible before repo_package scrolls the console
            # with packaging information.
            time.sleep(1)

    # Pass the key/value to the package command.
    # They are appended from build.py
    for arg in config["argv_backup"]:
        if arg.startswith("--/"):
            command.append(arg)

    package_display_name = "thin package" if options.thin else "fat package"
    print(f"Packaging app ({package_display_name})...")

    _run_command(command)


def setup_repo_tool(parser, config):
    tool_config = config.get("repo_package_app", {})
    parser.description = "Tool to package an Omniverse app."

    parser.add_argument(
        "--container",
        dest="container",
        help="Generate a Docker container image rather than package archive.",
        required=False,
        action="store_true",
    )

    parser.add_argument(
        "--target-app",
        dest="target_app",
        help="Optional target Kit app to be fed into container entrypoint. This is the filename located in source/apps/ e.g. `my_company.my_usd_explorer_streaming.kit`. To be used with `--container`.",
        required=False,
    )

    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        help="Package name: limited to alphanumeric, period, and underscore characters. When used with `--container` this value is fed into `docker build` as the value for `--tag` e.g. `my_container:106.0`",
        required=False,
    )

    parser.add_argument(
        "--thin",
        dest="thin",
        required=False,
        action="store_true",
        help="Produce a thin package. It can download all dependencies from the Internet.",
    )

    omni.repo.man.add_config_arg(parser)

    # is enabled?
    enabled = tool_config.get("enabled", False)
    if not enabled:
        return None

    return run_repo_tool
