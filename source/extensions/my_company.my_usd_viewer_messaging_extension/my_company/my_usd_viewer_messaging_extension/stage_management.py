# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from pxr import UsdGeom, Usd
import asyncio

import carb
import carb.dictionary
import carb.events
import carb.settings
import carb.tokens
import omni.client.utils
import omni.ext
import omni.usd
import omni.kit.app
import omni.kit.livestream.messaging as messaging
from omni.kit.viewport.utility import get_active_viewport_camera_string, get_active_viewport_window


class StageManager:
    """This class manages the stage and its related events."""
    def __init__(self):
        # Internal messaging state
        self._is_external_update: bool = False
        self._camera_attrs = {}
        self._subscriptions = []

        # -- register outgoing events/messages
        outgoing = [
            # notify when user selects something in the viewport.
            "stageSelectionChanged",
            # response to request for children of a prim
            "getChildrenResponse",
            # response to request for primitive being pickable.
            "makePrimsPickableResponse",
            # response to the request to reset camera attributes
            "resetStageResponse",
            # NEW: response to camera switching request
            "switchCameraResponse",
        ]

        for o in outgoing:
            messaging.register_event_type_to_send(o)

        # -- register incoming events/messages
        incoming = {
            # request to get children of a prim
            'getChildrenRequest': self._on_get_children,
            # request to select a prim
            'selectPrimsRequest': self._on_select_prims,
            # request to make primitives pickable
            'makePrimsPickable': self._on_make_pickable,
            # request to make primitives pickable
            'resetStage': self._on_reset_camera,
            # NEW: request to switch camera
            'switchCameraRequest': self._on_switch_camera,
        }

        for event_type, handler in incoming.items():
            self._subscriptions.append(
                omni.kit.app.get_app().get_message_bus_event_stream().
                create_subscription_to_pop_by_type(
                    carb.events.type_from_string(event_type), handler
                )
            )

        # -- subscribe to stage events
        event_stream = omni.usd.get_context().get_stage_event_stream()
        self._subscriptions.append(
            event_stream.create_subscription_to_pop(self._on_stage_event)
        )

    def get_children(self, prim_path, filters=None):
        """
        Collect any children of the given `prim_path`, potentially filtered by `filters`
        """
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        if not prim:
            return []

        filter_types = {
            "USDGeom": UsdGeom.Mesh,
            "mesh": UsdGeom.Mesh,
            "xform": UsdGeom.Xform,
            "scope": UsdGeom.Scope,
        }

        children = []
        for child in prim.GetChildren():
            # If a child doesn't pass any filter, we skip it.
            if filters is not None:
                if not any(child.IsA(filter_types[filt]) for filt in filters if filt in filter_types):
                    continue

            child_name = child.GetName()
            child_path = str(prim.GetPath())
            # Skipping over cameras
            if child_name.startswith('OmniverseKit_'):
                continue
            # Also skipping rendering primitives.
            if prim_path == '/' and child_name == 'Render':
                continue
            child_path = child_path if child_path != '/' else ''
            carb.log_info(f'child_path: {child_path}')
            info = {"name": child_name, "path": f'{child_path}/{child_name}'}

            # We return an empty list here to indicate that children are
            # available, but the current app does not support pagination,
            # so we use this to lazy load the stage tree.
            if child.GetChildren():
                info["children"] = []

            children.append(info)

        return children

    def _on_get_children(self, event: carb.events.IEvent) -> None:
        """
        Handler for the `getChildrenRequest` event
        Collects a filtered collection of a given primitives children.
        """
        if event.type == carb.events.type_from_string("getChildrenRequest"):
            carb.log_info(
                "Received message to return list of a prim\'s children"
            )
            message_bus = omni.kit.app.get_app().get_message_bus_event_stream()
            event_type = carb.events.type_from_string("getChildrenResponse")
            children = self.get_children(
                prim_path=event.payload["prim_path"],
                filters=event.payload["filters"]
            )
            payload = {
                "prim_path": event.payload["prim_path"],
                "children": children
            }
            message_bus.dispatch(event_type, payload=payload)
            message_bus.pump()

    def _on_select_prims(self, event: carb.events.IEvent) -> None:
        """
        Handler for `selectPrimsRequest` event.

        Selects the given primitives.
        """
        if event.type == carb.events.type_from_string("selectPrimsRequest"):
            new_selection = []
            if "paths" in event.payload:
                new_selection = list(event.payload["paths"])
                carb.log_info(f"Received message to select '{new_selection}'")
            # Flagging this as an external event because it
            # was initiated by the client.
            self._is_external_update = True
            sel = omni.usd.get_context().get_selection()
            sel.clear_selected_prim_paths()
            sel.set_selected_prim_paths(new_selection, True)

    def _on_switch_camera(self, event: carb.events.IEvent) -> None:
        """
        UPDATED: Handler for `switchCameraRequest` event.
        Switches the viewport camera to the specified camera path or free camera mode.
        """
        if event.type == carb.events.type_from_string("switchCameraRequest"):
            # Fix: Use bracket notation instead of .get() for carb.dictionary.Item
            camera_path = event.payload["camera_path"] if "camera_path" in event.payload else None
            carb.log_info(f"Received message to switch to camera: {camera_path}")
            
            # Run the camera switching asynchronously
            asyncio.ensure_future(self._handle_camera_switch(camera_path))

    async def _handle_camera_switch(self, camera_path):
        """
        UPDATED: Handle the actual camera switching asynchronously with free camera support
        """
        try:
            if not camera_path:
                self._send_camera_response("error", "No camera path provided")
                return

            # NEW: Handle free camera mode
            if camera_path == "FREE_CAMERA":
                success = await self._switch_to_free_camera()
                if success:
                    self._send_camera_response("success", "", "FREE_CAMERA")
                    carb.log_info("Successfully switched to free camera mode")
                else:
                    self._send_camera_response("error", "Failed to switch to free camera")
                return

            # Get the current stage
            usd_context = omni.usd.get_context()
            stage = usd_context.get_stage()
            if not stage:
                self._send_camera_response("error", "No active stage")
                return

            # Get the camera prim
            camera_prim = stage.GetPrimAtPath(camera_path)
            if not camera_prim or not camera_prim.IsValid():
                self._send_camera_response("error", f"Camera not found at path: {camera_path}")
                return

            # Verify it's actually a camera
            if not camera_prim.IsA(UsdGeom.Camera):
                self._send_camera_response("error", f"Prim at {camera_path} is not a camera")
                return

            # Switch the viewport camera
            success = await self._switch_viewport_camera(camera_path)

            if success:
                self._send_camera_response("success", "", camera_path)
                carb.log_info(f"Successfully switched to camera: {camera_path}")
            else:
                self._send_camera_response("error", "Failed to switch viewport camera")

        except Exception as e:
            carb.log_error(f"Error in camera switching: {e}")
            self._send_camera_response("error", str(e))

    async def _switch_to_free_camera(self):
        """
        CLEANED UP: Simplified free camera approach based on what actually works
        """
        try:
            carb.log_info("Starting free camera reset...")
            
            viewport_window = get_active_viewport_window()
            if not viewport_window:
                carb.log_error("No active viewport window found")
                return False

            viewport_api = viewport_window.viewport_api
            if not viewport_api:
                carb.log_error("No viewport API found")
                return False

            app = omni.kit.app.get_app()
            
            # Method 1: Clear camera path first
            viewport_api.camera_path = ""
            carb.log_info("Cleared camera path")
            
            for _ in range(3):
                await app.next_update_async()
            
            # Method 2: Set to perspective camera (this is what actually works for free navigation)
            viewport_api.camera_path = "/OmniverseKit_Persp"
            carb.log_info("Set to perspective camera for free navigation")
            
            for _ in range(5):
                await app.next_update_async()
            
            # Note: /OmniverseKit_Persp actually enables free navigation in Kit
            # This is the expected behavior - the perspective camera allows user control
            
            carb.log_info("Free camera mode activated - navigation enabled")
            return True
            
        except Exception as e:
            carb.log_error(f"Error in free camera reset: {e}")
            return False

    async def _switch_viewport_camera(self, camera_path):
        """
        Switch the active viewport to use the specified camera
        """
        try:
            # Get the active viewport window
            viewport_window = get_active_viewport_window()
            if not viewport_window:
                carb.log_error("No active viewport window found")
                return False

            # Get the viewport API
            viewport_api = viewport_window.viewport_api
            if not viewport_api:
                carb.log_error("No viewport API found")
                return False

            # Set the camera path
            viewport_api.camera_path = camera_path

            # Wait a few frames to ensure the camera switch takes effect
            app = omni.kit.app.get_app()
            for _ in range(5):
                await app.next_update_async()

            carb.log_info(f"Viewport camera set to: {viewport_api.camera_path}")
            return True

        except Exception as e:
            carb.log_error(f"Error switching viewport camera: {e}")
            return False

    def _send_camera_response(self, result, error_msg="", camera_path=""):
        """
        Send camera switching response to web client
        """
        message_bus = omni.kit.app.get_app().get_message_bus_event_stream()
        event_type = carb.events.type_from_string("switchCameraResponse")
        
        payload = {
            "result": result,
            "camera_path": camera_path
        }
        
        if error_msg:
            payload["error"] = error_msg

        message_bus.dispatch(event_type, payload=payload)
        message_bus.pump()
        carb.log_info(f"Sent camera response: {result}")

    def _on_stage_event(self, event):
        """
        Hanles all stage related events.

        `omni.usd.StageEventType.SELECTION_CHANGED`:
            Informs the StreamerApp that the selection has changed.
        `omni.usd.StageEventType.ASSETS_LOADED`:
            Informs the StreamerApp that a stage has finished loading
            its assets.
        `omni.usd.StageEventType.OPENED`:
            On stage opened, we collect some of the camera properties
            to allow for them to be reset.
        """
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            # If the selection changed came from an external event,
            # we don't need to let the streaming client know because it
            # initiated the change and is already aware.
            if self._is_external_update:
                self._is_external_update = False
            else:
                message_bus = omni.kit.app.get_app()\
                    .get_message_bus_event_stream()
                event_type = carb.events.type_from_string(
                    "stageSelectionChanged"
                )
                payload = {"prims": omni.usd.get_context().get_selection().
                           get_selected_prim_paths()}
                message_bus.dispatch(event_type, payload=payload)
                message_bus.pump()
                carb.log_info(f"Selection changed: Path to USD prims currently selected = {omni.usd.get_context().get_selection().get_selected_prim_paths()}")

        elif event.type == int(omni.usd.StageEventType.OPENED):
            stage = omni.usd.get_context().get_stage()
            stage_url = stage.GetRootLayer().identifier if stage else ''

            if stage_url:
                # Set the entire stage to not be pickable.
                ctx = omni.usd.get_context()
                ctx.set_pickable("/", False)
                # Clear before using, so that we're sure the data is only
                # from the new stage.
                self._camera_attrs.clear()
                # Capture the active camera's camera data, used to reset
                # the scene to a known good state.
                if (prim := ctx.get_stage().GetPrimAtPath(get_active_viewport_camera_string())):
                    for attr in prim.GetAttributes():
                        self._camera_attrs[attr.GetName()] = attr.Get()

    def _on_reset_camera(self, event: carb.events.IEvent):
        """
        Handler for `resetStage` event.

        Resets the camera back to values collected when the stage was opened.
        A success message is sent if all attributes are succesfully reset, and error message is set otherwise.
        """
        if event.type == carb.events.type_from_string("resetStage"):
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            try:
                # Reset the camera.
                # The camera lives on the session layer, which has a higher
                # opinion than the root stage. So we need to explicitly target
                # the session layer when resetting the camera's attributes.
                camera_prim = ctx.get_stage().GetPrimAtPath(
                    get_active_viewport_camera_string()
                )
                edit_context = Usd.EditContext(
                    stage, Usd.EditTarget(stage.GetSessionLayer())
                )
                with edit_context:
                    for name, value in self._camera_attrs.items():
                        attr = camera_prim.GetAttribute(name)
                        attr.Set(value)
            except Exception as e:
                payload = {"result": "error", "error": str(e)}
            else:
                payload = {"result": "success", "error": ""}
            message_bus = omni.kit.app.get_app().get_message_bus_event_stream()
            event_type = carb.events.type_from_string("resetStageResponse")
            message_bus.dispatch(event_type, payload=payload)
            message_bus.pump()

    def _on_make_pickable(self, event: carb.events.IEvent):
        """
        Handler for `makePrimsPickable` event.

        Enables viewport selection for the provided primitives.
        Sends 'makePrimsPickableResponse' back to streamer with
        current success status.
        """
        if event.type == carb.events.type_from_string("makePrimsPickable"):
            message_bus = omni.kit.app.get_app().get_message_bus_event_stream()
            event_type = carb.events.type_from_string(
                "makePrimsPickableResponse"
            )
            # Reset the stage to not be pickable.
            ctx = omni.usd.get_context()
            ctx.set_pickable("/", False)
            # Set the provided paths to be pickable.
            try:
                paths = event.payload['paths'] or []
                for path in paths:
                    ctx.set_pickable(path, True)
            except Exception as e:
                payload = {"result": "error", "error": str(e)}
            else:
                payload = {"result": "success", "error": ""}
            message_bus.dispatch(event_type, payload=payload)
            message_bus.pump()

    def on_shutdown(self):
        """This is called every time the extension is deactivated. It is used
        to clean up the extension state."""
        # Reseting the state.
        self._subscriptions.clear()
        self._is_external_update: bool = False
        self._camera_attrs.clear()