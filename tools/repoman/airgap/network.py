# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#

"""Block outbound network access using Windows Firewall rules.

Provides a context manager equivalent to Docker's ``--network none``:
loopback traffic is preserved, but all other outbound connections are
denied.  Requires an elevated (Administrator) terminal.

Linux CI uses ``docker --network none`` instead, so this module is
Windows-only.
"""

from __future__ import annotations

import ctypes
import logging
import socket
import subprocess
import sys
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

RULE_NAME = "KitAirgapTest-BlockOutbound"


def _is_admin() -> bool:
    """Return True if the current process has Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0  # type: ignore[union-attr]
    except Exception:
        return False


def _network_reachable(host: str = "pypi.org", port: int = 443, timeout: float = 3) -> bool:
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


def add_block() -> None:
    """Add an outbound-blocking Windows Firewall rule."""
    subprocess.run(
        [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={RULE_NAME}",
            "dir=out",
            "action=block",
            "enable=yes",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def remove_block() -> None:
    """Remove the outbound-blocking firewall rule. Safe to call even if not present."""
    subprocess.run(
        [
            "netsh",
            "advfirewall",
            "firewall",
            "delete",
            "rule",
            f"name={RULE_NAME}",
        ],
        capture_output=True,
        text=True,
    )


@contextmanager
def blocked_network(verify: bool = True) -> Generator[None, None, None]:
    """Context manager that blocks outbound network for its duration.

    Requires an elevated (Administrator) terminal.  On exit (including
    exceptions), the firewall rule is unconditionally removed.

    Args:
        verify: After blocking, confirm the network is actually unreachable.
    """
    if sys.platform != "win32":
        raise RuntimeError(
            "--block-network is only supported on Windows. " "Linux CI should use docker --network none instead."
        )

    if not _is_admin():
        raise PermissionError("Blocking network access requires an elevated (Administrator) terminal.")

    # Clean up any stale rule from a previous crashed run
    remove_block()

    print(f"Blocking outbound network access (firewall rule: {RULE_NAME}) ...")
    add_block()
    try:
        if verify:
            if _network_reachable():
                remove_block()
                raise RuntimeError(
                    "Network is still reachable after adding firewall block rule. "
                    "The firewall rule may not be effective."
                )
            print("Verified: outbound network is blocked.")
        yield
    finally:
        print(f"Restoring network access (removing firewall rule: {RULE_NAME}) ...")
        remove_block()
        if verify and not _network_reachable():
            logger.warning(
                "Network still appears blocked after removing firewall rule. "
                "You may need to manually run: "
                f'netsh advfirewall firewall delete rule name="{RULE_NAME}"'
            )
        else:
            print("Verified: network access restored.")
