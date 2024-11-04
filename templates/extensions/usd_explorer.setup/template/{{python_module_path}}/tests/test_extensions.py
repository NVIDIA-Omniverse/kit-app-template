# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import sys

import carb.settings
import omni.kit.app
import omni.kit.actions.core
from omni.kit.test import AsyncTestCase
from pxr import Usd, UsdGeom, Gf


class TestUSDExplorerExtensions(AsyncTestCase):
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

    async def test_regression_omfp_2304(self):
        loaded_omni_kit_collaboration_selection_outline = False
        manager = omni.kit.app.get_app().get_extension_manager()
        for ext in manager.get_extensions():
            if ext["name"] == "omni.kit.collaboration.selection_outline":
                loaded_omni_kit_collaboration_selection_outline = True
                break
        self.assertTrue(loaded_omni_kit_collaboration_selection_outline)

    async def _wait(self, frames: int = 10):
        for _ in range(frames):
            await omni.kit.app.get_app().next_update_async()

    async def wait_stage_loading(self):
        while True:
            _, files_loaded, total_files = omni.usd.get_context().get_stage_loading_status()
            if files_loaded or total_files:
                await self._wait()
                continue
            break
        await self._wait(100)

    async def _get_1_1_1_rotation(self) -> Gf.Vec3d:
        """Loads a stage and returns the transformation of the (1,1,1) vector by the directional light's rotation"""
        await self._wait()
        omni.kit.actions.core.execute_action("omni.kit.window.file", "new")
        await self.wait_stage_loading()
        context = omni.usd.get_context()
        self.assertIsNotNone(context)
        stage = context.get_stage()
        self.assertIsNotNone(stage)

        prim_path = '/Environment/DistantLight'
        prim = stage.GetPrimAtPath(prim_path)
        self.assertTrue(prim.IsValid())

        # Extract the prim's transformation matrix in world space
        xformAPI = UsdGeom.XformCache()
        transform_matrix_world = xformAPI.GetLocalToWorldTransform(prim)

        unit_point = Gf.Vec3d(1, 1, 1)
        transformed_point = transform_matrix_world.Transform(unit_point)
        return transformed_point
