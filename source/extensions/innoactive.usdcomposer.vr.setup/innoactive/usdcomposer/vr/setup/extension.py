# Copyright (c) 2018-2020, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#

import asyncio
import logging
import os
import sys
from pathlib import Path

import carb.imgui as _imgui
import carb.input
import carb.settings
import carb.tokens
import omni.ext
import omni.kit.app
import omni.kit.commands
import omni.kit.menu.utils
import omni.kit.stage_templates as stage_templates
import omni.kit.ui
import omni.ui as ui
import omni.usd
from omni.kit.window.title import get_main_window_title

DATA_PATH = Path(carb.tokens.get_tokens_interface().resolve("${innoactive.usdcomposer.vr.setup}"))


async def _load_layout(layout_file: str, keep_windows_open=False):
    try:
        from omni.kit.quicklayout import QuickLayout

        # few frames delay to avoid the conflict with the layout of omni.kit.mainwindow
        for i in range(3):
            await omni.kit.app.get_app().next_update_async()
        QuickLayout.load_file(layout_file, keep_windows_open)

    except Exception as exc:
        pass

        QuickLayout.load_file(layout_file)


class CreateSetupExtension(omni.ext.IExt):
    """Create Final Configuration"""

    def on_startup(self, ext_id):
        """setup the window layout, menu, final configuration of the extensions etc"""
        self._settings = carb.settings.get_settings()
        self._menu_layout = []

        telemetry_logger = logging.getLogger("idl.telemetry.opentelemetry")
        telemetry_logger.setLevel(logging.ERROR)

        # this is a work around as some Extensions don't properly setup their default setting in time
        self._set_defaults()

        # adjust couple of viewport settings
        self._settings.set("/app/viewport/boundingBoxes/enabled", True)

        # Force enable Axis, Grid, Outline and Lights
        forceEnable = self._settings.get("/app/create/forceViewportSettings")
        if forceEnable:
            display_options = self._settings.get("/persistent/app/viewport/displayOptions")
            # Note: flags are from omni/kit/ViewportTypes.h
            kShowFlagAxis = 1 << 1
            kShowFlagGrid = 1 << 6
            kShowFlagSelectionOutline = 1 << 7
            kShowFlagLight = 1 << 8
            display_options = (
                display_options | (kShowFlagAxis) | (kShowFlagGrid) | (kShowFlagSelectionOutline) | (kShowFlagLight)
            )
            self._settings.set("/persistent/app/viewport/displayOptions", display_options)
            # Make sure these are in sync from changes above
            self._settings.set("/app/viewport/show/lights", True)
            self._settings.set("/app/viewport/grid/enabled", True)
            self._settings.set("/app/viewport/outline/enabled", True)

            # Make sure any action-graph setup locking out user from HUD does not persist across re-launch
            self._settings.set("/persistent/app/viewport/Viewport/Viewport0/hud/visible", True)
            self._settings.set("/persistent/app/viewport/Viewport 2/Viewport0/hud/visible", True)

        # These two settings do not co-operate well on ADA cards, so for
        # now simulate a toggle of the present thread on startup to work around
        if self._settings.get("/exts/omni.kit.renderer.core/present/enabled") and self._settings.get(
            "/exts/omni.kit.widget.viewport/autoAttach/mode"
        ):

            async def _toggle_present(settings, n_waits: int = 1):
                async def _toggle_setting(app, enabled: bool, n_waits: int):
                    for _ in range(n_waits):
                        await app.next_update_async()
                    settings.set("/exts/omni.kit.renderer.core/present/enabled", enabled)

                app = omni.kit.app.get_app()
                await _toggle_setting(app, False, n_waits)
                await _toggle_setting(app, True, n_waits)

            asyncio.ensure_future(_toggle_present(self._settings))

        # Setting and Saving FSD as a global change in preferences
        # Requires to listen for changes at the local path to update Composer's persistent path.
        fabric_app_setting = self._settings.get("/app/useFabricSceneDelegate")
        fabric_persistent_setting = self._settings.get("/persistent/app/useFabricSceneDelegate")
        fabric_enabled: bool = fabric_app_setting if fabric_persistent_setting == None else fabric_persistent_setting

        self._settings.set("/app/useFabricSceneDelegate", fabric_enabled)

        self._sub_fabric_delegate_changed = omni.kit.app.SettingChangeSubscription(
            "/app/useFabricSceneDelegate",
            self._on_fabric_delegate_changed
        )

        # Adjust the Window Title to show the Create Version
        window_title = get_main_window_title()

        app_version = self._settings.get("/app/version")
        if not app_version:
            app_version = open(carb.tokens.get_tokens_interface().resolve("${app}/../VERSION")).read()

        if app_version:
            if "+" in app_version:
                app_version, _ = app_version.split("+")

            # for RC version we remove some details
            PRODUCTION = self._settings.get("/privacy/externalBuild")
            if PRODUCTION:
                if "-" in app_version:
                    app_version, _ = app_version.split("-")
                window_title.set_app_version(app_version)
            else:
                window_title.set_app_version(app_version)

        # setup some imgui Style overide
        imgui = _imgui.acquire_imgui()
        imgui.push_style_color(_imgui.StyleColor.ScrollbarGrab, carb.Float4(0.4, 0.4, 0.4, 1))
        imgui.push_style_color(_imgui.StyleColor.ScrollbarGrabHovered, carb.Float4(0.6, 0.6, 0.6, 1))
        imgui.push_style_color(_imgui.StyleColor.ScrollbarGrabActive, carb.Float4(0.8, 0.8, 0.8, 1))

        imgui.push_style_var_float(_imgui.StyleVar.DockSplitterSize, 2)

        layout_file = f"{DATA_PATH}/layouts/default.json"

        # Setting to hack few things in test run. Ideally we shouldn't need it.
        test_mode = self._settings.get("/app/testMode")

        if not test_mode:
            self.__setup_window_task = asyncio.ensure_future(_load_layout(layout_file, True))

        self.__setup_property_window = asyncio.ensure_future(self.__property_window())

        self.__menu_update()

        if not test_mode and not self._settings.get("/app/content/emptyStageOnStart"):
            self.__await_new_scene = asyncio.ensure_future(self.__new_stage())

        startup_time = omni.kit.app.get_app_interface().get_time_since_start_s()
        self._settings.set("/crashreporter/data/startup_time", f"{startup_time}")

        def show_documentation(*x):
            import webbrowser
            webbrowser.open("https://docs.omniverse.nvidia.com/composer/latest/index.html")
        self._help_menu_items = [
            omni.kit.menu.utils.MenuItemDescription(name="Documentation",
                                                    onclick_fn=show_documentation,
                                                    appear_after=[omni.kit.menu.utils.MenuItemOrder.FIRST])
        ]
        omni.kit.menu.utils.add_menu_items(self._help_menu_items, name="Help")

    def _set_defaults(self):
        """this is trying to setup some defaults for extensions to avoid warning"""
        self._settings.set_default("/persistent/app/omniverse/bookmarks", {})
        self._settings.set_default("/persistent/app/stage/timeCodeRange", [0, 100])

        self._settings.set_default("/persistent/audio/context/closeAudioPlayerOnStop", False)

        self._settings.set_default("/persistent/app/primCreation/PrimCreationWithDefaultXformOps", True)
        self._settings.set_default("/persistent/app/primCreation/DefaultXformOpType", "Scale, Rotate, Translate")
        self._settings.set_default("/persistent/app/primCreation/DefaultRotationOrder", "ZYX")
        self._settings.set_default("/persistent/app/primCreation/DefaultXformOpPrecision", "Double")

        # omni.kit.property.tagging
        self._settings.set_default("/persistent/exts/omni.kit.property.tagging/showAdvancedTagView", False)
        self._settings.set_default("/persistent/exts/omni.kit.property.tagging/showHiddenTags", False)
        self._settings.set_default("/persistent/exts/omni.kit.property.tagging/modifyHiddenTags", False)

        self._settings.set_default(
            "/rtx/sceneDb/ambientLightIntensity", 0.0
        )  # set default ambientLight intensity to Zero

    def _on_fabric_delegate_changed(self, value: str, event_type: carb.settings.ChangeEventType):
        if event_type == carb.settings.ChangeEventType.CHANGED:
            enabled: bool = self._settings.get_as_bool("/app/useFabricSceneDelegate")
            self._settings.set("/persistent/app/useFabricSceneDelegate", enabled)

    async def __new_stage(self):

        # 10 frame delay to allow Layout
        for i in range(5):
            await omni.kit.app.get_app().next_update_async()

        if omni.usd.get_context().can_open_stage():
            stage_templates.new_stage(template=None)

    def _launch_app(self, app_id, console=True, custom_args=None):
        """launch another Kit app with the same settings"""
        import platform
        import subprocess
        import sys

        app_path = carb.tokens.get_tokens_interface().resolve("${app}")
        kit_file_path = os.path.join(app_path, app_id)

        # https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
        # Validate input from command line (detected in static analysis)
        kit_exe = sys.argv[0]
        if not os.path.exists(kit_exe):
            print(f"cannot find executable{kit_exe}")
            return

        launch_args = [kit_exe]
        launch_args += [kit_file_path]
        if custom_args:
            launch_args.extend(custom_args)

        # Pass all exts folders
        exts_folders = self._settings.get("/app/exts/folders")
        if exts_folders:
            for folder in exts_folders:
                launch_args.extend(["--ext-folder", folder])

        kwargs = {"close_fds": False}
        if platform.system().lower() == "windows":
            if console:
                kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(launch_args, **kwargs)

    def _show_ui_docs(self):
        """show the omniverse ui documentation as an external Application"""
        self._launch_app("omni.app.uidoc.kit")

    def _show_launcher(self):
        """show the omniverse ui documentation as an external Application"""
        self._launch_app("omni.create.launcher.kit", console=False, custom_args={"--/app/auto_launch=false"})

    async def __property_window(self):
        await omni.kit.app.get_app().next_update_async()
        import omni.kit.window.property as property_window_ext
        from omni.kit.property.usd import PrimPathWidget

        property_window = property_window_ext.get_window()
        property_window.set_scheme_delegate_layout(
            "Create Layout",
            ["basis_curves_prim", "path_prim", "material_prim", "xformable_prim", "shade_prim", "camera_prim"],
        )

        # expand width of path_items to "Instancable" doesn't get wrapped
        PrimPathWidget.set_path_item_padding(3.5)

    def __menu_update(self):
        from omni.kit.menu.utils import MenuLayout

        editor_menu = omni.kit.ui.get_editor_menu()

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
                            # MenuLayout.Item("Keyframer"),
                            # MenuLayout.Item("Recorder"),
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
                            MenuLayout.Item("Content", source="Window/Content"),
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
                            MenuLayout.Group("Flow", source="Window/Flow"),
                            MenuLayout.Group("Blast Destruction", source="Window/Blast"),
                            MenuLayout.Group("Blast Destruction", source="Window/Blast Destruction"),
                            MenuLayout.Group("Boom Collision Audio", source="Window/Boom"),
                            MenuLayout.Group("Boom Collision Audio", source="Window/Boom Collision Audio"),
                            MenuLayout.Group("Physics", source="Window/Physics"),
                        ],
                    ),
                    MenuLayout.SubMenu(
                        "Utilities",
                        [
                            MenuLayout.Item("Console"),
                            MenuLayout.Item("Profiler"),
                            MenuLayout.Item("USD Paths"),
                            MenuLayout.Item("Statistics"),
                            MenuLayout.Item("Activity Progress"),
                            MenuLayout.Item("Actions"),
                            MenuLayout.Item("Asset Validator"),
                        ],
                    ),
                    MenuLayout.Sort(exclude_items=["Extensions"], sort_submenus=True),
                    MenuLayout.Item("New Viewport Window", remove=True),
                    # MenuLayout.Item("Material Preview", remove=True),
                ],
            ),
            MenuLayout.Menu(
                "Layout",
                [
                    MenuLayout.Item("Default", source="Reset Layout"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("UI Toggle Visibility", source="Window/UI Toggle Visibility"),
                    MenuLayout.Item("Fullscreen Mode", source="Window/Fullscreen Mode"),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Save Layout", source="Window/Layout/Save Layout..."),
                    MenuLayout.Item("Load Layout", source="Window/Layout/Load Layout..."),
                    MenuLayout.Seperator(),
                    MenuLayout.Item("Quick Save", source="Window/Layout/Quick Save"),
                    MenuLayout.Item("Quick Load", source="Window/Layout/Quick Load"),
                ],
            ),
        ]
        omni.kit.menu.utils.add_layout(self._menu_layout)

        # set omnu.ui Help Menu
        # self._ui_doc_menu_path = "Help/Omni UI Docs"
        # self._ui_doc_menu_item = editor_menu.add_item(self._ui_doc_menu_path, lambda *_: self._show_ui_docs())
        # editor_menu.set_priority(self._ui_doc_menu_path, -10)

        self._layout_menu_items = []
        self._current_layout_priority = 20

        def add_layout_menu_entry(name, parameter, key):
            import inspect

            menu_path = f"Layout/{name}"
            menu = editor_menu.add_item(menu_path, None, False, self._current_layout_priority)
            self._current_layout_priority = self._current_layout_priority + 1

            if inspect.isfunction(parameter):
                menu_action = omni.kit.menu.utils.add_action_to_menu(
                    menu_path,
                    lambda *_: asyncio.ensure_future(parameter()),
                    name,
                    (carb.input.KEYBOARD_MODIFIER_FLAG_CONTROL, key),
                )
            else:

                async def _active_layout(layout):
                    await _load_layout(layout)
                    # load layout file again to make sure layout correct
                    await _load_layout(layout)

                menu_action = omni.kit.menu.utils.add_action_to_menu(
                    menu_path,
                    lambda *_: asyncio.ensure_future(_active_layout(f"{DATA_PATH}/layouts/{parameter}.json")),
                    name,
                    (carb.input.KEYBOARD_MODIFIER_FLAG_CONTROL, key),
                )

            self._layout_menu_items.append((menu, menu_action))

        add_layout_menu_entry("Reset Layout", "default", carb.input.KeyboardInput.KEY_1)

        # create Quick Load & Quick Save
        from omni.kit.quicklayout import QuickLayout

        async def quick_save():
            QuickLayout.quick_save(None, None)

        async def quick_load():
            QuickLayout.quick_load(None, None)

        add_layout_menu_entry("Quick Save", quick_save, carb.input.KeyboardInput.KEY_7)
        add_layout_menu_entry("Quick Load", quick_load, carb.input.KeyboardInput.KEY_8)

        # open "Asset Stores" window
        ui.Workspace.show_window("Asset Stores")

    def on_shutdown(self):
        self._sub_fabric_delegate_changed = None

        omni.kit.menu.utils.remove_layout(self._menu_layout)
        self._menu_layout = None
        self._layout_menu_items = None
        # self._ui_doc_menu_item = None
        self._launcher_menu = None
        self._reset_menu = None
