import argparse
import contextlib
import functools
import json
import logging
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Dict, Optional

import omni.repo.man
import toml
from omni.repo.man import change_cwd, get_token, process_args_to_cmd, resolve_tokens, run_process
from omni.repo.man.fileutils import rmtree
from omni.repo.man.utils import call_with_retry

logger = logging.getLogger(__name__)

KAT_SDK_FILE_PATH = "tools/deps/kit-sdk.packman.xml"
KIT_SDK_USER_FILE_PATH = "tools/deps/kit-sdk.packman.xml.user"
REPO_CACHE_FILE = "repo-cache.json"

# Load tomlkit
from omni.repo.man.deps import validate_dependencies

validate_dependencies(
    Path(__file__),
    tool_name="post_build",
    requirements_file=Path(__file__).parent / "requirements.txt",
    strict_deps=True,
)
from tomlkit import TOMLDocument, dumps, parse


def read_toml(toml_file: Path) -> TOMLDocument:
    """Using tomlkit injest the toml_file in a format preserving manner.

    Args:
        toml_file (Path): Path to the toml file to read.

    Returns:
        TOMLDoctument: A format preserving object.
    """
    if toml_file.is_file():
        content = ""
        with open(toml_file, "r") as file:
            content = file.read()
        config = parse(content)
        return config

    raise Exception(f"Target file: {toml_file} does not exist, cannot read it.")


def write_toml(toml_file: Path, content: TOMLDocument):
    """Using tomlkit, write out the toml_file while preserving its format.

    Args:
        toml_file (Path): Path to the toml file we want to write out.
        content (TOMLDocument): The formatted TOML contents to be written to disk.
    """
    toml_file.write_text(dumps(content))


def write_repo_cache_json(root, cache_root):
    cache_dir = f"{cache_root}/_cache" if cache_root else "_cache"
    cache_config = {
        "PIP_CACHE_DIR": f"{cache_dir}/pip",
        "UV_CACHE_DIR": f"{cache_dir}/uv",
        "PM_PACKAGES_ROOT": f"{cache_dir}/packman",
    }
    with open(os.path.join(root, REPO_CACHE_FILE), "w") as f:
        json.dump(cache_config, f, indent=4)


def get_or_set_kit_kernel_version(deps_file: Path, new_version: Optional[str] = None) -> str:
    """Get or set kit-kernel version in a deps file.

    Args:
        deps_file: Path to the deps file
        new_version: If provided, sets the kit-kernel version to this value

    Returns:
        The current (or newly set) kit-kernel version

    Raises:
        ValueError: If kit-kernel package is not found in deps file
    """
    tree = ET.parse(deps_file)
    root = tree.getroot()

    # Find all package elements and check their names
    for package in root.findall(".//package"):
        if package.get("name") == "kit-kernel":
            if new_version is not None:
                package.set("version", new_version)
                tree.write(deps_file, encoding="utf-8", xml_declaration=True)
            return package.get("version")

    # If not found, log error and raise exception
    logger.error(f"Could not find kit-kernel package in {deps_file}")
    logger.debug("Found packages:")
    for package in root.findall(".//package"):
        logger.debug(f"  - {package.get('name')}")
    raise ValueError(f"Missing kit-kernel package in {deps_file}")


def registry_mapping(config: dict) -> dict:
    """Get the registry mappings from repo.toml"""
    registry_mapping = config.get("registry_mapping", None)
    if registry_mapping is None:
        raise ValueError("No [registry_mapping] in config!")
    return registry_mapping


def registry_mapping_phase(registry_mapping: dict) -> str:
    """Get current phase from version pre-release tag."""
    version = get_version()
    for phase in registry_mapping.keys():
        if phase.lower() in version.lower():
            return phase
    raise ValueError(f"{version} matches no phase in {registry_mapping}")


@functools.lru_cache()
def get_version() -> str:
    """Get the version from VERSION.md"""
    version_file = Path(resolve_tokens("${root}/VERSION.md"))
    return version_file.read_text().strip()


def update_kit_core_json(config: dict):
    """During stage phase, override the kit-core registry settings."""
    registries_map = registry_mapping(config)
    phase = registry_mapping_phase(registries_map)
    if not phase == "stage":
        return

    staging_registry_list = registries_map[phase]["registries"]

    kit_core_json = process_path("${root}/_build/${platform}/${config}/kernel/config/kit-core.json")
    with open(kit_core_json, "r") as f:
        kit_core_data = json.load(f)
    kit_core_data["exts"]["omni.kit.registry.nucleus"]["registries"] = staging_registry_list

    external_build = kit_core_data["privacy"]["externalBuild"]
    if not external_build:
        logger.warning("External Build is not set to true in kit-core.json, setting to true!")
        kit_core_data["privacy"]["externalBuild"] = True

    with open(kit_core_json, "w") as f:
        json.dump(kit_core_data, f, indent=4)


