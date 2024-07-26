# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import json
import time
from typing import Tuple

import carb.settings
import omni.kit.app
from omni.kit.test import AsyncTestCase


class TestAppStartup(AsyncTestCase):
    def app_startup_time(self, test_id: str) -> float:
        """Get startup time - send to nvdf"""
        test_start_time = time.monotonic()
        startup_time = omni.kit.app.get_app().get_time_since_start_s()
        test_result = {"startup_time_s": startup_time}
        print(f"App Startup time: {startup_time}")
        self._post_to_nvdf(test_id, test_result, time.monotonic() - test_start_time)
        return startup_time

    def app_startup_warning_count(self, test_id: str) -> Tuple[int, int]:
        """Get the count of warnings during startup - send to nvdf"""
        test_start_time = time.monotonic()
        warning_count = 0
        error_count = 0
        log_file_path = carb.settings.get_settings().get("/log/file")
        with open(log_file_path, "r") as file:
            for line in file:
                if "[Warning]" in line:
                    warning_count += 1
                elif "[Error]" in line:
                    error_count += 1

        test_result = {"startup_warning_count": warning_count, "startup_error_count": error_count}
        print(f"App Startup Warning count: {warning_count}")
        print(f"App Startup Error count: {error_count}")
        self._post_to_nvdf(test_id, test_result, time.monotonic() - test_start_time)
        return warning_count, error_count

    # TODO: should call proper API from Kit
    def _post_to_nvdf(self, test_id: str, test_result: dict, test_duration: float):
        """Send results to nvdf"""
        try:
            from omni.kit.test.nvdf import _can_post_to_nvdf, _get_ci_info, _post_json, get_app_info, to_nvdf_form

            if not _can_post_to_nvdf():
                return

            data = {}
            data["ts_created"] = int(time.time() * 1000)
            data["app"] = get_app_info()
            data["ci"] = _get_ci_info()
            data["test"] = {
                "passed": True,
                "skipped": False,
                "unreliable": False,
                "duration": test_duration,
                "test_id": test_id,
                "ext_test_id": "omni.create.tests",
                "test_type": "unittest",
            }
            data["test"].update(test_result)

            project = "omniverse-kit-tests-results-v2"
            json_str = json.dumps(to_nvdf_form(data), skipkeys=True)
            _post_json(project, json_str)
            # print(json_str)  # uncomment to debug

        except Exception as e:
            carb.log_warn(f"Exception occurred: {e}")

    async def test_l1_app_startup_time(self):
        """Get startup time - send to nvdf"""
        for _ in range(60):
            await omni.kit.app.get_app().next_update_async()

        self.app_startup_time(self.id())
        self.assertTrue(True)

    async def test_l1_app_startup_warning_count(self):
        """Get the count of warnings during startup - send to nvdf"""
        for _ in range(60):
            await omni.kit.app.get_app().next_update_async()

        self.app_startup_warning_count(self.id())
        self.assertTrue(True)
