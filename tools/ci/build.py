# Common CI job build script for Kit Extensions & Apps:

import os
import shutil
import sys
import tempfile
from pathlib import Path
from string import Template

import omni.repo.ci
import omni.repo.man
from omni.repo.man import resolve_tokens
from omni.repo.man.utils import is_running_on_ci

# Import kit artifact helper
sys.path.insert(0, str(Path(__file__).parent))
import kit_artifact

OTHERS = "others"

# Temporary hack, repo_kit_tools premake expects source/apps to exist.
ROOT = Path(__file__).joinpath("..", "..", "..").resolve()
source_apps = ROOT / "source/apps"
source_apps.mkdir(parents=True, exist_ok=True)

# Need the EULA breadcrumb.
eula_breadcrumb = Path(f"{ROOT}/.omniverse_eula_accepted.txt")
eula_breadcrumb.parent.mkdir(parents=True, exist_ok=True)
eula_breadcrumb.touch()

# Setup kit from artifact if running from kit CI
kit_artifact.setup_kit_from_artifact()

# Common names
# This is the prefix of the app name and the app script.
# The prefix name is hardcoded in launcher.toml and warmup.{sh,bat} of each app.
# Remember to update all of them if you'd like to update it.
company = "nv_internal"


def _is_single_app(app):
    return app and app != OTHERS


def _get_package_args():
    app = os.getenv("APP")
    if not _is_single_app(app):
        return []

    args = []
    # Append arguments to update the package name.
    for p in ["fat", "thin"]:
        sub_section = f"{p}_package"
        archive_name = f'--/repo_package/packages/{sub_section}/archive_name="{app}-{p}"'
        args.append(archive_name)

        version_file = _get_app_version_file_path()
        if version_file and Path(version_path).is_file():
            version_args = f'--/repo/folders/version_file="{_get_app_version_file_path()}"'
            args.append(version_args)

    return args


def _get_app_version_file_path():
    app = os.getenv("APP")
    if not _is_single_app(app):
        # Return the Kit version if not one of the launcher targeted apps.
        return f"{ROOT}/tools/VERSION.md"
    return f"{ROOT}/tools/VERSION.md"


def _get_app_version():
    path = _get_app_version_file_path()
    if not path or not os.path.exists(path):
        return "DEFAULT"
    with open(path) as fr:
        return fr.read().strip()


def _template_playback(template_filepath: Path, replacements: dict = {}):
    # Read in the repo_kit_template replay file template
    base_template = template_filepath.read_text()
    # Swap things around.
    prepared_template = Template(base_template).substitute(replacements)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        # Write out the prepared playback template
        # Don't delete the file on exiting the context manager. Windows requires the file to be closed
        # before it can be opened for reading. Delete it with a try/finally to keep things tidy even
        # in failure scenarios.
        temp_file_name = temp_file.name
        temp_file.write(prepared_template)
        temp_file.flush()

    try:
        # Render the Application/Extension template
        omni.repo.ci.launch(["${root}/repo${shell_ext}", "template", "replay", temp_file_name])

    finally:
        # Cleanup the tempfile
        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)


def _template_new_usd_viewer():
    # Instantiate the usd_viewer Application + Messaging Extenson + Setup Extension

    # repo template playback template path
    playback_template_path = Path(resolve_tokens("${root}/tools/ci/automated_templating/usd_viewer.toml.j2"))

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": _get_app_version(), "APPLICATION_NAME": f"{company}.my_usd_viewer"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)


def _template_new_usd_explorer():
    # Instantiate the usd_explorer Application + Setup Extension

    # repo template playback template path
    playback_template_path = Path(resolve_tokens("${root}/tools/ci/automated_templating/usd_explorer.toml.j2"))

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": _get_app_version(), "APPLICATION_NAME": f"{company}.my_usd_explorer"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)


def _template_new_usd_composer():
    # Instantiate the usd_composer Application + Setup Extension

    # repo template playback template path
    playback_template_path = Path(resolve_tokens("${root}/tools/ci/automated_templating/usd_composer.toml.j2"))

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": _get_app_version(), "APPLICATION_NAME": f"{company}.my_usd_composer"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)