def public_packman_config(dev_dir: str):
    """Update packman config for public. (remove urm)"""
    packman_config = os.path.join(dev_dir, "tools", "packman", "config.packman.xml")
    with open(packman_config, "w") as f:
        f.write("""
<config remotes="cloudfront">
    <remote2 name="cloudfront">
        <transport actions="download" protocol="https" packageLocation="d4i3qtqj3r0z5.cloudfront.net/${name}@${version}" />
    </remote2>
</config>
""")


def precache_airgap_extensions(dev_dir):
    PRECACHE_DIR_NAME = "exts"
    script_path = os.path.dirname(os.path.realpath(__file__)) + "/scripts/kit_precache_airgap.py"
    script_path = os.path.abspath(script_path).replace("\\", "/")
    with change_cwd(f"{dev_dir}/.."):
        args = [
            resolve_tokens("./kit${exe_ext}"),
            "--allow-root",
            "--portable",
            "--enable",
            "omni.kit.async_engine",
            "--enable",
            "omni.kit.loop",
            "--/app/extensions/syncRegistryOnStartup=1",
            "--/crashreporter/gatherUserStory=0",
            "--/app/settings/persistent=0",
            "--/app/settings/loadUserConfig=0",
            "--/app/extensions/generateVersionLock=1",
            "--/app/extensions/parallelPullEnabled=1",
            "--/app/enableStdoutOutput=1",
            "--/app/extensions/registryEnabled=1",
            "--/app/extensions/mkdirExtFolders=0",
            f"--/app/extensions/registryCacheFull='./{PRECACHE_DIR_NAME}'",
            "--/log/flushStandardStreamOutput=1",
            "--/exts/omni.kit.registry.nucleus/registries/0/name='kit/sdk'",
            "--/exts/omni.kit.registry.nucleus/registries/0/url='https://pdx.s8k.io/v1/AUTH_team-ov-kit-exts/exts/kit/sdk/${kit_version_short}/${kit_git_hash}'",
            "--/exts/omni.kit.registry.nucleus/registries/1/url=''",
            "--/exts/omni.kit.registry.nucleus/registries/2/url=''",
            "--/exts/omni.kit.registry.nucleus/registries/3/url=''",
            "--/app/extensions/target/config=release",
            "--portable-root .",
            "--exec",
            f"{script_path}",
        ]

        print(f"Running kit to precache airgap extensions with: {process_args_to_cmd(args)}")
        run_process(args, exit_on_error=True)


def get_public_deps():
    """Get all public dependencies from public-deps.packman.xml"""
    public_deps_packman_xml = Path(resolve_tokens("${root}/tools/deps/public-deps.packman.xml"))
    tree = ET.parse(public_deps_packman_xml)
    root = tree.getroot()

    # Find all filter include elements
    filter_includes = []
    for filter_elem in root.findall(".//filter"):
        include = filter_elem.get("include")
        if include:
            filter_includes.append(include)

    return set(filter_includes)


def public_repo_deps(dest_repo_deps_path: str, config: dict, rewrite_link_prefix: Optional[tuple] = None):
    """Update repo deps for public usage.

    Args:
        dest_repo_deps_path: Path to write the filtered repo-deps.packman.xml.
        config: Build configuration dictionary.
        rewrite_link_prefix: Optional (old, new) tuple to rewrite linkPath prefixes.
            e.g. ("../../", "../") to adjust for a shallower directory depth.
    """

    public_deps = get_public_deps()

    src_repo_deps = resolve_tokens("${root}/tools/deps/repo-deps.packman.xml")
    tree = ET.parse(src_repo_deps)

    root = tree.getroot()

    # Find and remove dependencies not in the names_to_keep list
    for dependency in root.findall("dependency"):
        name = dependency.get("name")
        if name not in public_deps:
            print(f"Removing non-public dependency: {name}")
            root.remove(dependency)

    # Rewrite linkPath prefixes if needed (e.g. for dev/ folder which is one level less deep)
    if rewrite_link_prefix:
        old_prefix, new_prefix = rewrite_link_prefix
        for dependency in root.findall("dependency"):
            link_path = dependency.get("linkPath", "")
            if link_path.startswith(old_prefix):
                dependency.set("linkPath", new_prefix + link_path[len(old_prefix) :])

    # Write the modified XML tree to the output file
    tree.write(dest_repo_deps_path, encoding="utf-8", xml_declaration=True)


