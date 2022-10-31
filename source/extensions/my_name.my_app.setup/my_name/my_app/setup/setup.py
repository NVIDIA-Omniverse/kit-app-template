import asyncio
from pathlib import Path

import carb.imgui as _imgui
import carb.settings
import carb.tokens
import omni.ext
import omni.kit.menu.utils
from omni.kit.menu.utils import MenuLayout
from omni.kit.quicklayout import QuickLayout
from omni.kit.window.title import get_main_window_title


async def _load_layout(layout_file: str):
    """this private methods just help loading layout, you can use it in the Layout Menu"""
    await omni.kit.app.get_app().next_update_async()
    QuickLayout.load_file(layout_file)


# This extension is mostly loading the Layout updating menu
class SetupExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def on_startup(self, ext_id):

        # get the settings
        self._settings = carb.settings.get_settings()

        self._await_layout = asyncio.ensure_future(self._delayed_layout())
        # setup the menu and their layout
        self._setup_menu()

        # setup the Application Title
        window_title = get_main_window_title()
        window_title.set_app_version(self._settings.get("/app/titleVersion"))

    async def _delayed_layout(self):

        # few frame delay to allow automatic Layout of window that want their own positions
        for i in range(4):
            await omni.kit.app.get_app().next_update_async()

        settings = carb.settings.get_settings()
        # setup the Layout for your app
        layouts_path = carb.tokens.get_tokens_interface().resolve("${my_name.my_app.setup}/layouts")
        layout_file = Path(layouts_path).joinpath(f"{settings.get('/app/layout/name')}.json")
        asyncio.ensure_future(_load_layout(f"{layout_file}"))

        # using imgui directly to adjust some color and Variable
        imgui = _imgui.acquire_imgui()

        # DockSplitterSize is the variable that drive the size of the Dock Split connection
        imgui.push_style_var_float(_imgui.StyleVar.DockSplitterSize, 2)

    def _setup_menu(self):
        editor_menu = omni.kit.ui.get_editor_menu()
        # you can have some file Menu
        self._file_open = editor_menu.add_item("File/Open", self._open_file)

        # some Menu Item
        self._help_menu = editor_menu.add_item("Help/Show", self._show_help)

        # from omni.kit.menu.utils import MenuLayout
        # self._menu_layout = [
        #         MenuLayout.Menu("Window", [
        #             MenuLayout.Item("MyWindow"),
        #         ]),
        # ]
        # omni.kit.menu.utils.add_layout(self._menu_layout)

    def _show_help(self, menu, toggled):
        print("Help is Coming")

    def _open_file(self, menu, toggled):
        print("Open the File you want")

    def on_shutdown(self):
        pass
