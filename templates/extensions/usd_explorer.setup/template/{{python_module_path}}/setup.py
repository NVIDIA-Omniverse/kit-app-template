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
import inspect
import os
import weakref
import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import cast, Optional

import omni.client
import omni.ext
import omni.kit.menu.utils
import omni.kit.app
import omni.kit.context_menu
import omni.kit.ui
import omni.usd

from omni.kit.quicklayout import QuickLayout
from omni.kit.menu.utils import MenuLayout, MenuItemDescription
from omni.kit.window.title import get_main_window_title
from omni.kit.viewport.menubar.core import get_instance as get_mb_inst, DEFAULT_MENUBAR_NAME
from omni.kit.viewport.menubar.core.viewport_menu_model import ViewportMenuModel
from omni.kit.viewport.utility import get_active_viewport, get_active_viewport_window, disable_selection

import carb
import carb.settings
import carb.dictionary
import carb.events
import carb.tokens
import carb.input

import omni.kit.imgui as _imgui

from .navigation import Navigation
from .menu_helper import MenuHelper
from .menubar_helper import MenubarHelper
from .stage_template import SunnySkyStage
from .ui_state_manager import UIStateManager

SETTINGS_PATH_FOCUSED = "/app/workspace/currentFocused"
APPLICATION_MODE_PATH = "/app/application_mode"
MODAL_TOOL_ACTIVE_PATH = "/app/tools/modal_tool_active"
CURRENT_TOOL_PATH = "/app/viewport/currentTool"
ROOT_WINDOW_NAME = "DockSpace"
ICON_PATH = carb.tokens.get_tokens_interface().resolve("${% raw %}{{% endraw %}{{ extension_name }}{% raw %}}{% endraw %}/data/icons")
SETTINGS_STARTUP_EXPAND_VIEWPORT = "/app/startup/expandViewport"
VIEWPORT_CONTEXT_MENU_PATH = "/exts/omni.kit.window.viewport/showContextMenu"
TELEPORT_VISIBLE_PATH = "/persistent/exts/omni.kit.viewport.navigation.teleport/visible"


async def _load_layout_startup(
        layout_file: str, keep_windows_open: bool = False
    ):
    """Loads the startup layout file."""
    try:
        # few frames delay to avoid the conflict with the layout of
        # omni.kit.mainwindow
        for _ in range(3):
            await omni.kit.app.get_app().next_update_async()
        QuickLayout.load_file(layout_file, keep_windows_open)

        # WOR: some layout don't happy collectly the first time
        await omni.kit.app.get_app().next_update_async()
        QuickLayout.load_file(layout_file, keep_windows_open)
    except Exception as exc:  # pragma: no coverthrow an exception)
        carb.log_warn(f"Failed to load layout {layout_file}: {exc}")


async def _load_layout(layout_file: str, keep_windows_open: bool = False):
    """Load a layout file and catch any exceptions that occur."""
    try:
        # few frames delay to avoid the conflict with the layout of
        # omni.kit.mainwindow
        for i in range(3):
            await omni.kit.app.get_app().next_update_async()
        QuickLayout.load_file(layout_file, keep_windows_open)

    except Exception as exc:  # pragma: no coverthrow an exception)
        carb.log_warn(f"Failed to load layout {layout_file}: {exc}")


async def _clear_startup_scene_edits():
    try:
        # This could possibly be a smaller value.
        # I want to ensure this happens after RTX startup
        for _ in range(50):
            await omni.kit.app.get_app().next_update_async()
        omni.usd.get_context().set_pending_edit(False)
    except Exception as exc:  # pragma: no cover
        carb.log_warn(f"Failed to clear stage edits on startup: {exc}")


