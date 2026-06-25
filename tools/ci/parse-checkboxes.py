#!/usr/bin/env python3
"""
Parse checkboxes from GitLab MR description and generate environment variables.
Based on the avsim-service implementation.
"""

import json
import os
import re
import sys
from pathlib import Path


def load_checkbox_config(config_file):
    """Load checkbox configuration from JSON file."""
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        return config.get("checkbox", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading checkbox config: {e}")
        return {}


def parse_checkboxes(mr_description, checkbox_config):
    """Parse checkboxes from MR description and return environment variables."""
    env_vars = {}

    # Initialize all checkboxes as unchecked
    for var_name in checkbox_config.keys():
        env_vars[var_name] = "0"

    if not mr_description:
        return env_vars

    # Parse each line looking for checkbox patterns
    for line in mr_description.split("\n"):
        line = line.strip()

        # Match checkbox pattern: - [x] or - [ ] followed by text
        checkbox_match = re.match(r"^-\s*\[([x\sX])\]\s*(.+)", line)
        if not checkbox_match:
            continue

        checked = checkbox_match.group(1).strip().lower() == "x"
        checkbox_text = checkbox_match.group(2).strip()

        # Find matching configuration
        for var_name, config_text in checkbox_config.items():
            if config_text.lower() in checkbox_text.lower():
                env_vars[var_name] = "1" if checked else "0"
                break

    return env_vars


def write_env_file(env_vars, output_file):
    """Write environment variables to file."""
    with open(output_file, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")


def main():
    """Main function to parse checkboxes and generate environment file."""
    # Get input parameters
    config_file = os.environ.get("CHECKBOX_CONFIG_FILE", "tools/ci/shared/checkbox.json")
    mr_description = os.environ.get("CI_MERGE_REQUEST_DESCRIPTION", "")
    output_file = os.environ.get("CHECKBOX_OUTPUT_FILE", "CHECKBOXES.env")

    # Alternative: read from file if CI_MERGE_REQUEST_DESCRIPTION is empty
    if not mr_description and os.path.exists("_MR_DESCRIPTION.txt"):
        with open("_MR_DESCRIPTION.txt", "r") as f:
            mr_description = f.read()

    print(f"Loading checkbox config from: {config_file}")
    checkbox_config = load_checkbox_config(config_file)

    if not checkbox_config:
        print("No checkbox configuration found, creating empty env file")
        with open(output_file, "w") as f:
            f.write("# No checkbox configuration found\n")
        return 0

    print(f"Parsing checkboxes from MR description...")
    env_vars = parse_checkboxes(mr_description, checkbox_config)

    print(f"Writing environment variables to: {output_file}")
    write_env_file(env_vars, output_file)

    # Print summary
    checked_items = [k for k, v in env_vars.items() if v == "1"]
    if checked_items:
        print(f"Checked items: {', '.join(checked_items)}")
    else:
        print("No checkboxes are checked")

    return 0


if __name__ == "__main__":
    sys.exit(main())
