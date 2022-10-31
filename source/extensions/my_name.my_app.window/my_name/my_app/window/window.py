__all__ = ["MyWindow"]
import omni.ui as ui


class MyWindow(ui.Window):
    """My Window"""

    title = "My Window"

    def __init__(self, **kwargs):
        super().__init__(MyWindow.title, **kwargs)

        # here you build the content of the window
        with self.frame:
            with ui.VStack():
                ui.Label("My Great Window", height=0, style={"font_size": 48, "alignment": ui.Alignment.CENTER})

                ui.Spacer()

                ui.Label(
                    """Today I will build something special with
                        #Omniverse Kit""",
                    height=0,
                    style={"font_size": 32, "alignment": ui.Alignment.CENTER},
                )

                ui.Spacer()

                with ui.HStack(height=50, style={"font_size": 24}):
                    ui.Button("Add")
                    ui.Button("Reset")

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False
