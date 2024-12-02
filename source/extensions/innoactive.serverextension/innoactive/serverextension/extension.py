import os
import omni.ext
import omni.ui as ui
import omni.usd
import json
import carb
import carb.tokens
import asyncio  # Import asyncio for the delay
from pxr import Usd, UsdGeom, Gf
from omni.kit.viewport.utility import get_active_viewport


# Functions and vars are available to other extensions as usual in python: `innoactive.serverextension.some_public_function(x)`
def set_usd(usd):
    print(f"[innoactive.serverextension] set_usd '{usd}'")
    MyExtension.set_usd(MyExtension, usd)

# Any class derived from `omni.ext.IExt` in the top level module (defined in `python.modules` of `extension.toml`) will
# be instantiated when the extension gets enabled, and `on_startup(ext_id)` will be called.
# Later when the extension gets disabled on_shutdown() is called.
class MyExtension(omni.ext.IExt):
    # ext_id is the current extension id. It can be used with the extension manager to query additional information,
    # like where this extension is located on the filesystem.
    empty_stage = "usd/Empty/Stage.usd"
    usd_to_load = "" # usd/JetEngine/jetengine.usd
    layout_json = "./InnoactiveLayout.json"
    stage = None  # Reference to the USD stage
    
    def set_usd(self, usd_file):
        print(f"[innoactive.serverextension] internal set_usd '{usd_file}'")
        self.usd_to_load = usd_file

    def _ensure_camera_temp(self, camera_name="XRCam", position=(0, 0, 0)):
        """
        Ensures a temporary camera with the specified name exists in the stage.
        If not, it creates one at the given position.
        Sets the camera as the active camera for the viewport.
        """
        if not self.stage:
            print("[innoactive.serverextension] Stage is not loaded.")
            return

        camera_path = f"/{camera_name}"

        # Check if the camera already exists
        camera_prim = self.stage.GetPrimAtPath(camera_path)
        if camera_prim and camera_prim.IsValid():
            print(f"[innoactive.serverextension] Camera '{camera_name}' already exists.")
        else:
            print(f"[innoactive.serverextension] Camera '{camera_name}' not found. Adding it to the stage (temporary).")
            try:
                # Add the camera in the session layer
                with Usd.EditContext(self.stage, self.stage.GetSessionLayer()):
                    camera_prim = self.stage.DefinePrim(camera_path, "Camera")
                    camera = UsdGeom.Camera(camera_prim)

                    # Set camera's translation
                    camera_prim.GetAttribute("xformOp:translate").Set(Gf.Vec3d(*position))

                print(f"[innoactive.serverextension] Temporary Camera '{camera_name}' added successfully at {position}.")
            except Exception as e:
                print(f"[innoactive.serverextension] Failed to add temporary Camera '{camera_name}': {str(e)}")

        # Set the camera as active in the viewport
        self._set_active_camera_in_viewport(camera_path)

    def _set_active_camera_in_viewport(self, camera_path):
        """
        Sets the specified camera as the active camera in the active viewport.
        """
        try:
            viewport = get_active_viewport()
            if not viewport:
                raise RuntimeError("No active Viewport")
            viewport.camera_path = camera_path
            print(f"[innoactive.serverextension] Camera '{camera_path}' set as active in the viewport.")
        except Exception as e:
            print(f"[innoactive.serverextension] Failed to set active camera in the viewport '{camera_path}': {str(e)}")

    def _on_stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.OPENED):
            print("[innoactive.serverextension] Stage has fully loaded!")
            stage_path = self.usd_context.get_stage_url()
            print(f"[innoactive.serverextension] Stage {stage_path}")

            # Get the stage and store it at the class level
            self.stage = self.usd_context.get_stage()
            if not self.stage:
                print("[innoactive.serverextension] Unable to retrieve stage.")
                return

            if stage_path == self.empty_stage:
                print("[innoactive.serverextension] empty_stage loaded")
                asyncio.ensure_future(self._delayed_load_usd(10))
            else:
                print("[innoactive.serverextension] USD loaded")
                self.load_layout(workspace_file=self.layout_json)


    def load_usd(self, usd_file: str, log_errors=True):
        """
        Class method to load a USD file.
        Args:
            usd_file (str): Path to the USD file to load.
            log_errors (bool): Whether to log errors if loading fails.
        """
        if not isinstance(usd_file, str):
            if log_errors:
                carb.log_error(f"[innoactive.serverextension] Invalid USD path: {usd_file}. Must be a string.")
            return

        if not os.path.exists(usd_file):
            if log_errors:
                carb.log_error(f"[innoactive.serverextension] USD file does not exist: {usd_file}")
            return

        try:
            carb.log_info(f"[innoactive.serverextension] Loading USD file: {usd_file}")
            omni.usd.get_context().open_stage(usd_file)

            # Ensure the XRCam camera exists
            self._ensure_camera_temp("XRCam", position=(0, 0, 0))

        except Exception as e:
            if log_errors:
                carb.log_error(f"[innoactive.serverextension] Failed to open USD file {usd_file}: {str(e)}")

    async def _delayed_load_usd(self, delay = 10):

        await asyncio.sleep(delay) 
        self.load_usd(usd_file=self.usd_to_load)

    def load_layout(self, workspace_file="./InnoactiveLayout.json", log_errors=True):

        if not os.path.exists(workspace_file):
            if log_errors:
                carb.log_error(f"[innoactive.serverextension] Layout file does not exist: {workspace_file}")
            return

        try:
            result, _, content = omni.client.read_file(workspace_file)
            if result != omni.client.Result.OK:
                if log_errors:
                    carb.log_error(f"[innoactive.serverextension] Can't read the workspace file {workspace_file}, error code: {result}")
                return

            try:
                data = json.loads(memoryview(content).tobytes().decode("utf-8"))
            except Exception as e:
                if log_errors:
                    carb.log_error(f"[innoactive.serverextension] Failed to parse JSON from {workspace_file}: {str(e)}")
                return

            ui.Workspace.restore_workspace(data, False)
            carb.log_info(f"[innoactive.serverextension] The workspace is loaded from {workspace_file}")
        except Exception as e:
            if log_errors:
                carb.log_error(f"[innoactive.serverextension] Unexpected error while loading layout: {str(e)}")


    
    
    def on_startup(self, ext_id):
        print("[innoactive.serverextension] Extension startup")

        # Get the USD context
        self.usd_context = omni.usd.get_context()

        # Subscribe to stage events
        self._subscription = self.usd_context.get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event,
            name="Stage Event Subscription"
        )

        self._window = ui.Window("Innoctive Server Extension", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")

                def set_cam():
                    self._set_active_camera_in_viewport("/XRCam")

                def on_load_usd():
                    self.load_usd(usd_file=self.usd_to_load)

                def on_reset_stage():
                    self.load_usd(usd_file=self.empty_stage)
                    print("on_reset_stage()")

                def on_load_layout():
                    self.load_layout(workspace_file=self.layout_json)
                    print("on_load_layout()")

                with ui.VStack():
                    # ui.Button("SetCam", clicked_fn=set_cam)
                    ui.Button("Load Layout", clicked_fn=on_load_layout)
                    # ui.Button("Load USD", clicked_fn=on_load_usd)
                    # ui.Button("Reset", clicked_fn=on_reset_stage)

    
    

    def on_shutdown(self):
        print("[innoactive.serverextension] Extension shutdown")

