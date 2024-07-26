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


class TestAppStartup(AsyncTestCase):
    async def test_l1_app_startup_time(self):
        """Get startup time - send to nvdf"""
        for _ in range(60):
            await omni.kit.app.get_app().next_update_async()

        try:
            from omni.kit.core.tests import app_startup_time

            app_startup_time(self.id())
        except:  # noqa
            pass
        self.assertTrue(True)

    async def test_l1_app_startup_warning_count(self):
        """Get the count of warnings during startup - send to nvdf"""
        for _ in range(60):
            await omni.kit.app.get_app().next_update_async()

        try:
            from omni.kit.core.tests import app_startup_warning_count

            app_startup_warning_count(self.id())
        except:  # noqa
            pass
        self.assertTrue(True)