def process_path(p):
    return os.path.normpath(resolve_tokens(p))


@contextlib.contextmanager
def airgap_packman_kit_kernel(temp_dir: str, kit_kernel_version: str):
    """Temporarily override the kit-kernel version in kit-sdk.packman.xml before restoring the Packman link-back to the Kit SDK archive."""

    try:
        # For air-gap hard-code the kit-kernel version instead of using the NGC Kit-Kernel.json pattern.
        temp_kit_sdk_packman_xml = f"{temp_dir}/tools/deps/kit-sdk.packman.xml"
        with open(temp_kit_sdk_packman_xml, "w") as f:
            f.write(f"""
    <project toolsVersion="5.0">
    <dependency name="kit_sdk_${{config}}"  linkPath="../../_build/${{platform_target}}/${{config}}/kit" tags="${{config}} non-redist">
        <package name="kit-kernel" version="{kit_kernel_version}"/>
    </dependency>
    </project>""")

        yield

    finally:
        # Create the Packman user file that symlinks back to the Kit SDK archive so the base_project can find Kit.
        kit_user_file = f"{temp_dir}/tools/deps/kit-sdk.packman.xml.user"
        with open(kit_user_file, "w") as f:
            f.write("""
    <project toolsVersion="5.6">
    <dependency name="kit_sdk_${config}" linkPath="../../_build/${platform_target}/${config}/kit">
        <source path="{{parent_repo_root}}/.." />
    </dependency>
    </project>""")


@contextlib.contextmanager
def override_repo_toml(temp_dir: str):
    """Override the repo.toml on fetching kit-kernel from NGC. This is used when creating a KSP package that will fetch kit-kernel from NGC, but we don't want it to fetch from NGC during archive build time."""
    try:
        # Create a temporary user.repo.toml to override fetching kit-kernel from NGC.
        user_repo_toml = f"{temp_dir}/user.repo.toml"
        user_repo_toml_contents = {"repo_build": {"fetch": {"before_pull_commands": []}}}
        with open(user_repo_toml, "w") as f:
            toml.dump(user_repo_toml_contents, f)

        yield

    finally:
        # Unlink the temporary user.repo.toml
        Path(user_repo_toml).unlink()


def set_airgap_token(repo_toml: Path):
    """Set the airgap token in the base_project's repo.toml"""
    repo_toml_data = read_toml(repo_toml)
    # Ensure repo and tokens sections exist, preserving existing content
    if "repo" not in repo_toml_data:
        repo_toml_data["repo"] = {}
    if "tokens" not in repo_toml_data["repo"]:
        repo_toml_data["repo"]["tokens"] = {}
    # Add the airgap token while preserving other tokens
    repo_toml_data["repo"]["tokens"]["airgap"] = True
    write_toml(repo_toml, repo_toml_data)


def set_airgap_kit_registries(template_deps_dir: Path):
    """Add empty registries setting to template .kit files for airgap builds.

    This ensures applications created from templates in airgap environments
    don't attempt to contact external extension registries.
    """
    registry_setting = '\n[settings.exts."omni.kit.registry.nucleus"]\n    registries = []\n'

    for template_dir_name in ["kit_core_templates", "kit_sample_templates"]:
        template_dir = template_deps_dir / template_dir_name
        if not template_dir.exists():
            logger.warning(f"Template directory not found: {template_dir}")
            continue
        for kit_file in template_dir.rglob("*.kit"):
            content = kit_file.read_text()
            if "omni.kit.registry.nucleus" in content:
                logger.info(f"Skipping {kit_file} - already has registry.nucleus settings")
                continue
            if not content.endswith("\n"):
                content += "\n"
            kit_file.write_text(content + registry_setting)
            logger.info(f"Added airgap registry settings to {kit_file}")


