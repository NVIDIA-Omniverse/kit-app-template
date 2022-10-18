import omni.ext
import omni.kit.ui
# import omni.ui as ui
from .window import MyWindow


class WindowExtension(omni.ext.IExt):

    MENU_PATH = "Window/MyWindow"

    def on_startup(self, ext_id):

        editor_menu = omni.kit.ui.get_editor_menu()

        # Most application have an Window Menu, See MenuLayout to re-organize it
        self._window = None
        self._menu = editor_menu.add_item(WindowExtension.MENU_PATH, self._on_menu_click, toggle=True, value=True)
        self.show_window(self._menu, True)

    def _on_menu_click(self, menu, toggled):
        self.show_window(menu, toggled)

    def show_window(self, menu, toggled):
        if toggled:
            if self._window is None:
                self._window = MyWindow()
                self._window.set_visibility_changed_fn(self._visiblity_changed_fn)
            else:
                self._window.show()
        else:
            self._window = None

    def _visiblity_changed_fn(self, visible):
        if self._menu:
            omni.kit.ui.get_editor_menu().set_value(WindowExtension.MENU_PATH, visible)
            self.show_window(None, visible)

    def on_shutdown(self):
        self._window = None
