# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import asyncio

import carb.settings
import omni.kit.app
import omni.kit.commands
import omni.kit.menu.utils
import omni.renderer_capture
from omni.kit.menu.utils import MenuLayout

SETTINGS_APPLICATION_MODE_PATH = "/app/application_mode"


class MenuHelper:
    """Helper class to manage the main menu layout based on the
    application mode."""
    def __init__(self):
        self._settings = carb.settings.get_settings()
        self._current_layout = None
        self._pending_layout = None
        self._changing_layout_task: asyncio.Task = None
        self._menu_layout_empty = []
        self._menu_layout_modify = []
        self._app_ready_sub = None

        omni.kit.menu.utils.add_hook(self._menu_hook)

        self._app_mode_sub = self._settings.subscribe_to_node_change_events(
            SETTINGS_APPLICATION_MODE_PATH, self._on_application_mode_changed
        )
        self._menu_hook()

    def destroy(self):
        """Tear down the menu helper."""
        omni.kit.menu.utils.remove_hook(self._menu_hook)

        if self._changing_layout_task and not self._changing_layout_task.done():
            self._changing_layout_task.cancel()
            self._changing_layout_task = None

        if self._app_mode_sub:
            self._settings.unsubscribe_to_change_events(self._app_mode_sub)
            self._app_mode_sub = None

        self._app_ready_sub = None

        if self._current_layout:
            omni.kit.menu.utils.remove_layout(self._current_layout)
            self._current_layout = None

    def _menu_hook(self, *args, **kwargs):
        """Get the menu instance and build the desired menu."""
        if self._settings.get_as_bool("/app/view/debug/menus"):
            return

        LAYOUT_EMPTY_ALLOWED_MENUS = set(["Developer",])
        LAYOUT_MODIFY_ALLOWED_MENUS = {
            "File", "Edit", "Window", "Tools", "Help", "Developer",
        }

        # make NEW list object instead of clear original
        # the original list may be held by self._current_layout and omni.kit.menu.utils
        self._menu_layout_empty = []
        self._menu_layout_modify = []

        menu_instance = omni.kit.menu.utils.get_instance()
        if not menu_instance:  # pragma: no cover
            return

        # Build new layouts using allowlists
        menu_defs, _menu_order, _menu_delegates = menu_instance.get_menu_data()

        for key in menu_defs:
            if key.lower().endswith("widget"):
                continue

            if key not in LAYOUT_EMPTY_ALLOWED_MENUS:
                self._menu_layout_empty.append(
                    MenuLayout.Menu(key, remove=True)
                )

            if key not in LAYOUT_MODIFY_ALLOWED_MENUS:
                self._menu_layout_modify.append(
                    MenuLayout.Menu(key, remove=True)
                )

            # Remove 'Viewport 2' entry
            if key == "Window":
                for menu_item_1 in menu_defs[key]:
                    for menu_item_2 in menu_item_1:
                        if menu_item_2.name == "Viewport":
                            menu_item_2.sub_menu = [mi for mi in
                                                    menu_item_2.sub_menu if
                                                    mi.name != "Viewport 2"]

        if self._changing_layout_task is None or self._changing_layout_task.done():
            self._changing_layout_task = \
                asyncio.ensure_future(self._delayed_change_layout())

    def _on_application_mode_changed(self, *args):
        """Callback for when the application mode changes."""
        if self._changing_layout_task is None or self._changing_layout_task.done():
            self._changing_layout_task = \
                asyncio.ensure_future(self._delayed_change_layout())

    async def _delayed_change_layout(self):
        """Delay the layout change to avoid omni.ui error."""
        mode = self._settings.get_as_string(SETTINGS_APPLICATION_MODE_PATH)
        if mode in ["present", "review"]:
            pending_layout = self._menu_layout_empty
        else:
            pending_layout = self._menu_layout_modify

        # Don't change layout inside of menu callback
        # _on_application_mode_changed omni.ui throws error
        if self._current_layout:
            # Here only check number of layout menu items and name of every of
            # layout menu item
            same_layout = len(self._current_layout) == len(pending_layout)
            if same_layout:
                for index, item in enumerate(self._current_layout):
                    if item.name != pending_layout[index].name:
                        same_layout = False
            if same_layout:
                return

            omni.kit.menu.utils.remove_layout(self._current_layout)
            self._current_layout = None

        omni.kit.menu.utils.add_layout(pending_layout)  # type: ignore
        self._current_layout = pending_layout.copy()

        self._changing_layout_task = None