def airgap_download_deps(temp_dir: str, stage_build: bool = False):
    """
    Download all dependencies for an air-gap package.
    Args:
        temp_dir: The temporary directory to download the dependencies to.
        stage_build: Whether to stage the build dependencies as well.
    """
    with change_cwd(temp_dir):
        print(f"Writing out repo cache json for {temp_dir}")
        print(f"Fetching repo tooling deps for {temp_dir}")
        repo_cmd = f"{temp_dir}/repo" + resolve_tokens("${shell_ext}")
        run_process([repo_cmd, "--help"], exit_on_error=True)
        if stage_build:
            print(f"Fetching build dependencies for {temp_dir}")
            kit_kernel_version = get_or_set_kit_kernel_version(resolve_tokens("${root}/tools/deps/kit-sdk.packman.xml"))
            with (
                override_repo_toml(temp_dir),
                airgap_packman_kit_kernel(temp_dir, kit_kernel_version),
            ):
                run_process([repo_cmd, "build", "--fetch-only", "-r", "--/repo/tokens/cache=true"], exit_on_error=True)


def _rename_packman_xml(deps_dir: Path):
    """Rename the packman.template.xml files to packman.xml.

    This exists so that tooling that scans for packman.xml files does not detect the incomplete base_project/deps files
    """
    for packman_xml in deps_dir.glob("*.packman.template.xml"):
        new_name = packman_xml.name.replace(".template", "")
        logger.info(f"Renaming {packman_xml} to {new_name}")
        packman_xml.rename(packman_xml.parent / new_name)


def _stage_base_project(config: dict):
    """
    Stage the base_project into the build directory.
    - Copy the base_project into the build directory.
    - Copy Packman installation into base_project.
    - Strip the non-public dependencies from the base_project's repo-deps.packman.xml.
    - Copy KAT templates into templates/ directory (for airgap builds).
    """
    base_project_dir = process_path("${root}/base_project")
    build_root = process_path("${root}/_build/${platform}/${config}")
    build_base_project_dir = f"{build_root}/base_project"

    # Remove prior build artifacts.
    if Path(build_base_project_dir).exists():
        shutil.rmtree(build_base_project_dir)

    # Copy the base_project into the build directory.
    shutil.copytree(base_project_dir, build_base_project_dir)

    # Copy the .skills folder and content to the base project directory
    skills_source = Path(resolve_tokens("${root}/.skills"))
    if skills_source.exists():
        shutil.copytree(skills_source, Path(build_base_project_dir) / ".skills")

    # Rename the packman.template.xml files to packman.xml.
    _rename_packman_xml(Path(build_base_project_dir) / "tools" / "deps")
    # Copy over the host-deps.packman toml to tools/deps for KAT
    omni.repo.man.copyfile(
        Path(resolve_tokens("${root}/tools/deps/host-deps.packman.xml")),
        Path(build_base_project_dir) / "tools" / "deps" / "host-deps.packman.xml",
    )

    # Copy Packman from ${root} into staged base_project.
    packman_source = Path(resolve_tokens("${root}/tools/packman"))
    packman_destination = Path(build_base_project_dir) / "tools" / "packman"
    # Clear base_project Packman directory.
    rmtree(packman_destination)
    shutil.copytree(packman_source, packman_destination)

    # Copy repoman from ${root} into staged base_project.
    repoman_source = Path(resolve_tokens("${root}/tools/repoman"))
    repoman_destination = Path(build_base_project_dir) / "tools" / "repoman"
    # Copy select files from repoman source to repoman destination.
    repoman_files = [
        "repoman.py",
        "repoman_bootstrapper.py",
    ]
    for file in repoman_files:
        shutil.copy(repoman_source / file, repoman_destination / file)

    # Remove the repo-deps-nv.packman.xml file
    nv_repo_deps = Path(build_base_project_dir) / "tools" / "deps" / "repo-deps-nv.packman.xml"
    if nv_repo_deps.exists():
        nv_repo_deps.unlink()

    # Strip the non-public dependencies from the base_project's repo-deps.packman.xml.
    # deps/ is needed for repoman.py bootstrap (hardcodes deps/repo-deps.packman.xml).
    # tools/deps/ is the source copy and already has public-only deps.
    public_repo_deps(f"{build_base_project_dir}/tools/deps/repo-deps.packman.xml", config)

    # If ngc_fetch is true, prep the base_project to fetch kit-kernel via NGC using the `repo stage kit` command.
    if get_token("ngc_fetch"):
        registries_map = registry_mapping(config)
        # Set the NGC Kit-Kernel info in the base_project
        if registry_mapping_phase(registries_map) in ["dev", "stage"]:
            # Use the Internal NGC-Kit-Kernel.json for dev and staging builds
            ngc_kit_kernel_internal_path = (
                Path(build_base_project_dir) / "tools" / "deps" / "NGC-Kit-Kernel-Internal.json"
            )
            ngc_kit_kernel_path = Path(build_base_project_dir) / "tools" / "deps" / "NGC-Kit-Kernel.json"
            # Unlink the existing NGC-Kit-Kernel.json if it exists because Windows does not permit a rename to the same file
            ngc_kit_kernel_path.unlink()
            ngc_kit_kernel_internal_path.rename(ngc_kit_kernel_path)
        else:
            ngc_kit_kernel_internal_path = (
                Path(build_base_project_dir) / "tools" / "deps" / "NGC-Kit-Kernel-Internal.json"
            )
            if ngc_kit_kernel_internal_path.exists():
                ngc_kit_kernel_internal_path.unlink()

        # Write out the version strings in NGC Kit-Kernel.json
        with open(ngc_kit_kernel_path, "r") as f:
            ngc_kit_kernel_data = json.load(f)
        # Pin Kit-Kernel version from the packman dependency (short version without build metadata)
        root_kit_sdk_packman_xml = Path(resolve_tokens(f"${{root}}/{KAT_SDK_FILE_PATH}"))
        kit_kernel_version = get_or_set_kit_kernel_version(root_kit_sdk_packman_xml).split("+")[0]
        ngc_kit_kernel_data["windows-x86_64"]["version"] = kit_kernel_version
        ngc_kit_kernel_data["linux-x86_64"]["version"] = kit_kernel_version
        with open(ngc_kit_kernel_path, "w") as f:
            json.dump(ngc_kit_kernel_data, f, indent=4)

    # Prep the base_project to fetch kit-kernel via Cloudfront using Packman
    else:
        root_kit_sdk_packman_xml = Path(resolve_tokens("${root}/tools/deps/kit-sdk.packman.xml"))
        # base_project_kit_sdk_packman_xml = Path(build_base_project_dir) / "deps" / "kit-sdk.packman.xml"
        kat_project_kit_sdk_packman_xml = Path(build_base_project_dir) / "tools" / "deps" / "kit-sdk.packman.xml"
        # Edit the base_project kit-sdk.packman.xml version with the local kit-kernel version.
        kit_kernel_version = get_or_set_kit_kernel_version(root_kit_sdk_packman_xml)
        get_or_set_kit_kernel_version(kat_project_kit_sdk_packman_xml, kit_kernel_version)
        # Copy the updated kit-sdk.packman.xml to the tools/deps directory so it is publicly accessible when staging.
        # omni.repo.man.copyfile(base_project_kit_sdk_packman_xml, kat_project_kit_sdk_packman_xml)


