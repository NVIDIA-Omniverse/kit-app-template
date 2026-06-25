# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import asyncio

import carb
import carb.dictionary
import carb.settings
import carb.tokens
import omni.ext
import omni.kit.actions.core
import omni.kit.app
import omni.ui as ui
from omni.kit.viewport.navigation.core import (
    NAVIGATION_TOOL_OPERATION_ACTIVE,
    ViewportNavigationTooltip,
    get_navigation_bar,
)

__all__ = ["Navigation"]


CURRENT_TOOL_PATH = "/app/viewport/currentTool"
SETTING_NAVIGATION_ROOT = "/exts/omni.kit.tool.navigation/"
NAVIGATION_BAR_VISIBLE_PATH = \
    "/exts/omni.kit.viewport.navigation.core/isVisible"
APPLICATION_MODE_PATH = "/app/application_mode"
CAPTURE_VISIBLE_PATH = \
    "/persistent/exts/omni.kit.viewport.navigation.capture/visible"
MARKUP_VISIBLE_PATH = \
    "/persistent/exts/omni.kit.viewport.navigation.markup/visible"
MEASURE_VISIBLE_PATH = \
    "/persistent/exts/omni.kit.viewport.navigation.measure/visible"
SECTION_VISIBLE_PATH = \
"/persistent/exts/omni.kit.viewport.navigation.section/visible"
TELEPORT_SEPARATOR_VISIBLE_PATH = \
    "/persistent/exts/omni.kit.viewport.navigation.teleport/spvisible"
WAYPOINT_VISIBLE_PATH = \
    "/persistent/exts/omni.kit.viewport.navigation.waypoint/visible"
VIEWPORT_CONTEXT_MENU_PATH = \
    "/exts/omni.kit.window.viewport/showContextMenu"
MENUBAR_APP_MODES_PATH = \
    "/exts/omni.kit.usd_explorer.main.menubar/include_modify_mode"
WELCOME_WINDOW_VISIBLE_PATH = \
    "/exts/omni.kit.usd_explorer.window.welcome/visible"
ACTIVE_OPERATION_PATH = \
    "/exts/omni.kit.viewport.navigation.core/activeOperation"


