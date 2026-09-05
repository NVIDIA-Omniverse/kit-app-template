"""Lightweight docs lint checks."""
import re
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[1] / "readme-assets" / "additional-docs"


def test_warning_callouts_use_colon():
    """Warning-style callouts should end with a colon before the body text."""
    md_file = DOCS_ROOT / "kit_app_streaming_config.md"
    content = md_file.read_text(encoding="utf-8")

    # Find any ':warning: **Label**' style callout that does not have a colon after it.
    bad_callouts = re.findall(r":warning:\s*\*\*[A-Za-z ]+?\*\*(?!:)\s*$", content, re.MULTILINE)
    assert not bad_callouts, (
        f"Found warning callouts missing trailing colon in {md_file}: {bad_callouts}"
    )
