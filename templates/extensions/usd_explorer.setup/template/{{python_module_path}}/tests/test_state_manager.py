# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import carb.settings
import omni.kit.app
import omni.ui as ui
from omni.kit.test import AsyncTestCase
from ..ui_state_manager import UIStateManager, MODAL_TOOL_ACTIVE_PATH


class TestUIStateManager(AsyncTestCase):
    async def setUp(self):
        self._sm = UIStateManager()
        self._settings = carb.settings.get_settings()

    async def tearDown(self):
        self._sm = None

    async def test_destroy(self):
        self._sm.add_hide_on_modal('dummy', False)
        self._sm.add_settings_copy_dependency('a', 'b')
        self._sm.add_settings_dependency('c', 'd', {1: 2})
        self._sm.add_window_visibility_setting('my_window', 'my_setting')

        self._sm.destroy()

    async def test_hide_on_modal(self):
        self._settings.set_bool(MODAL_TOOL_ACTIVE_PATH, False)

        self._sm.add_hide_on_modal('NO_RESTORE', False)
        self._sm.add_hide_on_modal(['A_RESTORE', 'B_RESTORE'], True)

        window_no_restore = ui.Window('NO_RESTORE')
        window_restore_1 = ui.Window('A_RESTORE')
        window_restore_2 = ui.Window('B_RESTORE')
        window_no_restore.visible = True
        window_restore_1.visible = True
        window_restore_2.visible = False
        await self._wait()

        self._settings.set_bool(MODAL_TOOL_ACTIVE_PATH, True)
        await self._wait()
        self.assertFalse(window_no_restore.visible)
        self.assertFalse(window_restore_1.visible)
        self.assertFalse(window_restore_2.visible)

        self._settings.set_bool(MODAL_TOOL_ACTIVE_PATH, False)
        await self._wait()
        self.assertFalse(window_no_restore.visible)
        self.assertTrue(window_restore_1.visible)
        self.assertFalse(window_restore_2.visible)

        self._sm.remove_hide_on_modal(window_restore_1.title)
        self._settings.set_bool(MODAL_TOOL_ACTIVE_PATH, True)
        await self._wait()
        self.assertTrue(window_restore_1.visible)

        self._settings.set_bool(MODAL_TOOL_ACTIVE_PATH, False)

    async def test_window_visibility_setting(self):
        window_name = 'Dummy'
        setting_path = '/apps/dummy'
        setting_path2 = '/apps/dummy2'
        window = ui.Window(window_name)
        window.visible = True
        await self._wait()

        self._sm.add_window_visibility_setting(window_name=window_name, setting_path=setting_path)
        self._sm.add_window_visibility_setting(window_name=window_name, setting_path=setting_path2)
        self.assertIsNotNone(self._settings.get(setting_path))
        self.assertTrue(self._settings.get(setting_path))
        self.assertTrue(self._settings.get(setting_path2))

        window.visible = False
        self.assertFalse(self._settings.get(setting_path))
        self.assertFalse(self._settings.get(setting_path2))

        window.visible = True
        self.assertTrue(self._settings.get(setting_path))
        self.assertTrue(self._settings.get(setting_path2))

        self._sm.remove_window_visibility_setting(window_name=window_name, setting_path=setting_path)
        window.visible = False
        self.assertTrue(self._settings.get(setting_path))
        self.assertFalse(self._settings.get(setting_path2))

        self._sm.remove_all_window_visibility_settings(window_name=window_name)
        window.visible = True
        self.assertFalse(self._settings.get(setting_path2))

    async def test_setting_dependency(self):
        setting_path_copy_from = '/app/copy_from'
        setting_path_copy_to = '/ext/copy_to'

        setting_path_map_from = '/ext/map_from'
        setting_path_map_to = '/something/map_to'

        self._sm.add_settings_copy_dependency(setting_path_copy_from, setting_path_copy_to)
        self._settings.set_string(setting_path_copy_from, 'hello_world')
        self.assertEqual(self._settings.get(setting_path_copy_from), self._settings.get(setting_path_copy_to))
        # doesn't work the other way around
        self._settings.set_string(setting_path_copy_to, 'no_copy_back')
        self.assertEqual(self._settings.get(setting_path_copy_from), 'hello_world')

        self._sm.add_settings_dependency(setting_path_map_from, setting_path_map_to, {1: 2, 3: 4})
        self._settings.set_int(setting_path_map_from, 1)
        self.assertEqual(self._settings.get(setting_path_map_to), 2)
        self._settings.set_int(setting_path_map_from, 3)
        self.assertEqual(self._settings.get(setting_path_map_to), 4)
        # not in the map
        self._settings.set_int(setting_path_map_from, 42)
        self.assertEqual(self._settings.get(setting_path_map_to), 4)

        self.assertEqual(self._settings.get(setting_path_copy_from), 'hello_world')
        self.assertEqual(self._settings.get(setting_path_copy_to), 'no_copy_back')

        self._sm.remove_settings_dependency(setting_path_copy_from, setting_path_copy_to)
        self._settings.set_string(setting_path_copy_from, 'this_is_not_copied')
        self.assertEqual(self._settings.get(setting_path_copy_to), 'no_copy_back')

    async def _wait(self, frames: int = 5):
        for _ in range(frames):
            await omni.kit.app.get_app().next_update_async()