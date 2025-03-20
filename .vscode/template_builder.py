"""
Tool to pair down a K-A-T binary artifact to only the extensions
that need license and malware scanning.
"""

import argparse
from pathlib import Path
import platform
import subprocess
import sys

TEMPLATES_TOML_PARTIAL_PATH = Path("templates", "templates.toml")
SHELL_EXT = "sh" if platform.system() == "Linux" else "bat"


def _template_new_all(repo_path: Path) -> None:
    """Creates all K-A-T templates"""

    print("\n----------------------------------------------------------------------------------------")
    print("*** Creating all templates...")
    print("----------------------------------------------------------------------------------------\n")

    company = "my_company"
    commands = (
        f"--input=Application>;[kit_base_editor]: Kit Base Editor;{company}.kit_base_editor;DEFAULT;DEFAULT",
        f"--input=Application>;[omni_usd_composer]: USD Composer;{company}.usd_composer;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT",
        f"--input=Application>;[omni_usd_explorer]: USD Explorer;{company}.usd_explorer;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT",
        f"--input=Application>;[omni_usd_viewer]: USD Viewer;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT",
        f"--input=Application>;[kit_service]: Kit Service;{company}.kit_service;DEFAULT;DEFAULT;DEFAULT;DEFAULT;DEFAULT",
        f"--input=Extension>;[basic_python_extension]: Basic Python Extension;{company}.basic_python_extension;DEFAULT;DEFAULT",
        f"--input=Extension>;[basic_cpp_extension]: Basic C++ Extension;{company}.basic_cpp_extension;DEFAULT;DEFAULT",
        f"--input=Extension>;[basic_python_ui_extension]: Python UI Extension;{company}.basic_python_ui_extension;DEFAULT;DEFAULT",
    )

    for cmd in commands:
        repo_args = [
            f"{repo_path}",  # shell ext has already been appended.
            "template",
            "new",
            f"{cmd}",
        ]
        subprocess.run(repo_args, check=False)


def create_and_build_templates(
        arg_parser: argparse.ArgumentParser,
        source_dir: Path) -> None:
    """
    Creates all K-A-T templates and builds them.
    """

    repo_path = source_dir.joinpath(f"repo.{SHELL_EXT}")
    if not repo_path.exists():
        arg_parser.error(
            "Could not find the repo shell script in the provided Kit-App-Template repository. Exiting."
        )
        sys.exit(1)

    _template_new_all(repo_path)

    print("\n----------------------------------------------------------------------------------------")
    print("*** Building all applications and extensions...")
    print("----------------------------------------------------------------------------------------\n")
    subprocess.run([f"{repo_path}", "build"], check=False)


def is_valid_kat_repo(arg_parser: argparse.ArgumentParser, arg: Path) -> bool:
    """
    Determines if the provided Path points to a valid Kit-App-Template repo.
    """

    if not arg.exists():
        arg_parser.error(f"The path {arg} does not exist. Exiting.")
        return False
    if not arg.joinpath(TEMPLATES_TOML_PARTIAL_PATH).exists():
        arg_parser.error(
            f"The path {arg} does not appear to be a Kit-App-Template repository. Exiting."
        )
        return False
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="This will create all templates, build them, and optionally run all unit tests for them."
    )

    parser.add_argument(
        "--source_dir",
        "-k",
        type=Path,
        default=Path.cwd(),
        help="An absolute path to your locally cloned Kit-App-Template repository.",
        dest="source_dir",
        nargs=1
    )

    args = parser.parse_args()

    if not is_valid_kat_repo(parser, args.source_dir):
        print("This tool can only process Kit-App-Template repositories. Exiting...")
        sys.exit(1)

    create_and_build_templates(parser, args.source_dir)

    print("\n----------------------------------------------------------------------------------------")
    print("*** Done! ***")
    print("----------------------------------------------------------------------------------------")
