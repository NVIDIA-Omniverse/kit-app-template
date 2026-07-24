import logging
import re
from functools import lru_cache
from pathlib import Path

import omni.repo.man
import omni.repo.man.utils

logger = logging.getLogger(__name__)


def _kit_sdk_packman_path(root: Path) -> Path:
    for rel in ("tools/deps/kit-sdk.packman.xml", "deps/kit-sdk.packman.xml"):
        p = root / rel
        if p.is_file():
            return p
    raise ValueError("Kit SDK packman file not found: tools/deps/kit-sdk.packman.xml or deps/kit-sdk.packman.xml")


def _get_hash_from_packman(xml_path: Path) -> str | None:
    """Extract kit kernel hash from packman XML if version string contains it. Returns None if not present."""
    with open(xml_path) as f:
        content = f.read()
    version_match = re.search(r'version="[^"]*\+[^.]+\.\d+\.([a-f0-9]+)\.gl', content)
    if not version_match:
        return None
    git_hash = version_match.group(1)
    if not re.match(r"^[a-f0-9]{8}$", git_hash):
        raise ValueError(f"Invalid git hash format in packman XML: {git_hash!r}")
    return git_hash


def _get_hash_from_kit_binary(root: Path) -> str | None:
    """Run kit --help and parse hash from Kit Version line. Returns None if unavailable."""
    kit_path_templates = [
        "${root}/_build/${platform}/release/kit${exe_ext}",
        "${root}/_build/target-deps/kit/release/kit${exe_ext}",
    ]
    for template in kit_path_templates:
        kit_path = Path(omni.repo.man.resolve_tokens(template))
        if not kit_path.exists():
            continue
        try:
            _code, lines = omni.repo.man.utils.run_process_return_output(
                [str(kit_path), "--help"],
                quiet=True,
                print_stdout=False,
                print_stderr=False,
                cwd=str(root),
            )
            out = "\n".join(lines) if lines else ""
            m = re.search(r"Kit Version:\s*\S+\.([a-f0-9]{8})\.gl", out)
            if m:
                return m.group(1)
        except Exception as e:
            logger.debug("Kit kernel hash probe failed for %s: %s", kit_path, e)
            continue
    return None


@lru_cache(maxsize=1)
def get_kit_kernel_hash():
    """Return kit kernel hash from packman XML or kit binary (kit --help). Cached per process."""
    root = Path(omni.repo.man.resolve_tokens("${root}"))
    xml_path = _kit_sdk_packman_path(root)

    git_hash = _get_hash_from_packman(xml_path)
    if git_hash:
        return git_hash

    git_hash = _get_hash_from_kit_binary(root)
    if git_hash:
        return git_hash

    raise ValueError(
        "Kit kernel hash not found in kit-sdk.packman.xml and kit binary (kit --help) could not be used. "
        "Ensure packman version includes the hash or run `repo build --fetch-only --release` so kit is available."
    )