# This extension is mostly loading the Layout updating menu
class SetupExtension(omni.ext.IExt):
    """Setup extension for USD Explorer."""
    # ext_id is current extension id. It can be used with extension manager to
    # query additional information, like where this extension is located
    # on filesystem.

    @property
    def _app(self):
        """Return the app instance."""
        return omni.kit.app.get_app()

    @property
    def _settings(self):
        """Return the settings instance."""
        return carb.settings.get_settings()

    def on_startup(self, ext_id: str):
        """Setup the extension on startup."""
        self._ext_id = ext_id
        self._menubar_helper = MenubarHelper()
        self._menu_helper = MenuHelper()

        # using imgui directly to adjust some color and Variable
        imgui = _imgui.acquire_imgui()

        # match Create overides
        imgui.push_style_color(
            _imgui.StyleColor.ScrollbarGrab,
            carb.Float4(0.4, 0.4, 0.4, 1)
        )
        imgui.push_style_color(
            _imgui.StyleColor.ScrollbarGrabHovered,
            carb.Float4(0.6, 0.6, 0.6, 1)
        )
        imgui.push_style_color(
            _imgui.StyleColor.ScrollbarGrabActive,
            carb.Float4(0.8, 0.8, 0.8, 1)
        )

        # DockSplitterSize is the variable that drive the size of the Dock
        # Split connection
        imgui.push_style_var_float(_imgui.StyleVar.DockSplitterSize, 2)

        # setup the Layout for your app
        self._layouts_path = carb.tokens.get_tokens_interface().resolve("${% raw %}{{% endraw %}{{ extension_name }}{% raw %}}{% endraw %}/layouts")
        layout_file = Path(self._layouts_path).joinpath(f"{self._settings.get('/app/layout/name')}.json")
        asyncio.ensure_future(_load_layout_startup(f"{layout_file}", True))

        self.review_layout_path = str(
            Path(self._layouts_path) / "comment_layout.json"
        )
        self.default_layout_path = str(
            Path(self._layouts_path) / "default.json"
        )
        self.layout_user_path = str(
            Path(self._layouts_path) / "layout_user.json"
        )

        # remove the user defined layout so that we always load the default
        # layout when startup
        if not self._settings.get_as_bool('/app/ovc_deployment'):
            with suppress(FileNotFoundError):
                os.remove(self.layout_user_path)

        # setup the menu and their layout
        self._layout_menu_items = []
        self._layout_file_menu()
        self._menu_layout = []
        if self._settings.get_as_bool('/app/view/debug/menus'):
            self._layout_menu()

        # setup the Application Title
        window_title = get_main_window_title()
        if window_title:
            window_title.set_app_version("{{ version }}")

        # self._context_menu()
        self._register_my_menu()
        self._navigation = Navigation()
        self._navigation.on_startup(ext_id)

        self._application_mode_changed_sub = \
            self._settings.subscribe_to_node_change_events(
                APPLICATION_MODE_PATH,
                weakref.proxy(self)._on_application_mode_changed
            )

        self._set_viewport_menubar_visibility(False)
        asyncio.ensure_future(_clear_startup_scene_edits())

        self._usd_context = omni.usd.get_context()
        self._stage_event_sub = \
            self._usd_context.get_stage_event_stream().create_subscription_to_pop(
                self._on_stage_open_event, name="TeleportDefaultOn"
            )
        if self._settings.get_as_bool(SETTINGS_STARTUP_EXPAND_VIEWPORT):
            self._set_viewport_fill_on()

        self._stage_templates = [SunnySkyStage()]
        disable_selection(get_active_viewport())

        self._ui_state_manager = UIStateManager()
        self._setup_ui_state_changes()
        omni.kit.menu.utils.add_layout([
            MenuLayout.Menu("Window", [
                MenuLayout.Item(
                    "Viewport", source="Window/Viewport/Viewport 1"
                ),
                MenuLayout.Item("Playlist", remove=True),
                MenuLayout.Item("Layout", remove=True),
                MenuLayout.Sort(
                    exclude_items=["Extensions"], sort_submenus=True
                ),
            ])
        ])

        def show_documentation(*_args):
            """Open the documentation in a web browser."""
            webbrowser.open("https://docs.omniverse.nvidia.com/explorer")
        self._help_menu_items = [
            MenuItemDescription(
                name="Documentation",
                onclick_fn=show_documentation,
                appear_after=[omni.kit.menu.utils.MenuItemOrder.FIRST]
            )
        ]
        omni.kit.menu.utils.add_menu_items(self._help_menu_items, name="Help")

    def _on_stage_open_event(self, event: carb.events.IEvent):
        """Callback to clear tools and switch the app mode after a new stage
        is opened."""
        if event.type == int(omni.usd.StageEventType.OPENED):
            app_mode = self._settings.get_as_string(
                APPLICATION_MODE_PATH
            ).lower()

            # exit all tools
            self._settings.set(CURRENT_TOOL_PATH, "none")

            if app_mode == "review":
                asyncio.ensure_future(self._stage_post_open_teleport_toggle())

            # toggle RMB viewport context menu based on application mode
            value = False if app_mode == "review" else True
            self._settings.set(VIEWPORT_CONTEXT_MENU_PATH, value)

    # teleport is activated after loading a stage and app is in Review mode
    async def _stage_post_open_teleport_toggle(self):
        """Toggle the teleport tool after a stage is opened."""
        await self._app.next_update_async()
        if hasattr(self, "_usd_context") and self._usd_context is not None and not self._usd_context.is_new_stage():
            self._settings.set(
                "/exts/omni.kit.viewport.navigation.core/activeOperation",
                "teleport"
            )

    def _set_viewport_fill_on(self):
        """Set the viewport fill on."""
        vp_window = get_active_viewport_window()
        vp_widget = vp_window.viewport_widget if vp_window else None
        if vp_widget:
            vp_widget.expand_viewport = True

    def _set_viewport_menubar_visibility(self, show: bool):
        """Set the viewport menubar visibility."""
        mb_inst = get_mb_inst()
        if mb_inst and hasattr(mb_inst, "get_menubar"):
            main_menubar = mb_inst.get_menubar(DEFAULT_MENUBAR_NAME)
            if main_menubar.visible_model.as_bool != show:
                main_menubar.visible_model.set_value(show)
        ViewportMenuModel()._item_changed(None)

    def _on_application_mode_changed(
            self,
            item: carb.dictionary.Item,
            _typ: carb.settings.ChangeEventType
        ):
        """Callback for when the application mode changes."""
        if self._settings.get_as_string(APPLICATION_MODE_PATH).lower() == "review":
            omni.usd.get_context().get_selection().clear_selected_prim_paths()
            disable_selection(get_active_viewport())

        current_mode: str = cast(str, item.get_dict())
        asyncio.ensure_future(self.defer_load_layout(current_mode))

    async def defer_load_layout(self, current_mode: str):
        """Defer loading the layout based on the current mode."""
        keep_windows = True
        # Focus Mode Toolbar
        # current_mode not in ("review", "layout"))
        self._settings.set_bool(SETTINGS_PATH_FOCUSED, True)

        # Turn off all tools and modal
        self._settings.set_string(CURRENT_TOOL_PATH, "none")
        self._settings.set_bool(MODAL_TOOL_ACTIVE_PATH, False)

        if current_mode == "review":
            # save the current layout for restoring later if switch back
            QuickLayout.save_file(self.layout_user_path)
            # we don't want to keep any windows except the ones which are
            # visible in self.review_layout_path
            await _load_layout(self.review_layout_path, False)
        else:  # current_mode == "layout":
            # check if there is any user modified layout, if yes use that one
            layout_filename = self.default_layout_path
            if not self._settings.get_as_bool('/app.ovc_deployment') and os.path.exists(self.layout_user_path):
                layout_filename = self.layout_user_path
            await _load_layout(layout_filename, keep_windows)

        self._set_viewport_menubar_visibility(current_mode == "layout")

    def _setup_ui_state_changes(self):
        """Setup the UI state changes."""
        windows_to_hide_on_modal = ["Measure", "Section", "Waypoints"]
        self._ui_state_manager.add_hide_on_modal(
            window_names=windows_to_hide_on_modal, restore=True
        )

        window_titles = ["Markups", "Waypoints"]
        for window in window_titles:
            setting_name = f'/exts/omni.usd_explorer.setup/{window}/visible'
            self._ui_state_manager.add_window_visibility_setting(
                window, setting_name
            )

        # toggle icon visibilites based on window visibility
        self._ui_state_manager.add_settings_copy_dependency(
            source_path="/exts/omni.usd_explorer.setup/Markups/visible",
            target_path="/exts/omni.kit.markup.core/show_icons",
        )

        self._ui_state_manager.add_settings_copy_dependency(
            source_path="/exts/omni.usd_explorer.setup/Waypoints/visible",
            target_path="/exts/omni.kit.waypoint.core/show_icons",
        )

    def _custom_quicklayout_menu(self):
        # we setup a simple ways to Load custom layout from the exts
        def add_layout_menu_entry(name, parameter, key):
            """Add a layout menu entry."""
            layouts_path = carb.tokens.get_tokens_interface().resolve("${% raw %}{{% endraw %}{{ extension_name }}{% raw %}}{% endraw %}/layouts")

            menu_path = f"Layout/{name}"

            if inspect.isfunction(parameter):  # pragma: no cover
                menu_dict = omni.kit.menu.utils.build_submenu_dict(
                    [
                        MenuItemDescription(name=f"Layout/{name}",
                                            onclick_fn=lambda: asyncio.ensure_future(parameter()),
                                            hotkey=(carb.input.KEYBOARD_MODIFIER_FLAG_CONTROL, key)),
                    ]
                )
            else:
                menu_dict = omni.kit.menu.utils.build_submenu_dict(
                    [
                        MenuItemDescription(name=f"Layout/{name}",
                                            onclick_fn=lambda: asyncio.ensure_future(_load_layout(f"{layouts_path}/{parameter}.json")),
                                            hotkey=(carb.input.KEYBOARD_MODIFIER_FLAG_CONTROL, key)),
                    ]
                )

            # add menu
            for group in menu_dict:
                omni.kit.menu.utils.add_menu_items(menu_dict[group], group)

            self._layout_menu_items.append(menu_dict)

        add_layout_menu_entry(
            "Reset Layout", "default", carb.input.KeyboardInput.KEY_1
        )
        add_layout_menu_entry(
            "Viewport Only", "viewport_only", carb.input.KeyboardInput.KEY_2
        )
        add_layout_menu_entry(
            "Markup Editor", "markup_editor", carb.input.KeyboardInput.KEY_3
        )

    def _register_my_menu(self):
        """Gets the context menu and adds the menu items."""
        context_menu: Optional[omni.kit.context_menu.ContextMenuExtension] = \
            omni.kit.context_menu.get_instance()
        if not context_menu:  # pragma: no cover
            return

    def _layout_file_menu(self):
        """Setup the file menu layout."""
        self._menu_file_layout = [
            MenuLayout.Menu(
                "File",
                [
                    MenuLayout.Item("New"),
                    MenuLayout.Item("New From Stage Template"),
                    MenuLayout.Item("Open"),
                    MenuLayout.Item("Open Recent"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Re-open with New Edit Layer"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Share"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Save"),
                    MenuLayout.Item("Save As..."),
                    MenuLayout.Item("Save With Options"),
                    MenuLayout.Item("Save Selected"),
                    MenuLayout.Item("Save Flattened As...", remove=True),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Collect As..."),
                    MenuLayout.Item("Export"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Import"),
                    MenuLayout.Item("Add Reference"),
                    MenuLayout.Item("Add Payload"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Exit"),
                ]
            )
        ]
        omni.kit.menu.utils.add_layout(self._menu_file_layout)

    def _layout_menu(self):
        """Layout the Window menu."""
        self._menu_layout = [
            MenuLayout.Menu(
                "Window",
                [
                    MenuLayout.SubMenu(
                        "Animation",
                        [
                            MenuLayout.Item("Timeline"),
                            MenuLayout.Item("Sequencer"),
                            MenuLayout.Item("Curve Editor"),
                            MenuLayout.Item("Retargeting"),
                            MenuLayout.Item("Animation Graph"),
                            MenuLayout.Item("Animation Graph Samples"),
                        ],
                    ),
                    MenuLayout.SubMenu(
                        "Layout",
                        [
                            MenuLayout.Item("Quick Save", remove=True),
                            MenuLayout.Item("Quick Load", remove=True),
                        ],
                    ),
                    MenuLayout.SubMenu(
                        "Browsers",
                        [
                            MenuLayout.Item(
                                "Content", source="Window/Content"
                            ),
                            MenuLayout.Item("Materials"),
                            MenuLayout.Item("Skies"),
                        ],
                    ),
                    MenuLayout.SubMenu(
                        "Rendering",
                        [
                            MenuLayout.Item("Render Settings"),
                            MenuLayout.Item("Movie Capture"),
                            MenuLayout.Item("MDL Material Graph"),
                            MenuLayout.Item("Tablet XR"),
                        ],
                    ),
                    MenuLayout.SubMenu(
                        "Simulation",
                        [
                            MenuLayout.Group(
                                "Flow",
                                [
                                    MenuLayout.Item(
                                        "Presets",
                                        source="Window/Flow/Presets"
                                    ),
                                    MenuLayout.Item(
                                        "Monitor",
                                        source="Window/Flow/Monitor"
                                    ),
                                ],
                            ),
                            MenuLayout.Group(
                                "Blast",
                                [
                                    MenuLayout.Item(
                                        "Settings",
                                        source="Window/Blast/Settings"
                                    ),
                                    MenuLayout.SubMenu(
                                        "Documentation",
                                        [
                                            MenuLayout.Item(
                                                "Kit UI",
                                                source="Window/Blast/Documentation/Kit UI"
                                            ),
                                            MenuLayout.Item(
                                                "Programming",
                                                source="Window/Blast/Documentation/Programming"
                                            ),
                                            MenuLayout.Item(
                                                "USD Schemas",
                                                source="Window/Blast/Documentation/USD Schemas"
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            MenuLayout.Item("Debug"),
                            # MenuLayout.Item("Performance"),
                            MenuLayout.Group(
                                "Physics",
                                [
                                    MenuLayout.Item("Demo Scenes"),
                                    MenuLayout.Item(
                                        "Settings",
                                        source="Window/Physics/Settings"
                                    ),
                                    MenuLayout.Item("Debug"),
                                    MenuLayout.Item("Test Runner"),
                                    MenuLayout.Item("Character Controller"),
                                    MenuLayout.Item("OmniPVD"),
                                    MenuLayout.Item("Physics Helpers"),
                                ],
                            ),
                        ],
                    ),
                    MenuLayout.SubMenu(
                        "Utilities",
                        [
                            MenuLayout.Item("Console"),
                            MenuLayout.Item("Profiler"),
                            MenuLayout.Item("USD Paths"),
                            MenuLayout.Item("Statistics"),
                            MenuLayout.Item("Activity Monitor"),
                        ],
                    ),
                    # Remove 'Viewport 2' entry
                    MenuLayout.SubMenu(
                        "Viewport",
                        [
                            MenuLayout.Item("Viewport 2", remove=True),
                        ],
                    ),
                    MenuLayout.Sort(exclude_items=["Extensions"]),
                    MenuLayout.Item("New Viewport Window", remove=True),
                ],
            ),
            # that is you enable the Quick Layout Menu
            MenuLayout.Menu(
                "Layout",
                [
                    MenuLayout.Item("Default", source="Reset Layout"),
                    MenuLayout.Item("Viewport Only"),
                    MenuLayout.Item("Markup Editor"),
                    MenuLayout.Item("Waypoint Viewer"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item(
                        "UI Toggle Visibility",
                        source="Window/UI Toggle Visibility"
                    ),
                    MenuLayout.Item(
                        "Fullscreen Mode",
                        source="Window/Fullscreen Mode"
                    ),
                    MenuLayout.Seperator(),
                    MenuLayout.Item(
                        "Save Layout",
                        source="Window/Layout/Save Layout..."
                    ),
                    MenuLayout.Item(
                        "Load Layout",
                        source="Window/Layout/Load Layout..."
                    ),
                ],
            ),
            MenuLayout.Menu(
                "Tools", [MenuLayout.SubMenu("Animation", remove=True)]
            ),
        ]
        omni.kit.menu.utils.add_layout(self._menu_layout)

        # if you want to support the Quick Layout Menu
        self._custom_quicklayout_menu()

    def on_shutdown(self):
        """Shutdown the extension."""
        if self._menu_layout:
            omni.kit.menu.utils.remove_layout(self._menu_layout)
            self._menu_layout.clear()

        for menu_dict in self._layout_menu_items:
            for group in menu_dict:
                omni.kit.menu.utils.remove_menu_items(menu_dict[group], group)

        self._layout_menu_items.clear()
        self._navigation.on_shutdown()
        del self._navigation
        self._settings.unsubscribe_to_change_events(
            self._application_mode_changed_sub
        )
        del self._application_mode_changed_sub

        self._stage_event_sub = None

        # From View setup
        self._menubar_helper.destroy()
        if self._menu_helper and hasattr(self._menu_helper, "destroy"):
            self._menu_helper.destroy()
        self._menu_helper = None

        self._stage_templates = []
