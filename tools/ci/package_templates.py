# This ci tool will package the templates into a zip file and upload it to the specified location.
# The content will first be evaluated and stripped of the autoremove content, similar to how we would
# for staging for github. This will ensure that the content is consistent with what we would have in the
# public github for release.

import logging
import os
import sys
from pathlib import Path

import omni.repo.ci
from omni.repo.man import print_log, resolve_tokens

logger = logging.getLogger(__name__)


def _fail(message):
    logger.error(f"stage_for_github failed: {message}")
    sys.exit(-1)


def trim_files_inplace(operating_dir, trim_files, begin_marker, end_marker):
    for file in trim_files:
        path = os.path.join(operating_dir, file)
        if not os.path.exists(path):
            _fail(f"Can't find file: {path} to trim")

        print_log(f"trimming file: {path}...")

        content = ""
        with open(path, "r") as f:
            content = f.read()
            lines = content.split("\n")
            found_stuff_to_trim = False
            try:
                while True:
                    start = next(i for i, v in enumerate(lines) if v.strip().startswith(begin_marker))
                    end = next(i for i, v in enumerate(lines) if v.strip().startswith(end_marker))
                    found_stuff_to_trim = True
                    del lines[start : end + 1]
            except StopIteration:
                if not found_stuff_to_trim:
                    print_log(f"nothing to trim was not found in: {path}")
                    return

            content = "\n".join(lines)

        with open(path, "w") as f:
            f.write(content)


################################################################################
# Template pruning
################################################################################
print_log("trimming templates...")
trim_files = [
    "templates/apps/kit_base_editor/kit_base_editor.kit",
    "templates/apps/kit_service/kit_service.kit",
    "templates/apps/usd_composer/omni.usd_composer.kit",
    "templates/apps/usd_explorer/omni.usd_explorer.kit",
    "templates/apps/usd_viewer/omni.usd_viewer.kit",
    "templates/apps/streaming_configs/default_stream.kit",
    "templates/apps/streaming_configs/nvcf_stream.kit",
]
begin_marker = "# AUTOREMOVE: BEGIN"
end_marker = "# AUTOREMOVE: END"
project_root = Path(resolve_tokens("${root}"))
trim_files_inplace(project_root, trim_files, begin_marker, end_marker)


################################################################################
# Package
################################################################################
# Package all templates via commands
for template in ["kit_core_templates", "kit_sample_templates"]:
    print_log(f"packaging {template}...")
    omni.repo.ci.launch(
        [
            "${root}/repo${shell_ext}",
            "_package",
            "-m",
            template,
        ]
    )