def _template_new_others():
    version = _get_app_version()
    # Instantiate Kit Base Editor Application
    # repo template playback template path

    playback_template_path = Path(resolve_tokens("${root}/tools/ci/automated_templating/kit_base_editor.toml.j2"))

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": version, "APPLICATION_NAME": f"{company}.kit_base_editor"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)

    # Instantiate Kit Service Application + Setup Extension
    playback_template_path = Path(resolve_tokens("${root}/tools/ci/automated_templating/kit_service.toml.j2"))

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": version, "APPLICATION_NAME": f"{company}.kit_service"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)

    # Instantiate Basic Python Extension
    playback_template_path = Path(
        resolve_tokens("${root}/tools/ci/automated_templating/basic_python_extension.toml.j2")
    )

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": version, "APPLICATION_NAME": f"{company}.basic_python_extension"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)

    # Instantiate Basic C++ Extension
    playback_template_path = Path(resolve_tokens("${root}/tools/ci/automated_templating/basic_cpp_extension.toml.j2"))

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": version, "APPLICATION_NAME": f"{company}.basic_cpp_extension"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)

    # Instantiate Basic Python UI Extension
    playback_template_path = Path(
        resolve_tokens("${root}/tools/ci/automated_templating/basic_python_ui_extension.toml.j2")
    )

    # String.Template replacements within playback_template_path
    replacements = {"VERSION": version, "APPLICATION_NAME": f"{company}.basic_python_ui_extension"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)

    playback_template_path = Path(
        resolve_tokens("${root}/tools/ci/automated_templating/basic_pybind11_extension.toml.j2")
    )
    # String.Template replacements within playback_template_path
    replacements = {"VERSION": version, "APPLICATION_NAME": f"{company}.basic_python_binding"}

    # Stamp out the playback template and then build the desired application template. Template. Template.
    _template_playback(playback_template_path, replacements)


def _template_new_python_extension():
    # Instantiate Basic Python Extension. Used in a stand-alone manner to test
    # templating + building of just an extension.
    omni.repo.ci.launch(
        [
            "${root}/repo${shell_ext}",
            "template",
            "new",
            f"--input=Extension>;[basic_python_ui_extension]: Python UI Extension;{company}.python_extension;DEFAULT;0.1.0;",
        ]
    )


################################################################################
# Build
################################################################################

# Generate apps from templates.
app = os.getenv("APP")
template_func = locals().get(f"_template_new_{app}")
if template_func:
    template_func()

elif not is_running_on_ci():
    # Local development option.
    for func in [
        _template_new_usd_viewer,
        _template_new_usd_explorer,
        _template_new_usd_composer,
        _template_new_others,
    ]:
        func()

else:
    print(f"Invalid APP: {app}")
    sys.exit(1)

version_path = _get_app_version_file_path()
# Avoid copying tools/VERSION.md over tools/VERSION.md when a non-core app is being templated.
if (
    version_path
    and Path(version_path).is_file()
    and Path(version_path).as_posix() != (ROOT / "tools/VERSION.md").as_posix()
):
    print(f"> Update the version file from {version_path} with version {_get_app_version()}")
    shutil.copy2(version_path, ROOT / "tools/VERSION.md")
else:
    print(f"> Use the original version file")

# Build Release, there are vulkan-sdk requirements associated with debug
# builds that CI agents do not have.
omni.repo.ci.launch(["${root}/repo${shell_ext}", "build", "-r"])


################################################################################
# Deploy extensions
################################################################################
# Tool to promote extensions to the public registry pipeline, if enabled (for apps)
# Run only on windows as it has more extensions (titlebar)
is_windows = omni.repo.ci.is_windows()
if app == OTHERS:
    if (
        omni.repo.ci.is_gitlab()
        and omni.repo.ci.get_repo_config().get("repo_deploy_exts", {}).get("enabled", False)
        and is_windows
    ):
        omni.repo.ci.launch(["${root}/repo${shell_ext}", "deploy_exts"])


################################################################################
# Package
################################################################################

# Use repo_docs.enabled as indicator for whether to build docs
# docs are also windows only on CI
repo_docs_enabled = omni.repo.ci.get_repo_config().get("repo_docs", {}).get("enabled", True)
repo_docs_enabled = repo_docs_enabled and is_windows and app == OTHERS  # prevent creating docs in every app build

# Docs (windows only)
if repo_docs_enabled:
    omni.repo.ci.launch(["${root}/repo${shell_ext}", "docs", "--config", "release"])

# Package all
omni.repo.ci.launch(
    [
        "${root}/repo${shell_ext}",
        "package",
        "-c",
        "release",
    ]
    + _get_package_args()
)

if repo_docs_enabled:
    omni.repo.ci.launch(["${root}/repo${shell_ext}", "_package", "-m", "docs", "-c", "release"])
