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

from omni.ui.tests.test_base import OmniUiTest
from omni.kit import ui_test


ext_id = '{{ extension_name }}'


class TestSetupToolExtension(OmniUiTest):
    async def test_extension(self):
        manager = omni.kit.app.get_app().get_extension_manager()
        self.assertTrue(ext_id)
        self.assertTrue(manager.is_extension_enabled(ext_id))

        app = omni.kit.app.get_app()
        for _ in range(100):
            await app.next_update_async()

        manager.set_extension_enabled(ext_id, False)
        await ui_test.human_delay()

        self.assertTrue(not manager.is_extension_enabled(ext_id))
        manager.set_extension_enabled(ext_id, True)
        await ui_test.human_delay()

        self.assertTrue(manager.is_extension_enabled(ext_id))

    async def test_menubar_helper_camera_dependency(self):
        manager = omni.kit.app.get_app().get_extension_manager()

        manager.set_extension_enabled(ext_id, False)
        await ui_test.human_delay()
        self.assertFalse(manager.is_extension_enabled(ext_id))

        manager.set_extension_enabled('omni.kit.viewport.menubar.camera', True)
        await ui_test.human_delay()

        manager.set_extension_enabled(ext_id, True)
        await ui_test.human_delay()
        self.assertTrue(manager.is_extension_enabled(ext_id))

        manager.set_extension_enabled(ext_id, False)
        await ui_test.human_delay()
        self.assertFalse(manager.is_extension_enabled(ext_id))

        manager.set_extension_enabled(ext_id, True)
        await ui_test.human_delay()
        self.assertTrue(manager.is_extension_enabled(ext_id))

    async def test_menu_helper(self):
        from ..menu_helper import MenuHelper

        menu_helper = MenuHelper()
        menu_helper.destroy()

    async def test_menubar_helper_menu(self):
        from ..menubar_helper import MenubarHelper

        menubar_helper = MenubarHelper()
        menubar_helper._create_camera_speed(None, None)
        menubar_helper.destroy()

    async def test_menu_helper_debug_setting(self):
        SETTINGS_VIEW_DEBUG_MENUS = '/app/view/debug/menus'

        import carb.settings
        settings = carb.settings.get_settings()

        manager = omni.kit.app.get_app().get_extension_manager()
        manager.set_extension_enabled(ext_id, False)
        await ui_test.human_delay()
        self.assertFalse(manager.is_extension_enabled(ext_id))

        orig_value = settings.get(SETTINGS_VIEW_DEBUG_MENUS)
        settings.set_bool(SETTINGS_VIEW_DEBUG_MENUS, True)

        manager.set_extension_enabled(ext_id, True)
        await ui_test.human_delay()
        self.assertTrue(manager.is_extension_enabled(ext_id))

        manager.set_extension_enabled(ext_id, False)
        await ui_test.human_delay()
        self.assertFalse(manager.is_extension_enabled(ext_id))

        settings.set_bool(SETTINGS_VIEW_DEBUG_MENUS, orig_value)

        manager.set_extension_enabled(ext_id, True)
        await ui_test.human_delay()
        self.assertTrue(manager.is_extension_enabled(ext_id))

    async def test_menu_helper_application_mode_change(self):
        from ..menu_helper import SETTINGS_APPLICATION_MODE_PATH

        import carb.settings
        settings = carb.settings.get_settings()

        settings.set_string(SETTINGS_APPLICATION_MODE_PATH, 'modify')
        await ui_test.human_delay()
        settings.set_string(SETTINGS_APPLICATION_MODE_PATH, 'welcome')
        await ui_test.human_delay()
        settings.set_string(SETTINGS_APPLICATION_MODE_PATH, 'modify')
        await ui_test.human_delay()
        settings.set_string(SETTINGS_APPLICATION_MODE_PATH, 'comment')
        await ui_test.human_delay()
        settings.set_string(SETTINGS_APPLICATION_MODE_PATH, 'modify')
        await ui_test.human_delay()

    async def test_menu_helper_widget_menu(self):
        import omni.kit.menu.utils
        omni.kit.menu.utils.add_menu_items([], name='test widget')

        from ..menu_helper import MenuHelper
        menu_helper = MenuHelper()
        menu_helper.destroy()

    async def test_startup_expand_viewport(self):
        from ..setup import SETTINGS_STARTUP_EXPAND_VIEWPORT

        import carb.settings
        settings = carb.settings.get_settings()

        orig_value = settings.get(SETTINGS_STARTUP_EXPAND_VIEWPORT)
        settings.set_bool(SETTINGS_STARTUP_EXPAND_VIEWPORT, True)

        manager = omni.kit.app.get_app().get_extension_manager()
        manager.set_extension_enabled(ext_id, False)
        await ui_test.human_delay()
        self.assertFalse(manager.is_extension_enabled(ext_id))

        manager.set_extension_enabled(ext_id, True)
        await ui_test.human_delay()
        self.assertTrue(manager.is_extension_enabled(ext_id))

        settings.set_bool(SETTINGS_STARTUP_EXPAND_VIEWPORT, orig_value)

        manager.set_extension_enabled(ext_id, False)
        await ui_test.human_delay()
        self.assertFalse(manager.is_extension_enabled(ext_id))

        manager.set_extension_enabled(ext_id, True)
        await ui_test.human_delay()
        self.assertTrue(manager.is_extension_enabled(ext_id))

    async def test_navigation_invalid_dict(self):
        from ..navigation import Navigation

        navigation = Navigation()
        navigation._show_tooltips = False
        navigation._dict = 42
        navigation._on_application_mode_changed(None, None)
        navigation._on_showtips_click()

    async def test_navigation_current_tool_mode_change(self):
        from ..navigation import CURRENT_TOOL_PATH, APPLICATION_MODE_PATH

        import carb.settings
        settings = carb.settings.get_settings()

        settings.set_string(APPLICATION_MODE_PATH, 'modify')
        await ui_test.human_delay()

        settings.set_string(CURRENT_TOOL_PATH, 'markup')
        await ui_test.human_delay()

        settings.set_string(CURRENT_TOOL_PATH, 'navigation')
        await ui_test.human_delay()

        settings.set_string(CURRENT_TOOL_PATH, 'markup')
        await ui_test.human_delay()

        settings.set_string(CURRENT_TOOL_PATH, 'welcome')
        await ui_test.human_delay()

        settings.set_string(CURRENT_TOOL_PATH, 'navigation')
        await ui_test.human_delay()

        settings.set_string(CURRENT_TOOL_PATH, 'markup')
        await ui_test.human_delay()

        settings.set_string(CURRENT_TOOL_PATH, 'navigation')
        await ui_test.human_delay()

    async def test_setup_clear_startup_scene_edits(self):
        from ..setup import _clear_startup_scene_edits
        await _clear_startup_scene_edits()

        import omni.usd
        self.assertFalse(omni.usd.get_context().has_pending_edit())

    async def test_stage_template(self):
        import omni.kit.stage_templates
        omni.kit.stage_templates.new_stage(template='SunnySky')
