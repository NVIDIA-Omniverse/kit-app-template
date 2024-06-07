# SPDX-FileCopyrightText: Copyright (c) 2023-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#
import argparse
import logging
import os
import pathlib
import re
import sys
import zipfile
from string import Template

import omni.repo.man
from omni.repo.man import resolve_tokens
from omni.repo.man.exceptions import ExpectedError

# These dependencies come from repo_kit_template
from rich.console import Console
from rich.theme import Theme

logger = logging.getLogger(os.path.basename(__file__))

# This should match repo_kit_template.palette
INFO_COLOR = "#3A96D9"
theme = Theme()
console = Console(theme=theme)


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

    package_name = "thin_package" if options.thin else "fat_package"
    command = ["${root}/repo${shell_ext}", "_package", "-m", package_name, "-c", options.config]

    if options.name:
        package_name_check(options.name)
        command += ["--name", options.name]

    package_display_name = "thin package" if options.thin else "fat package"
    print(f"Packaging app ({package_display_name})...")

    console.print("\[ctrl+c to Exit]", style=INFO_COLOR)
    try:
        omni.repo.man.run_process(resolve_tokens(command), exit_on_error=True)
    except (KeyboardInterrupt, SystemExit):
        console.print("Exiting", style=INFO_COLOR)
        # exit(0) for now due to non-zero exit reporting.
        sys.exit(0)


def setup_repo_tool(parser, config):
    tool_config = config.get("repo_package_app", {})
    parser.description = "Tool to package an Omniverse app."
    parser.add_argument(
        "--thin",
        dest="thin",
        required=False,
        action="store_true",
        help="Produce a thin package. It can download all dependencies from the internet.",
    )

    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        help="Package name: limit to alphanumeric, period, and underscore characters",
        required=False,
    )

    omni.repo.man.add_config_arg(parser)

    # is enabled?
    enabled = tool_config.get("enabled", False)
    if not enabled:
        return None

    return run_repo_tool
