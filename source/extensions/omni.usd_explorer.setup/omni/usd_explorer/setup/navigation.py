import asyncio

import carb
import carb.settings
import carb.tokens
import carb.dictionary
import omni.kit.app
import omni.ext
import omni.ui as ui
import omni.kit.actions.core
from omni.kit.viewport.navigation.core import (
    NAVIGATION_TOOL_OPERATION_ACTIVE,
    ViewportNavigationTooltip,
    get_navigation_bar,
)

__all__ = ["Navigation"]


CURRENT_TOOL_PATH = "/app/viewport/currentTool"
SETTING_NAVIGATION_ROOT = "/exts/omni.kit.tool.navigation/"
NAVIGATION_BAR_VISIBLE_PATH = "/exts/omni.kit.viewport.navigation.core/isVisible"
APPLICATION_MODE_PATH = "/app/application_mode"
WALK_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.walk/visible"
CAPTURE_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.capture/visible"
MARKUP_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.markup/visible"
MEASURE_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.measure/visible"
SECTION_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.section/visible"
TELEPORT_SEPARATOR_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.teleport/spvisible"
WAYPOINT_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.waypoint/visible"
VIEWPORT_CONTEXT_MENU_PATH = "/exts/omni.kit.window.viewport/showContextMenu"
MENUBAR_APP_MODES_PATH = "/exts/omni.kit.usd_presenter.main.menubar/include_modify_mode"
WELCOME_WINDOW_VISIBLE_PATH = "/exts/omni.kit.usd_presenter.window.welcome/visible"
ACTIVE_OPERATION_PATH = "/exts/omni.kit.viewport.navigation.core/activeOperation"

class Navigation:
    NAVIGATION_BAR_NAME = None

    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def on_startup(self, ext_id: str) -> None:
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

        self._viewport_welcome_window_visibility_changed_sub = self._settings.subscribe_to_node_change_events(
            WELCOME_WINDOW_VISIBLE_PATH, self._on_welcome_window_visibility_change
        )

        # OMFP-1799 Set nav bar visibility defaults. These should remain fixed now.
        self._settings.set(WALK_VISIBLE_PATH, False)
        self._settings.set(MARKUP_VISIBLE_PATH, True)
        self._settings.set(WAYPOINT_VISIBLE_PATH, True)
        self._settings.set(TELEPORT_SEPARATOR_VISIBLE_PATH, True)
        self._settings.set(CAPTURE_VISIBLE_PATH, True)
        self._settings.set(MEASURE_VISIBLE_PATH, True)
        self._settings.set(SECTION_VISIBLE_PATH, True)

        self._application_mode_changed_sub = self._settings.subscribe_to_node_change_events(
            APPLICATION_MODE_PATH, self._on_application_mode_changed
        )

        self._show_tooltips = False
        self._nav_bar_visibility_sub = self._settings.subscribe_to_node_change_events(
            NAVIGATION_BAR_VISIBLE_PATH, self._delay_reset_tooltip)

    _prev_navbar_vis = None
    _prev_tool = None
    _prev_operation = None
    def _on_welcome_window_visibility_change(self, item: carb.dictionary.Item, *_) -> None:
        if not isinstance(self._dict, (carb.dictionary.IDictionary, dict)):
            return

        welcome_window_vis = self._dict.get(item)

        # preserve the state of the navbar upon closing the Welcome window if the app is in Layout mode
        if self._settings.get_as_string(APPLICATION_MODE_PATH).lower() == "layout":
            # preserve the state of the navbar visibility
            if welcome_window_vis:
                self._prev_navbar_vis = self._settings.get_as_bool(NAVIGATION_BAR_VISIBLE_PATH)
                self._settings.set(NAVIGATION_BAR_VISIBLE_PATH, not(welcome_window_vis))
                self._prev_tool = self._settings.get(CURRENT_TOOL_PATH)
                self._prev_operation = self._settings.get(ACTIVE_OPERATION_PATH)
            else: # restore the state of the navbar visibility
                if self._prev_navbar_vis is not None:
                    self._settings.set(NAVIGATION_BAR_VISIBLE_PATH, self._prev_navbar_vis)
                    self._prev_navbar_vis = None
                if self._prev_tool is not None:
                    self._settings.set(CURRENT_TOOL_PATH, self._prev_tool)
                if self._prev_operation is not None:
                    self._settings.set(ACTIVE_OPERATION_PATH, self._prev_operation)
            return
        else:
            if welcome_window_vis:
                self._settings.set(NAVIGATION_TOOL_OPERATION_ACTIVE, "none")
            else:
                self._settings.set(NAVIGATION_TOOL_OPERATION_ACTIVE, "teleport")

        self._settings.set(NAVIGATION_BAR_VISIBLE_PATH, not(welcome_window_vis))

    def _on_application_mode_changed(self, item: carb.dictionary.Item, *_) -> None:
        if not isinstance(self._dict, (carb.dictionary.IDictionary, dict)):
            return

        current_mode = self._dict.get(item)
        self._test = asyncio.ensure_future(self._switch_by_mode(current_mode))

    async def _switch_by_mode(self, current_mode: str) -> None:
        await omni.kit.app.get_app().next_update_async()
        state = True if current_mode == "review" else False
        self._settings.set(NAVIGATION_BAR_VISIBLE_PATH, state)
        self._settings.set(VIEWPORT_CONTEXT_MENU_PATH, not(state)) # toggle RMB viewport context menu
        self._delay_reset_tooltip(None)

    # OM-92161: Need to reset the tooltip when change the mode
    def _delay_reset_tooltip(self, *_) -> None:
        async def delay_set_tooltip() -> None:
            for _i in range(4):
                await omni.kit.app.get_app().next_update_async()  # type: ignore
            ViewportNavigationTooltip.set_visible(self._show_tooltips)
        asyncio.ensure_future(delay_set_tooltip())

    def _on_showtips_click(self, *_) -> None:
        self._show_tooltips = not self._show_tooltips
        ViewportNavigationTooltip.set_visible(self._show_tooltips)

    def on_shutdown(self) -> None:
        self._navigation_bar = None
        self._viewport_welcome_window_visibility_changed_sub = None
        self._settings.unsubscribe_to_change_events(self._application_mode_changed_sub)  # type:ignore
        self._application_mode_changed_sub = None
        self._dict = None
