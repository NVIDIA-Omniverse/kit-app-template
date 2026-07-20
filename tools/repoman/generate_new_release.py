#!/usr/bin/env python3
"""
This repo_man script is used to generate a new release for Kit SDK Public.
It will:
1. Update Kit App Template (KAT) with a new MR for the new release:
    - Sync KAT to latest {release}/{version} branch (i.e. production/108.0)
    - Bump kit-kernel to latest (use repo update kit-kernel)
    - Update .kit lockfile lock to same kit-kernel (i.e. '# Kit SDK Version: 108.0.0+feature.215530.a50dc8a2.gl' line in the kit file)
    - Update VERSION.md files (108.0.0-stage.7 -> 108.0.0-stage.8)
    - Create an MR
2. Update kit-sdk-public (KSP):
    - Sync KSP to latest {release}/{version} branch (i.e. production/108.0)
        - This script is in the kit-sdk-public repo. While workign on this script, assume we are in a branch off of the latest {release}/{version} branch.
    - Bump kit-kernel to latest (repo update kit-kernel)
    - Update .kit lockfile lock to same kit-kernel (i.e. '# Kit SDK Version: 108.0.0+feature.215530.a50dc8a2.gl' line in the kit file)
    - Update VERSION.md files (108.0.0-stage.7 -> 108.0.0-stage.8)
    - Update repo.toml to above commit in KAT (can be before merge - assuming only diff from target branch)
    - Create an MR
3. Create MRs - post MRs in omni-dev for approvals.

Settings for the repo tool (in repo.toml):
[repo_generate_new_release]
kat_path = "C:\\Users\\<username>\\git\\kit-app-template"  # Local path to KAT repository

args for the repo tool:
- release branch (i.e. production/108.0)
- --kat-path (optional if configured in repo.toml)
- bump level is automatically detected from current VERSION.md (i.e. if current is 108.0.0-stage.10, bump level is "stage")


Additional information:
- Use repo_man tools for git operaions
- .kit files are toml files, but edits should be done with plain text changes to preserve all comments and formatting.
- when updating `kit-kernel` using `repo update kit-kernel`, the kit-sdk.packman.xml file will be updated. From this xml file we can gather the new kit version.
- Create local branch and stage commits - do not push to remote. That will be done manually FOR NOW. Creating the MR can be added later.
- If the branch cannot be synced (i.e. there are local changes), the script should fail and print the local changes.
- The script should fail if the release branch does not exist.
- The script should fail if the bump level is not valid.
- The script should fail if the repo.toml file is not found.
- The script should fail if the repo.toml file is not valid.
- The script should fail if the repo.toml file is not valid.
- actual repos are:
    - https://gitlab-master.nvidia.com/omniverse/kit-github/kit-app-template.git
    - https://gitlab-master.nvidia.com/omniverse/kit-apps/kit-sdk-public.git
- version bumping should follow pattern of {pre_release_stage}.{number} (i.e. dev.1, stage.1, rc.1)
- bumping simply increments the number (i.e. dev.1 -> dev.2, stage.1 -> stage.2, rc.1 -> rc.2)
- the script should fail if the version is not valid.
- the script should fail if the version is not valid.
- KAT commit hash would be the commit hash of the commit that was used to update the kit-kernel in first steps of the script.
- Branches, when created, should be named bump-{version}-{bump_level}.{number} (i.e. bump-108.0-dev.1)

Working directory assumptions:
- Script runs from kit-sdk-public repo root
- KAT repo should be cloned/available at the specified local path
- All KSP operations happen in current working directory
- All KAT operations happen in the external KAT repo directory
- When work on this script is complete, the script should be run from the kit-sdk-public repo root from the branch that was created for the release.
"""

import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import omni.repo.man

# Repository configuration
KAT_REPO_URL = "https://gitlab-master.nvidia.com/omniverse/kit-github/kit-app-template.git"
KSP_REPO_URL = "https://gitlab-master.nvidia.com/omniverse/kit-apps/kit-sdk-public.git"

# Valid bump levels
VALID_BUMP_LEVELS = ["dev", "stage", "rc"]

# File paths
KIT_SDK_PACKMAN_XML = "deps/kit-sdk.packman.xml"
KAT_KIT_SDK_PACKMAN_XML = "tools/deps/kit-sdk.packman.xml"  # Different path in KAT
VERSION_MD = "VERSION.md"
REPO_TOML = "repo.toml"

