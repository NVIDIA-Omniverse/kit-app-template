## Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
##
## NVIDIA CORPORATION and its licensors retain all intellectual property
## and proprietary rights in and to this software, related documentation
## and any modifications thereto.  Any use, reproduction, disclosure or
## distribution of this software and related documentation without an express
## license agreement from NVIDIA CORPORATION is strictly prohibited.
##
import sys

import carb.settings
import omni.kit.app
import omni.kit.actions.core
from omni.kit.core.tests import validate_extensions_load, validate_extensions_tests
from omni.kit.test import AsyncTestCase
from pxr import Usd, UsdGeom, Gf


class TestUSDExplorerExtensions(AsyncTestCase):
    async def test_l1_extensions_have_tests(self):
        """Loop all enabled extensions to see if they have at least one (1) unittest"""
        await omni.kit.app.get_app().next_update_async()
        await omni.kit.app.get_app().next_update_async()

        # This list should be empty or near empty ideally
        EXCLUSION_LIST = [
            # extensions from Kit
            "omni.mdl",
            "omni.ansel.init",
            # extensions from USD Explorer
        ]
        # These extensions only run tests on win32 for now
        if sys.platform != "win32":
            EXCLUSION_LIST.append("omni.hydra.scene_api")
            EXCLUSION_LIST.append("omni.rtx.tests")

        self.assertEqual(validate_extensions_tests(EXCLUSION_LIST), 0)

    async def test_l1_extensions_load(self):
        """Loop all enabled extensions to see if they loaded correctly"""
        self.assertEqual(validate_extensions_load(), 0)

    async def test_regression_omfp_2304(self):
        """Regression test for OMFP-2304"""
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

    async def test_regression_omfp_OMFP_3314(self):
        """Regression test for OMFP-3314"""
        settings = carb.settings.get_settings()
        UP_AXIS_PATH = "/persistent/app/stage/upAxis"

        settings.set("/persistent/app/newStage/defaultTemplate", "SunnySky")

        settings.set_string(UP_AXIS_PATH, "Z")
        point_z_up = await self._get_1_1_1_rotation()
        settings.set_string(UP_AXIS_PATH, "Y")
        point_y_up = await self._get_1_1_1_rotation()

        # with the default camera position:
        # in y-up: z points bottom left, x points bottom right, y points up
        # in z-up: x points bottom left, y points bottom right, z points up
        places = 4
        self.assertAlmostEqual(point_y_up[2], point_z_up[0], places=places)
        self.assertAlmostEqual(point_y_up[0], point_z_up[1], places=places)
        self.assertAlmostEqual(point_y_up[1], point_z_up[2], places=places)

