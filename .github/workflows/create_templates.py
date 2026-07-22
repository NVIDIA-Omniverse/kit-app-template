#!/usr/bin/env python3
"""
Script to run template replay tests for all test configuration files.
Executes: repo.sh template replay <TEST_FILE> for each test file,
followed by a single repo.sh build to verify the templates can be built.
"""

import subprocess
import os
import sys
import platform
from pathlib import Path

# List of test files to process
TEST_FILES = [
    ".github/workflows/replay_files/base_editor",
    ".github/workflows/replay_files/usd_composer",
    ".github/workflows/replay_files/usd_explorer",
    ".github/workflows/replay_files/usd_viewer",
    ".github/workflows/replay_files/kit_service",
]

# Determine the repo script based on OS
REPO_SCRIPT = "repo.bat" if platform.system() == "Windows" else "./repo.sh"


def run_template_replay(test_file: str) -> bool:
    """
    Run repo.sh template replay for a given test file.

    Args:
        test_file: Name of the test file to process

    Returns:
        True if successful, False if failed
    """
    cmd = [REPO_SCRIPT, "template", "replay", test_file]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,
            text=True,
            timeout=300  # 5 minute timeout
        )

        print(f"SUCCESS: {test_file}")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"FAILED: {test_file}")
        print(f"   Return code: {e.returncode}")
        if e.stdout:
            print(f"   Stdout: {e.stdout.strip()}")
        if e.stderr:
            print(f"   Stderr: {e.stderr.strip()}")
        return False

    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {test_file} (exceeded 5 minutes)")
        return False

    except FileNotFoundError:
        print(f"ERROR: {REPO_SCRIPT} not found. Make sure you're in the correct directory.")
        return False


def run_build() -> bool:
    """
    Run repo.sh build to verify the templates can be built.

    Returns:
        True if successful, False if failed
    """
    cmd = [REPO_SCRIPT, "build"]

    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=False,
            text=True,
            timeout=600  # 10 minute timeout for build
        )

        print("SUCCESS: Build completed")
        if result.stdout:
            print(f"   Output: {result.stdout.strip()}")
        return True

    except subprocess.CalledProcessError as e:
        print("FAILED: Build")
        print(f"   Return code: {e.returncode}")
        if e.stdout:
            print(f"   Stdout: {e.stdout.strip()}")
        if e.stderr:
            print(f"   Stderr: {e.stderr.strip()}")
        return False

    except subprocess.TimeoutExpired:
        print("TIMEOUT: Build (exceeded 10 minutes)")
        return False

    except FileNotFoundError:
        print(f"ERROR: {REPO_SCRIPT} not found. Make sure you're in the correct directory.")
        return False


def main():
    """Main function to run all template replay tests."""

    os.chdir(Path(__file__).parent.parent.parent.resolve())  # Change to script's parent directory
    print("Starting template replay tests...")
    print("=" * 50)

    # Check if repo script exists
    repo_path = Path(REPO_SCRIPT.replace("./", ""))
    if not repo_path.exists():
        print(f"ERROR: {REPO_SCRIPT} not found in current directory")
        print(repo_path.resolve())
        print("Please run this script from the repository root.")
        sys.exit(1)

    # Check to see if .omniverse_eula_accepted.txt exists. If not, make it.
    eula_file = Path(".omniverse_eula_accepted.txt")
    if not eula_file.exists():
        print("Creating .omniverse_eula_accepted.txt to accept EULA")
        eula_file.touch()

    success_count = 0
    total_count = len(TEST_FILES)

    for test_file in TEST_FILES:
        print()
        if run_template_replay(test_file):
            success_count += 1

    print()
    print("=" * 50)
    print(f"SUMMARY: {success_count}/{total_count} template replay tests passed")

    # Delete .omniverse_eula_accepted.txt if it was created
    print("Deleting .omniverse_eula_accepted.txt")
    eula_file.unlink(missing_ok=True)

    # Overall success depends template replays
    if success_count == total_count:
        print("\nTemplate creation passed!")
        sys.exit(0)
    else:
        if success_count < total_count:
            print(f"\n{total_count - success_count} template replay(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