def _stage_dev_dir(config: dict, options: argparse.Namespace):
    """
    Stage the dev directory in the build directory.
    - Update packman config + repo-deps.packman.xml to public configuration
    - Prep repo template config for a single choice for templating base_project
    - Add `repo project` tool to repo_tools.toml
    - Add templates.toml entry for templating base_project
    """

    build_root = process_path("${root}/_build/${platform}/${config}")
    dev_dir = f"{build_root}/dev"
    templates_dir = f"{dev_dir}/templates"
    templates_toml = f"{templates_dir}/templates.toml"
    os.makedirs(templates_dir, exist_ok=True)

    # Update repo-deps.packman.xml to public configuration.
    # Rewrite linkPath prefix: source XML is at tools/deps/ (depth 2) but dev copy is at deps/ (depth 1).
    public_repo_deps(f"{dev_dir}/deps/repo-deps.packman.xml", config, rewrite_link_prefix=("../../", "../"))

    # Prep repo template for a single choice for templating base_project
    repo_toml = Path(f"{dev_dir}/repo.toml")
    with open(repo_toml, "r") as f:
        repo_toml_data = f.read()

        if "[repo_kit_template]" not in repo_toml_data:
            repo_toml_data += "\n[repo_kit_template]\n"
            repo_toml_data += 'extension_templates_config = "${root}/templates/templates.toml"\n'
            repo_toml_data += "skip_single_choice = true\n"
        else:
            assert False, "[repo_kit_template] already exists in repo.toml"

    with open(repo_toml, "w") as f:
        f.write(repo_toml_data)

    if options.airgap:
        # Set the airgap token in repo.toml if creating an airgap package.
        # This controls the `repo stage` behavior around pulling dependencies from NGC
        # vs using the packman cache in the local Kit SDK archive
        set_airgap_token(repo_toml)

    # Add `repo project` tool to repo_tools.toml
    repo_tools_toml = f"{dev_dir}/repo_tools.toml"
    with open(repo_tools_toml, "r") as f:
        repo_tools_toml_data = f.read()

        # Insert the stage command into repo_tools.toml
        if "[repo_project]" not in repo_tools_toml_data:
            repo_tools_toml_data += "\n[repo_project]\n"
            repo_tools_toml_data += 'command = "stage"\n'
            repo_tools_toml_data += 'entry_point = "${config_root}/tools/repoman/stage.py:setup_repo_tool"\n'
        else:
            assert False, "[repo_project] already exists in repo_tools.toml"

    with open(repo_tools_toml, "w") as f:
        f.write(repo_tools_toml_data)

    # Write out templates.toml with a single choice for templating base_project
    if os.name == "nt":
        repo_template_cmd = ".\\\\repo.bat template new"
    else:
        repo_template_cmd = "./repo.sh template new"

    with open(templates_toml, "w") as f:
        f.write(f'''
[templates."kit-repo-empty"]
# Template class used for the custom logic
class = "RepoTemplate"

# Name displayed in CLI/UI
name = "Kit-App-Template Repository/Project"

# local
url = "."

# dir
subpath = "../../base_project"

# Do not render any files (both content and path). Except for user file where we have a variable for the path back to Kit SDK
skip_render_files.include = [
    "**",
]
skip_render_files.exclude = [
    "{KIT_SDK_USER_FILE_PATH}",
    "{REPO_CACHE_FILE}",
]
success_message = """
Repository created successfully: $dst

Inside this directory, run these repo commands to get started:

  repo template new  - Create a new Application from a template.
  repo build         - Build your new Application.
  repo launch        - Launch your new Application.

Detailed information in the README: $dst/README.md

Get started by typing:
  cd $dst
  {repo_template_cmd}
"""
''')


