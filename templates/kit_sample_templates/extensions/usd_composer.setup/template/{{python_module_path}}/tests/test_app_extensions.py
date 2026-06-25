# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import omni.kit.app
from omni.kit.test import AsyncTestCase


class TestUSDComposerExtensions(AsyncTestCase):
    # NOTE: Function pulled to remove dependency from omni.kit.core.tests
    def _validate_extensions_load(self):
        failures = []
        manager = omni.kit.app.get_app().get_extension_manager()
        for ext in manager.get_extensions():
            ext_id = ext["id"]
            ext_name = ext["name"]
            info = manager.get_extension_dict(ext_id)

            enabled = ext.get("enabled", False)
            if not enabled:
                continue

            failed = info.get("state/failed", False)
            if failed:
                failures.append(ext_name)

        if len(failures) == 0:
            print("\n[success] All extensions loaded successfully!\n")
        else:
            print("")
            print(f"[error] Found {len(failures)} extensions that could not load:")
            for count, ext in enumerate(failures):
                print(f"  {count+1}: {ext}")
            print("")
        return len(failures)

    async def test_l1_extensions_load(self):
        """Loop all enabled extensions to see if they loaded correctly"""
        self.assertEqual(self._validate_extensions_load(), 0)