class Navigation:
    """Manages the navigation bar and its visibility."""
    NAVIGATION_BAR_NAME = None

    def __init__(self):
        self._ext_name = None
        self._settings = None
        self._navigation_bar = None
        self._tool_bar_button = None
        self._dict = None
        self._panel_visible = None
        self._viewport_welcome_window_visibility_changed_sub = None
        self._application_mode_changed_sub = None
        self._show_tooltips = None
        self._nav_bar_visibility_sub = None

    # ext_id is current extension id. It can be used with extension manager
    # to query additional information, like where this extension is located
    # on filesystem.
    def on_startup(self, ext_id: str):
        """Initialize the navigation bar and set up event subscriptions."""
        sections = ext_id.split("-")
        self._ext_name = sections[0]

        self._settings = carb.settings.get_settings()
        self._navigation_bar = get_navigation_bar()

        self._tool_bar_button = None

        self._dict = carb.dictionary.get_dictionary()
        self._panel_visible = True
        self._navigation_bar.show()
        self._settings.set(CURRENT_TOOL_PATH, "navigation")
        self._settings.set(NAVIGATION_TOOL_OPERATION_ACTIVE, "teleport")

        self._viewport_welcome_window_visibility_changed_sub = \
            self._settings.subscribe_to_node_change_events(
                WELCOME_WINDOW_VISIBLE_PATH,
                self._on_welcome_window_visibility_change
            )

        self._settings.set(MARKUP_VISIBLE_PATH, True)
        self._settings.set(WAYPOINT_VISIBLE_PATH, True)
        self._settings.set(TELEPORT_SEPARATOR_VISIBLE_PATH, True)
        self._settings.set(CAPTURE_VISIBLE_PATH, True)
        self._settings.set(MEASURE_VISIBLE_PATH, True)
        self._settings.set(SECTION_VISIBLE_PATH, True)

        self._application_mode_changed_sub = \
            self._settings.subscribe_to_node_change_events(
                APPLICATION_MODE_PATH, self._on_application_mode_changed
            )

        self._show_tooltips = False
        self._nav_bar_visibility_sub = \
            self._settings.subscribe_to_node_change_events(
                NAVIGATION_BAR_VISIBLE_PATH, self._delay_reset_tooltip
            )

    _prev_navbar_vis = None
    _prev_tool = None
    _prev_operation = None

    def _on_welcome_window_visibility_change(
            self, item: carb.dictionary.Item, *_
    ):
        """Callback for when the welcome window visibility changes."""
        if not isinstance(self._dict, (carb.dictionary.IDictionary, dict)):
            return

        welcome_window_vis = self._dict.get(item)

        # preserve the state of the navbar upon closing the Welcome window if
        # the app is in Layout mode
        if self._settings.get_as_string(APPLICATION_MODE_PATH).lower() == "layout":
            # preserve the state of the navbar visibility
            if welcome_window_vis:
                self._prev_navbar_vis = \
                    self._settings.get_as_bool(NAVIGATION_BAR_VISIBLE_PATH)
                self._settings.set(
                    NAVIGATION_BAR_VISIBLE_PATH, not (welcome_window_vis)
                )
                self._prev_tool = self._settings.get(CURRENT_TOOL_PATH)
                self._prev_operation = \
                    self._settings.get(ACTIVE_OPERATION_PATH)
            else:  # restore the state of the navbar visibility
                if self._prev_navbar_vis is not None:
                    self._settings.set(
                        NAVIGATION_BAR_VISIBLE_PATH, self._prev_navbar_vis
                    )
                    self._prev_navbar_vis = None
                if self._prev_tool is not None:
                    self._settings.set(CURRENT_TOOL_PATH, self._prev_tool)
                if self._prev_operation is not None:
                    self._settings.set(
                        ACTIVE_OPERATION_PATH, self._prev_operation
                    )
        else:
            if welcome_window_vis:
                self._settings.set(NAVIGATION_TOOL_OPERATION_ACTIVE, "none")
            else:
                self._settings.set(
                    NAVIGATION_TOOL_OPERATION_ACTIVE, "teleport"
                )

            self._settings.set(
                NAVIGATION_BAR_VISIBLE_PATH, not (welcome_window_vis)
            )

    def _on_application_mode_changed(self, item: carb.dictionary.Item, *_):
        """Callback for when the application mode changes."""
        if not isinstance(self._dict, (carb.dictionary.IDictionary, dict)):
            return

        current_mode = self._dict.get(item)
        self._test = asyncio.ensure_future(self._switch_by_mode(current_mode))

    async def _switch_by_mode(self, current_mode: str):
        """Switch application mode based on provided mode."""
        await omni.kit.app.get_app().next_update_async()
        state = True if current_mode == "review" else False
        self._settings.set(NAVIGATION_BAR_VISIBLE_PATH, state)
        # toggle RMB viewport context menu
        self._settings.set(VIEWPORT_CONTEXT_MENU_PATH, not (state))
        self._delay_reset_tooltip(None)

    def _delay_reset_tooltip(self, *_):
        """Delay setting the tooltip visibility."""
        async def delay_set_tooltip():
            for _i in range(4):
                await omni.kit.app.get_app().next_update_async()
            ViewportNavigationTooltip.set_visible(self._show_tooltips)
        asyncio.ensure_future(delay_set_tooltip())

    def _on_showtips_click(self, *_):
        """Toggle the visibility of the tooltips."""
        self._show_tooltips = not self._show_tooltips
        ViewportNavigationTooltip.set_visible(self._show_tooltips)

    def on_shutdown(self):
        """Clean up event subscriptions."""
        self._navigation_bar = None
        self._viewport_welcome_window_visibility_changed_sub = None
        self._settings.unsubscribe_to_change_events(
            self._application_mode_changed_sub
        )
        self._application_mode_changed_sub = None
        self._dict = None