def run_repo_tool(options: argparse.Namespace, config: Dict):

    # Copy the base_project into the build directory.
    _stage_base_project(config)

    # Prep the dev directory for templating out base_project
    _stage_dev_dir(config, options)

    base_dir = process_path("${root}/_build/${platform}/${config}")
    dev_dir = process_path("${root}/_build/${platform}/${config}/dev")
    base_project_dir = process_path("${root}/_build/${platform}/${config}/base_project")

    # If airgap precache the pre-built applications
    if options.airgap:
        write_repo_cache_json(dev_dir, base_dir)
        precache_airgap_extensions(dev_dir)
        airgap_download_deps(dev_dir, stage_build=False)
        write_repo_cache_json(dev_dir, "..")

    # If airgap configure the base_project to use the air-gap cache.
    if options.airgap:
        with change_cwd(base_project_dir):
            # Set a repo_cache_json to populate the air-gap cache
            write_repo_cache_json(base_project_dir, base_dir)
            # Grab the build dependencies for the base_project
            airgap_download_deps(base_project_dir, stage_build=True)

            # Add empty registries to template kit files so apps created in
            # airgap environments don't attempt to contact external registries.
            set_airgap_kit_registries(Path(base_project_dir) / "_repo" / "deps")

            # Set the repo_cache_json to point back to the Kit SDK
            write_repo_cache_json(base_project_dir, "{{parent_repo_root}}/..")
        print("FINISHED AIRGAP PRECACHE AND CONFIGURATION OF BASE_PROJECT")

    # Update kit-core.json registry mapping.
    update_kit_core_json(config)

    # Sanitize Packman config.packman.xml in dev + base_project.
    public_packman_config(dev_dir)
    public_packman_config(base_project_dir)

    # Clean up _repo and _build directories
    for path in [Path(dev_dir) / "_repo", Path(base_project_dir) / "_repo", Path(base_project_dir) / "_build"]:
        if path.exists():
            call_with_retry(
                f"remove {path}",
                lambda: rmtree(path),
                exception_types=PermissionError,
            )


def setup_repo_tool(parser: argparse.ArgumentParser, config: Dict) -> Optional[Callable]:
    """Entry point for 'repo_launch' tool"""

    parser.description = "Tool to add kit-app-template to Kit SDK"

    omni.repo.man.add_config_arg(parser)

    parser.add_argument(
        "--air-gap",
        action="store_true",
        dest="airgap",
        help="Add KAT with all deps cached for air-gapped package.",
    )

    return run_repo_tool