# Kit files that need version updates
KIT_FILES = [
    "source/apps/omni.app.editor.base.kit",
    "source/apps/omni.app.editor.full.kit",
]


class ReleaseGeneratorError(Exception):
    """Custom exception for release generation errors."""

    pass


def run_command(cmd: List[str], cwd: Optional[str] = None, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Run a command and handle errors."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=capture_output, text=True, check=True)
        return result
    except subprocess.CalledProcessError as e:
        raise ReleaseGeneratorError(f"Command failed: {' '.join(cmd)}\nError: {e.stderr if e.stderr else str(e)}")


def find_git_tracked_files(repo_path: str, pattern: str) -> List[Path]:
    """Find files matching pattern that are tracked by git (efficient approach)."""
    try:
        # Get all git-tracked files in one efficient command
        result = run_command(["git", "ls-files", f"*{pattern}"], cwd=repo_path, capture_output=True)

        repo_path_obj = Path(repo_path)
        matching_files = []

        # Parse the output and convert to Path objects
        for line in result.stdout.strip().split("\n"):
            if line.strip():  # Skip empty lines
                file_path = repo_path_obj / line.strip()
                if file_path.exists():  # Make sure file actually exists
                    matching_files.append(file_path)

        return matching_files

    except ReleaseGeneratorError:
        # Fallback: if git ls-files fails, return empty list
        print(f"Warning: Could not get git-tracked files for pattern {pattern}")
        return []


def parse_version(version_str: str) -> Tuple[str, str, int]:
    """Parse version string into components.

    Args:
        version_str: Version string like "108.0.0-stage.10"

    Returns:
        Tuple of (base_version, bump_level, number)

    Raises:
        ReleaseGeneratorError: If version format is invalid
    """
    match = re.match(r"^(\d+\.\d+\.\d+)-(\w+)\.(\d+)$", version_str)
    if not match:
        raise ReleaseGeneratorError(f"Invalid version format: {version_str}")

    base_version, bump_level, number = match.groups()
    return base_version, bump_level, int(number)


def bump_version(current_version: str) -> str:
    """Bump version number by incrementing the number for the current bump level.

    Args:
        current_version: Current version string (e.g., "108.0.0-stage.10")

    Returns:
        New version string (e.g., "108.0.0-stage.11")

    Raises:
        ReleaseGeneratorError: If version cannot be bumped
    """
    base_version, current_bump_level, current_number = parse_version(current_version)

    # Validate that the bump level is valid
    if current_bump_level not in VALID_BUMP_LEVELS:
        raise ReleaseGeneratorError(
            f"Invalid bump level '{current_bump_level}' in current version. Must be one of: {', '.join(VALID_BUMP_LEVELS)}"
        )

    new_number = current_number + 1
    return f"{base_version}-{current_bump_level}.{new_number}"


def get_kit_kernel_version() -> str:
    """Extract kit-kernel version from packman XML file."""
    xml_path = Path(KIT_SDK_PACKMAN_XML)
    if not xml_path.exists():
        raise ReleaseGeneratorError(f"Kit SDK packman file not found: {xml_path}")

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for package in root.findall(".//package"):
            if package.get("name") == "kit-kernel":
                return package.get("version")

        raise ReleaseGeneratorError("kit-kernel package not found in packman XML")
    except ET.ParseError as e:
        raise ReleaseGeneratorError(f"Failed to parse packman XML: {e}")


def extract_core_kit_version(full_version: str) -> str:
    """Extract core version without platform/config variables.

    Input: 108.0.0+feature.218394.823b724c.gl.${platform_target_abi}.${config}
    Output: 108.0.0+feature.218394.823b724c.gl
    """
    # Remove platform and config variables from the end
    core_version = full_version

    # Remove .${platform_target_abi}.${config} or similar patterns
    core_version = re.sub(r"\.?\$\{[^}]+\}", "", core_version)

    # Clean up any trailing dots
    core_version = core_version.rstrip(".")

    return core_version


def update_kit_files_version_comment(kit_version: str) -> None:
    """Update Kit SDK Version comments in .kit files (only if they already exist)."""
    core_version = extract_core_kit_version(kit_version)

    for kit_file_path in KIT_FILES:
        kit_file = Path(kit_file_path)
        if not kit_file.exists():
            print(f"Warning: Kit file not found: {kit_file_path}")
            continue

        content = kit_file.read_text()

        # Only update existing Kit SDK Version comments, don't add new ones
        version_pattern = r"# Kit SDK Version: [^\n]+"
        new_comment = f"# Kit SDK Version: {core_version}"

        if re.search(version_pattern, content):
            content = re.sub(version_pattern, new_comment, content)
            kit_file.write_text(content)
            print(f"Updated Kit SDK version comment in {kit_file_path}")
        else:
            print(f"No Kit SDK version comment found in {kit_file_path} - skipping")


def update_version_md(new_version: str) -> None:
    """Update VERSION.md file with new version."""
    version_file = Path(VERSION_MD)
    if not version_file.exists():
        raise ReleaseGeneratorError(f"VERSION.md file not found: {version_file}")

    version_file.write_text(new_version)
    print(f"Updated VERSION.md to {new_version}")


def check_git_status(repo_path: str) -> None:
    """Check if git repository has uncommitted changes."""
    result = run_command(["git", "status", "--porcelain"], cwd=repo_path, capture_output=True)
    if result.stdout.strip():
        raise ReleaseGeneratorError(f"Repository has uncommitted changes in {repo_path}:\n{result.stdout}")


def sync_to_branch(repo_path: str, branch: str) -> None:
    """Sync repository to specified branch."""
    print(f"Syncing {repo_path} to branch {branch}")

    # Check for uncommitted changes
    check_git_status(repo_path)

    # Fetch latest changes
    run_command(["git", "fetch", "origin"], cwd=repo_path)

    # Check if branch exists
    result = run_command(["git", "ls-remote", "--heads", "origin", branch], cwd=repo_path, capture_output=True)
    if not result.stdout.strip():
        raise ReleaseGeneratorError(f"Branch '{branch}' does not exist in remote repository")

    # Switch to branch
    run_command(["git", "checkout", branch], cwd=repo_path)
    run_command(["git", "pull", "origin", branch], cwd=repo_path)


def create_or_use_branch(repo_path: str, branch_name: str) -> bool:
    """Create new branch or use existing one if it exists and has no changes.

    Returns:
        True if branch was created (new), False if existing branch was used
    """
    # Check if branch already exists locally
    result = run_command(["git", "branch", "--list", branch_name], cwd=repo_path, capture_output=True)

    if result.stdout.strip():
        # Branch exists, check if it has any changes compared to the base branch
        print(f"Branch {branch_name} already exists in {repo_path}")

        # Switch to the existing branch
        run_command(["git", "checkout", branch_name], cwd=repo_path)

        # Check if there are any uncommitted changes
        status_result = run_command(["git", "status", "--porcelain"], cwd=repo_path, capture_output=True)
        if status_result.stdout.strip():
            # Be lenient for current directory (KSP) since we're developing the tool there
            if repo_path == ".":
                print(f"Warning: Branch {branch_name} has uncommitted changes in current repo, but continuing...")
            else:
                raise ReleaseGeneratorError(
                    f"Branch {branch_name} exists but has uncommitted changes in {repo_path}. "
                    f"Please commit or stash changes before running the tool."
                )

        print(f"Using existing branch {branch_name}")
        return False
    else:
        # Branch doesn't exist, create it
        print(f"Creating branch {branch_name} in {repo_path}")
        run_command(["git", "checkout", "-b", branch_name], cwd=repo_path)
        return True


def commit_changes(repo_path: str, message: str) -> str:
    """Commit staged changes and return commit hash. Returns existing hash if no changes."""
    # Check if there are any changes to commit
    status_result = run_command(["git", "status", "--porcelain"], cwd=repo_path, capture_output=True)
    if not status_result.stdout.strip():
        print(f"No changes to commit in {repo_path}")
        result = run_command(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True)
        return result.stdout.strip()

    run_command(["git", "add", "."], cwd=repo_path)
    run_command(["git", "commit", "-m", message], cwd=repo_path)

    result = run_command(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True)
    return result.stdout.strip()


def update_repo_toml_kat_commit(kat_commit_hash: str) -> None:
    """Update repo.toml with KAT commit hash."""
    repo_toml_path = Path(REPO_TOML)
    if not repo_toml_path.exists():
        raise ReleaseGeneratorError(f"repo.toml not found: {repo_toml_path}")

    content = repo_toml_path.read_text()

    # Look for KAT commit configuration and update it
    # This is a simplified approach - in a real implementation, you'd want to parse TOML properly
    # But per requirements, we should do plain text changes to preserve formatting
    kat_commit_pattern = r'(commit\s*=\s*")[^"]+(".*# KAT commit)'
    replacement = r"\g<1>" + kat_commit_hash + r"\g<2>"

    if re.search(kat_commit_pattern, content):
        content = re.sub(kat_commit_pattern, replacement, content)
        repo_toml_path.write_text(content)
        print(f"Updated KAT commit hash in repo.toml to {kat_commit_hash}")
    else:
        print("Warning: Could not find KAT commit configuration in repo.toml")


def update_kit_kernel_ksp() -> str:
    """Update kit-kernel in KSP and return new version."""
    print("Updating kit-kernel in Kit SDK Public...")

    # Use repo tool to update kit-kernel
    repo_script = "repo.bat" if os.name == "nt" else "repo.sh"
    run_command([repo_script, "update", "kit-kernel"])

    # Get the new kit-kernel version
    kit_version = get_kit_kernel_version()
    print(f"Updated kit-kernel to version: {kit_version}")

    return kit_version


def update_kit_kernel_kat(kat_path: str, ksp_kit_version: str) -> str:
    """Update kit-kernel in KAT to match KSP version."""
    print("Updating kit-kernel in Kit App Template...")

    # KAT has packman file in tools/deps instead of deps
    kat_packman_xml = Path(kat_path) / KAT_KIT_SDK_PACKMAN_XML
    if not kat_packman_xml.exists():
        raise ReleaseGeneratorError(f"KAT packman file not found: {kat_packman_xml}")

    try:
        tree = ET.parse(kat_packman_xml)
        root = tree.getroot()

        # Find and update kit-kernel package version
        kit_kernel_found = False
        for package in root.findall(".//package"):
            if package.get("name") == "kit-kernel":
                old_version = package.get("version")
                package.set("version", ksp_kit_version)
                kit_kernel_found = True
                print(f"Updated KAT kit-kernel from {old_version} to {ksp_kit_version}")
                break

        if not kit_kernel_found:
            raise ReleaseGeneratorError("kit-kernel package not found in KAT packman XML")

        # Save the updated XML
        tree.write(kat_packman_xml, encoding="utf-8", xml_declaration=True)
        print(f"Updated kit-kernel in KAT to version: {ksp_kit_version}")
        return ksp_kit_version

    except ET.ParseError as e:
        raise ReleaseGeneratorError(f"Failed to parse KAT packman XML: {e}")


def process_kat_repo(kat_path: str, release_branch: str, new_version: str, ksp_kit_version: str) -> str:
    """Process KAT repository updates and return commit hash."""
    print(f"Processing KAT repository at {kat_path}")

    if not Path(kat_path).exists():
        raise ReleaseGeneratorError(f"KAT repository not found at {kat_path}")

    # Sync to release branch
    sync_to_branch(kat_path, release_branch)

    # Create new branch or use existing one
    base_version, bump_level, number = parse_version(new_version)
    branch_name = f"bump-{base_version}-{bump_level}.{number}"
    branch_created = create_or_use_branch(kat_path, branch_name)

    # Update kit-kernel to match KSP version
    kat_kit_version = update_kit_kernel_kat(kat_path, ksp_kit_version)

    # Find and update specific .kit file in KAT (only omni.all.template.extensions.kit)
    print("Searching for omni.all.template.extensions.kit file in KAT repository...")
    kat_kit_files = find_git_tracked_files(kat_path, "*.kit")

    target_kit_file = None
    kat_path_obj = Path(kat_path)

    for kit_file in kat_kit_files:
        if "omni.all.template.extensions" in kit_file.name:
            target_kit_file = kit_file
            print(f"Found target .kit file: {kit_file.relative_to(kat_path_obj)}")
            break

    if target_kit_file:
        # Update Kit SDK version comment in the specific .kit file
        core_kat_version = extract_core_kit_version(kat_kit_version)

        try:
            content = target_kit_file.read_text()

            version_pattern = r"# Kit SDK Version: [^\n]+"
            new_comment = f"# Kit SDK Version: {core_kat_version}"

            if re.search(version_pattern, content):
                content = re.sub(version_pattern, new_comment, content)
                target_kit_file.write_text(content)
                print(f"Updated Kit SDK version comment in KAT {target_kit_file.relative_to(kat_path_obj)}")
            else:
                print(f"No Kit SDK version comment found in KAT {target_kit_file.relative_to(kat_path_obj)} - skipping")
        except Exception as e:
            print(f"Warning: Could not update {target_kit_file.relative_to(kat_path_obj)}: {e}")
    else:
        print("omni.all.template.extensions.kit file not found in KAT repository")

    # Find and update ALL VERSION.md files in git-tracked files
    version_files = find_git_tracked_files(kat_path, "VERSION.md")

    if version_files:
        kat_path_obj = Path(kat_path)
        print(f"Found {len(version_files)} VERSION.md files in KAT repository:")

        for version_file in version_files:
            print(f"  - {version_file.relative_to(kat_path_obj)}")

        # Update ALL VERSION.md files with smart version replacement
        for version_file in version_files:
            try:
                current_content = version_file.read_text().strip()

                # Try to parse the current version to determine what format to use
                try:
                    current_base, current_bump, current_num = parse_version(current_content)
                    # If it parses successfully, it has pre-release format, use new_version
                    version_file.write_text(new_version)
                    print(
                        f"Updated KAT VERSION.md: {version_file.relative_to(kat_path_obj)} from '{current_content}' to '{new_version}'"
                    )
                except ReleaseGeneratorError:
                    # If parsing fails, it might be a simple version like "108.0.0"
                    # Extract just the base version part (e.g., "108.0.0" from "108.0.0-stage.11")
                    new_base_version = parse_version(new_version)[0]  # Gets "108.0.0"

                    # Check if current content looks like a simple version (x.y.z format)
                    if re.match(r"^\d+\.\d+\.\d+$", current_content):
                        version_file.write_text(new_base_version)
                        print(
                            f"Updated KAT VERSION.md: {version_file.relative_to(kat_path_obj)} from '{current_content}' to '{new_base_version}' (base version only)"
                        )
                    else:
                        # Unknown format, skip to be safe
                        print(
                            f"Skipping KAT VERSION.md: {version_file.relative_to(kat_path_obj)} - unknown format '{current_content}'"
                        )

            except Exception as e:
                print(f"Warning: Could not update {version_file.relative_to(kat_path_obj)}: {e}")
    else:
        # Create VERSION.md in root if none exists
        print("No git-tracked VERSION.md found in KAT repository - creating one in root")
        kat_version_md = Path(kat_path) / VERSION_MD
        kat_version_md.write_text(new_version)
        print(f"Created KAT VERSION.md with version {new_version}")

    # Commit changes
    core_kat_version = extract_core_kit_version(kat_kit_version)
    commit_message = f"Bump version to {new_version} and update kit-kernel to {core_kat_version}"
    commit_hash = commit_changes(kat_path, commit_message)

    if branch_created:
        print(f"Created KAT commit: {commit_hash}")
    else:
        print(f"KAT commit (existing or updated): {commit_hash}")
    return commit_hash


def process_ksp_repo_finish(release_branch: str, new_version: str, kat_commit_hash: str, kit_version: str) -> None:
    """Finish processing KSP (current) repository updates."""
    print("Finishing Kit SDK Public repository updates...")

    # Skip git status check for KSP since we're actively developing the tool here
    # and it's normal to have uncommitted changes

    # Create new branch or use existing one
    base_version, bump_level, number = parse_version(new_version)
    branch_name = f"bump-{base_version}-{bump_level}.{number}"
    branch_created = create_or_use_branch(".", branch_name)

    # Update .kit files with new Kit SDK version
    update_kit_files_version_comment(kit_version)

    # Update VERSION.md
    update_version_md(new_version)

    # Update repo.toml with KAT commit hash
    update_repo_toml_kat_commit(kat_commit_hash)

    # Commit changes
    core_kit_version = extract_core_kit_version(kit_version)
    commit_message = (
        f"Bump version to {new_version}, update kit-kernel to {core_kit_version}, and update KAT to {kat_commit_hash}"
    )
    commit_hash = commit_changes(".", commit_message)

    if branch_created:
        print(f"Created KSP commit: {commit_hash}")
    else:
        print(f"KSP commit (existing or updated): {commit_hash}")


def validate_arguments(release_branch: str) -> None:
    """Validate command line arguments."""
    # Validate release branch format (e.g., production/108.0)
    if not re.match(r"^[a-zA-Z_-]+/\d+\.\d+$", release_branch):
        raise ReleaseGeneratorError(f"Invalid release branch format: {release_branch}")


def run_repo_tool(options: argparse.Namespace, config: Dict):
    """Main entry point for repo tool integration."""
    try:
        # Validate arguments
        validate_arguments(options.release_branch)

        # Validate that we're in the KSP repository root
        if not Path(REPO_TOML).exists():
            raise ReleaseGeneratorError(f"repo.toml not found. Please run from kit-sdk-public repository root.")

        # Get KAT path from config or command line
        tool_config = config.get("repo_generate_new_release", {})
        kat_path = getattr(options, "kat_path", None) or tool_config.get("kat_path", "")

        if not kat_path:
            raise ReleaseGeneratorError(
                "KAT path not specified. Either:\n"
                "1. Set kat_path in [repo_generate_new_release] section of repo.toml, or\n"
                "2. Use --kat-path command line argument"
            )

        if not Path(kat_path).exists():
            raise ReleaseGeneratorError(f"KAT repository not found at: {kat_path}")

        print(f"Using KAT repository at: {kat_path}")

        # Read current version and auto-detect bump level
        version_file = Path(VERSION_MD)
        if not version_file.exists():
            raise ReleaseGeneratorError(f"VERSION.md not found")

        current_version = version_file.read_text().strip()
        base_version, current_bump_level, current_number = parse_version(current_version)
        new_version = bump_version(current_version)

        print(f"Auto-detected bump level: {current_bump_level}")
        print(f"Bumping version from {current_version} to {new_version}")

        # Update kit-kernel in KSP first to get the version
        kit_version = update_kit_kernel_ksp()

        # Process KAT repository with the KSP kit version
        kat_commit_hash = process_kat_repo(kat_path, options.release_branch, new_version, kit_version)

        # Process KSP repository (finish the KSP updates)
        process_ksp_repo_finish(options.release_branch, new_version, kat_commit_hash, kit_version)

        print("\n" + "=" * 60)
        print("SUCCESS: Release generation completed!")
        print("=" * 60)
        print(f"Bump level: {current_bump_level}")
        print(f"New version: {new_version}")
        print(f"KAT commit: {kat_commit_hash}")
        print("\nNext steps:")
        print("1. Review the changes in both repositories")
        print("2. Push the branches to remote repositories")
        print("3. Create merge requests for approval")
        print("=" * 60)

    except ReleaseGeneratorError as e:
        raise omni.repo.man.RepoToolError(f"Release generation failed: {e}")
    except KeyboardInterrupt:
        raise omni.repo.man.RepoToolError("Operation cancelled by user")
    except Exception as e:
        raise omni.repo.man.RepoToolError(f"Unexpected error: {e}")


def setup_parser(parser: argparse.ArgumentParser, config: Optional[Dict] = None) -> None:
    """Configure argument parser with common arguments."""
    parser.description = "Generate new release for Kit SDK Public (auto-detects bump level from VERSION.md)"

    parser.add_argument("release_branch", help="Release branch to sync to (e.g., production/108.0)")

    # Determine if --kat-path is required based on config
    if config:
        tool_config = config.get("repo_generate_new_release", {})
        config_kat_path = tool_config.get("kat_path", "")
        kat_path_required = not bool(config_kat_path)
        kat_path_help = f"Local path to KAT repository{' (overrides config)' if config_kat_path else ''}"
    else:
        # For standalone mode, always require --kat-path
        kat_path_required = True
        kat_path_help = "Local path to KAT repository"

    parser.add_argument("--kat-path", required=kat_path_required, help=kat_path_help)


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Optional[Callable]:
    """Entry point for 'repo generate_new_release' tool."""
    setup_parser(parser, config)
    return run_repo_tool


def main():
    """Standalone entry point for direct script execution."""
    parser = argparse.ArgumentParser()
    setup_parser(parser)  # No config for standalone mode

    args = parser.parse_args()

    try:
        # Call the repo tool function directly (with empty config for standalone mode)
        run_repo_tool(args, {})

    except omni.repo.man.RepoToolError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
