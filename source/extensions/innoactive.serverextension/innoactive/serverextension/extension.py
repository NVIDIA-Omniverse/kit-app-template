# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import os
import omni.ext
import omni.ui as ui
import omni.usd
import json
import carb
import carb.tokens



# Functions and vars are available to other extensions as usual in python: `innoactive.serverextension.some_public_function(x)`
def some_public_function(x: int):
    print(f"[innoactive.serverextension] some_public_function was called with {x}")
    return x ** x


# Any class derived from `omni.ext.IExt` in the top level module (defined in `python.modules` of `extension.toml`) will
# be instantiated when the extension gets enabled, and `on_startup(ext_id)` will be called.
# Later when the extension gets disabled on_shutdown() is called.
class MyExtension(omni.ext.IExt):
    # ext_id is the current extension id. It can be used with the extension manager to query additional information,
    # like where this extension is located on the filesystem.
    empty_stage = "usd/Empty/Stage.usd"
    layout_json = "./InnoactiveLayout.json"

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
        except Exception as e:
            if log_errors:
                carb.log_error(f"[innoactive.serverextension] Failed to open USD file {usd_file}: {str(e)}")

    def load_layout(self, workspace_file="./InnoactiveLayout.json", log_errors=True):
        """
        Class method to load a layout from a JSON file.
        Args:
            workspace_file (str): Path to the JSON workspace file.
            log_errors (bool): Whether to log errors if loading fails.
            *args: Additional arguments passed by the event system, ignored here.
        """
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

                def on_load_usd():
                    self.load_usd(usd_file="usd/JetEngine/jetengine.usd")

                def on_reset_stage():
                    self.load_usd(usd_file=self.empty_stage)
                    print("on_reset_stage()")

                def on_load_layout():
                    self.load_layout(workspace_file=self.layout_json)
                    print("on_load_layout()")

                with ui.VStack():
                    ui.Button("Load Layout", clicked_fn=on_load_layout)
                    ui.Button("Load USD", clicked_fn=on_load_usd)
                    ui.Button("Reset", clicked_fn=on_reset_stage)

    
    def _on_stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.OPENED):
            print("[innoactive.serverextension] Stage has fully loaded!")
            stage_path = self.usd_context.get_stage_url()
            print(f"[innoactive.serverextension] Stage {stage_path}")
            if stage_path == self.empty_stage:
                print("[innoactive.serverextension] empty_stage loaded")
                self.load_usd(usd_file="usd/JetEngine/jetengine.usd")
            else:
                print("[innoactive.serverextension] USD loaded")
                self.load_layout(workspace_file=self.layout_json) 




    def on_shutdown(self):
        print("[innoactive.serverextension] Extension shutdown")

