# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import math
import uuid
from typing import Dict, Any, Optional, Tuple

import carb
import carb.events
from carb.eventdispatcher import get_eventdispatcher
import omni.kit.app
import omni.kit.livestream.messaging as messaging
from omni.timeline import get_timeline_interface

from .viewport_capture import ViewportCapture
from .agent_client import AgentClient, AgentAction, ChatRequest, AgentResponse
from .camera_navigation import get_camera_navigation, CameraNavigation


class CustomMessageManager:
    """Manages custom messages between web client and Kit application"""

    # Camera movement detection threshold (in scene units)
    CAMERA_MOVEMENT_THRESHOLD = 1.0

    def __init__(self, agent_backend_url: str = "http://localhost:8000"):
        """Initialize the custom message manager"""
        self._subscriptions = []
        self._timeline = get_timeline_interface()
        self._viewport_capture = ViewportCapture()
        self._agent_client = AgentClient(base_url=agent_backend_url)
        self._pending_requests: Dict[str, Dict[str, Any]] = {}  # Track pending chat requests

        # Camera position tracking (per session)
        self._last_camera_positions: Dict[str, Dict[str, float]] = {}

        # Camera navigation for moving to store locations
        self._camera_navigation: CameraNavigation = get_camera_navigation()

        carb.log_info("[CustomMessageManager] Initializing...")

        # ===== REGISTER OUTGOING MESSAGES (Kit -> Web Client) =====
        outgoing_messages = [
            "customActionResult",       # Response to custom action requests
            "dataUpdateNotification",   # Notify client of data changes
            "parameterChanged",         # Confirm parameter changes
            "timelineStatusResponse",   # Timeline/simulation status response
            # Chat-related messages
            "chatResponse",             # Chat response from agent
            "chatTyping",               # Typing indicator
            "chatError",                # Chat error notification
        ]

        for message_type in outgoing_messages:
            messaging.register_event_type_to_send(message_type)
            omni.kit.app.register_event_alias(
                carb.events.type_from_string(message_type),
                message_type,
            )

        # ===== REGISTER INCOMING MESSAGE HANDLERS (Web Client -> Kit) =====
        incoming_handlers = {
            'customActionRequest': self._on_custom_action_request,
            'setParameter': self._on_set_parameter,
            'getCustomData': self._on_get_custom_data,
            'getTimelineStatus': self._on_get_timeline_status,
            'timelineControl': self._on_timeline_control,
            # Chat-related handlers
            'chatMessage': self._on_chat_message,
            'chatCancel': self._on_chat_cancel,
        }

        ed = get_eventdispatcher()
        for event_type, handler in incoming_handlers.items():
            # Register event alias for backward compatibility
            omni.kit.app.register_event_alias(
                carb.events.type_from_string(event_type),
                event_type,
            )
            # Subscribe to the event
            self._subscriptions.append(
                ed.observe_event(
                    observer_name=f"CustomMessageManager:{event_type}",
                    event_name=event_type,
                    on_event=handler
                )
            )

        carb.log_info("[CustomMessageManager] Initialized successfully")

    def _on_custom_action_request(self, event: carb.events.IEvent):
        """Handle custom action requests from web client"""
        payload = event.payload
        carb.log_info(f"[CustomMessageManager] Received custom action request: {payload}")

        action_type = payload.get('action_type', '')
        parameters = payload.get('parameters', {})

        # Process the action based on type
        if action_type == "rotate_camera":
            angle = parameters.get('angle', 0)
            result = {"rotated": True, "angle": angle}
        elif action_type == "toggle_feature":
            feature_name = parameters.get('feature', '')
            enabled = parameters.get('enabled', False)
            result = {"feature": feature_name, "enabled": enabled}
        else:
            result = {"error": f"Unknown action: {action_type}"}

        # Send response back to web client
        get_eventdispatcher().dispatch_event(
            "customActionResult",
            payload={
                'action_type': action_type,
                'result': result,
                'status': 'success'
            }
        )

    def _on_set_parameter(self, event: carb.events.IEvent):
        """Handle parameter setting requests"""
        payload = event.payload
        param_name = payload.get('name', '')
        param_value = payload.get('value')

        carb.log_info(f"[CustomMessageManager] Setting parameter: {param_name} = {param_value}")

        # Store in settings (example)
        if param_name and param_value is not None:
            settings = carb.settings.get_settings()
            settings.set(f"/ext/custom/{param_name}", param_value)

            # Send confirmation to web client
            get_eventdispatcher().dispatch_event(
                "parameterChanged",
                payload={
                    'name': param_name,
                    'value': param_value,
                    'status': 'success'
                }
            )

    def _on_get_custom_data(self, event: carb.events.IEvent):
        """Handle data requests from web client"""
        payload = event.payload
        data_type = payload.get('type', 'all')

        carb.log_info(f"[CustomMessageManager] Data request for type: {data_type}")

        # Collect the requested data
        if data_type == "viewport_info":
            data = {
                "resolution": "1920x1080",
                "fps": 60,
                "renderer": "RTX",
            }
        elif data_type == "app_status":
            data = {
                "version": "1.0.0",
                "uptime": "00:15:30",
                "memory_usage": "2.5GB",
            }
        else:
            data = {"message": f"No data available for type: {data_type}"}

        # Send data to web client
        get_eventdispatcher().dispatch_event(
            "dataUpdateNotification",
            payload={
                'type': data_type,
                'data': data,
            }
        )

    def _on_get_timeline_status(self, event: carb.events.IEvent):
        """Handle timeline status requests from web client"""
        carb.log_info("[CustomMessageManager] Timeline status requested")

        # Get current timeline state
        is_playing = self._timeline.is_playing()
        is_stopped = self._timeline.is_stopped()
        current_time = self._timeline.get_current_time()
        start_time = self._timeline.get_start_time()
        end_time = self._timeline.get_end_time()

        # Determine the mode
        if is_playing:
            mode = "playing"  # Scripted mode / simulation running
        elif is_stopped:
            mode = "stopped"  # Idle / not in simulation
        else:
            mode = "paused"   # Paused state

        # Send status back to web client
        get_eventdispatcher().dispatch_event(
            "timelineStatusResponse",
            payload={
                'mode': mode,
                'is_playing': is_playing,
                'is_stopped': is_stopped,
                'current_time': current_time,
                'start_time': start_time,
                'end_time': end_time,
                'scripted_mode_active': is_playing,  # True when simulation is running
            }
        )

    def _on_timeline_control(self, event: carb.events.IEvent):
        """Handle timeline control requests from web client (play/pause/stop)"""
        payload = event.payload
        action = payload.get('action', '')

        carb.log_info(f"[CustomMessageManager] Timeline control: {action}")

        result = {"action": action, "success": False, "error": None}

        try:
            if action == "play":
                self._timeline.play()
                result["success"] = True
                result["message"] = "Simulation started (scripted mode active)"
            elif action == "pause":
                self._timeline.pause()
                result["success"] = True
                result["message"] = "Simulation paused"
            elif action == "stop":
                self._timeline.stop()
                result["success"] = True
                result["message"] = "Simulation stopped (idle mode)"
            else:
                result["error"] = f"Unknown action: {action}"
        except Exception as e:
            result["error"] = str(e)
            carb.log_error(f"[CustomMessageManager] Timeline control error: {e}")

        # Send result back to web client
        get_eventdispatcher().dispatch_event(
            "timelineStatusResponse",
            payload={
                'action_result': result,
                'mode': "playing" if self._timeline.is_playing() else ("stopped" if self._timeline.is_stopped() else "paused"),
                'is_playing': self._timeline.is_playing(),
                'scripted_mode_active': self._timeline.is_playing(),
            }
        )

    # ===== CHAT MESSAGE HANDLERS =====

    def _on_chat_message(self, event: carb.events.IEvent):
        """Handle incoming chat messages from web client"""
        payload = event.payload
        message = payload.get('message', '')
        session_id = payload.get('session_id', str(uuid.uuid4()))
        request_id = payload.get('request_id', str(uuid.uuid4()))
        context = payload.get('context', {})

        carb.log_info(f"[CustomMessageManager] Chat message received: {message[:50]}...")

        # Send typing indicator
        self._send_typing_indicator(session_id, True)

        # Store the pending request
        self._pending_requests[request_id] = {
            'message': message,
            'session_id': session_id,
            'context': context,
            'cancelled': False
        }

        # Process chat asynchronously
        asyncio.ensure_future(
            self._process_chat_message(request_id, message, session_id, context)
        )

    def _on_chat_cancel(self, event: carb.events.IEvent):
        """Handle chat cancellation requests"""
        payload = event.payload
        request_id = payload.get('request_id', '')

        if request_id in self._pending_requests:
            self._pending_requests[request_id]['cancelled'] = True
            carb.log_info(f"[CustomMessageManager] Chat request cancelled: {request_id}")

    async def _process_chat_message(
        self,
        request_id: str,
        message: str,
        session_id: str,
        context: Dict[str, Any]
    ):
        """Process a chat message through the agent backend"""
        try:
            # Check if cancelled
            if self._is_request_cancelled(request_id):
                return

            # Get current camera position and detect movement
            current_camera_pos = self._get_camera_position()
            camera_moved, move_distance = self._detect_camera_movement(
                session_id, current_camera_pos
            )

            # Build enriched context with camera information
            enriched_context = {
                **context,
                "camera": {
                    "position": current_camera_pos,
                    "has_moved": camera_moved,
                    "move_distance": move_distance,
                }
            }

            # Update stored camera position for next comparison
            self._update_camera_position(session_id, current_camera_pos)

            carb.log_info(
                f"[CustomMessageManager] Camera context - "
                f"position: {current_camera_pos}, moved: {camera_moved}"
            )

            # Send initial message to agent with enriched context
            chat_request = ChatRequest(
                message=message,
                session_id=session_id,
                context=enriched_context
            )

            response = await self._agent_client.send_chat_message(chat_request)

            # Check if cancelled
            if self._is_request_cancelled(request_id):
                return

            # Handle agent actions
            if response.action == AgentAction.CAPTURE_FRAME:
                # Agent requested frame capture for visual analysis
                await self._handle_capture_frame_action(
                    request_id=request_id,
                    original_message=message,
                    session_id=session_id,
                    action_params=response.action_params or {},
                    context=enriched_context
                )
            elif response.action == AgentAction.GET_SCENE_INFO:
                # Agent requested scene information
                await self._handle_get_scene_info_action(
                    request_id=request_id,
                    original_message=message,
                    session_id=session_id,
                    response=response,
                    context=enriched_context
                )
            elif response.action == AgentAction.NAVIGATE_TO:
                # Agent requested camera navigation to a location
                await self._handle_navigate_to_action(
                    request_id=request_id,
                    session_id=session_id,
                    response=response,
                    action_params=response.action_params or {}
                )
            else:
                # No special action, send response to client
                self._send_chat_response(
                    session_id=session_id,
                    request_id=request_id,
                    message=response.message,
                    metadata=response.metadata
                )

        except Exception as e:
            carb.log_error(f"[CustomMessageManager] Chat processing error: {e}")
            self._send_chat_error(session_id, request_id, str(e))

        finally:
            # Clean up pending request
            self._pending_requests.pop(request_id, None)
            self._send_typing_indicator(session_id, False)

    async def _handle_capture_frame_action(
        self,
        request_id: str,
        original_message: str,
        session_id: str,
        action_params: Dict[str, Any],
        context: Dict[str, Any]
    ):
        """Handle the capture_frame action from agent"""
        carb.log_info("[CustomMessageManager] Capturing viewport frame for analysis...")

        # Get capture parameters
        width = action_params.get('width', 1280)
        height = action_params.get('height', 720)

        # Capture the viewport
        frame_data = await self._viewport_capture.capture_frame_async(
            width=width,
            height=height
        )

        if self._is_request_cancelled(request_id):
            return

        if frame_data is None:
            self._send_chat_response(
                session_id=session_id,
                request_id=request_id,
                message="I couldn't capture the current view. Please try again.",
                metadata={"error": "frame_capture_failed"}
            )
            return

        # Send frame to vision agent for analysis
        carb.log_info("[CustomMessageManager] Sending frame to vision agent...")

        analysis_response = await self._agent_client.send_frame_for_analysis(
            frame_data=frame_data,
            original_query=original_message,
            session_id=session_id,
            context=context
        )

        if self._is_request_cancelled(request_id):
            return

        # Check if image_url is available (from LuminiOne cloud upload)
        # If so, don't send the large base64 captured_frame to reduce payload size
        response_metadata = analysis_response.metadata or {}
        image_url = response_metadata.get('image_url')

        # Only include captured_frame if no image_url is available (local setup)
        # This avoids sending huge base64 payloads when we have a URL
        frame_to_send = None
        if not image_url:
            frame_to_send = analysis_response.captured_frame or frame_data
            carb.log_info("[CustomMessageManager] No image_url, sending base64 captured_frame")
        else:
            carb.log_info(f"[CustomMessageManager] Using image_url instead of base64: {image_url}")

        # Send final response to client
        self._send_chat_response(
            session_id=session_id,
            request_id=request_id,
            message=analysis_response.message,
            metadata={
                **response_metadata,
                "frame_analyzed": True
            },
            reasoning=analysis_response.reasoning,
            captured_frame=frame_to_send
        )

    async def _handle_get_scene_info_action(
        self,
        request_id: str,
        original_message: str,
        session_id: str,
        response: AgentResponse,
        context: Dict[str, Any]
    ):
        """Handle the get_scene_info action from agent"""
        # Gather scene information
        scene_info = self._get_scene_info()

        # Send scene info back to agent for continued processing
        updated_context = {
            **context,
            "scene_info": scene_info
        }

        chat_request = ChatRequest(
            message=original_message,
            session_id=session_id,
            context=updated_context
        )

        followup_response = await self._agent_client.send_chat_message(chat_request)

        if self._is_request_cancelled(request_id):
            return

        self._send_chat_response(
            session_id=session_id,
            request_id=request_id,
            message=followup_response.message,
            metadata=followup_response.metadata
        )

    def _get_scene_info(self) -> Dict[str, Any]:
        """Get current scene information"""
        try:
            import omni.usd
            stage = omni.usd.get_context().get_stage()

            if stage is None:
                return {"error": "No stage loaded"}

            # Gather basic scene info
            root_layer = stage.GetRootLayer()
            prims = list(stage.TraverseAll())

            return {
                "root_layer": root_layer.identifier if root_layer else None,
                "prim_count": len(prims),
                "up_axis": str(stage.GetMetadata("upAxis")),
                "meters_per_unit": stage.GetMetadata("metersPerUnit"),
            }

        except Exception as e:
            carb.log_error(f"[CustomMessageManager] Failed to get scene info: {e}")
            return {"error": str(e)}

    # ===== CAMERA NAVIGATION =====

    async def _handle_navigate_to_action(
        self,
        request_id: str,
        session_id: str,
        response: AgentResponse,
        action_params: Dict[str, Any]
    ):
        """Handle the navigate_to action from agent - move camera to a location"""
        destination = action_params.get('destination', '')
        speed = action_params.get('speed', 1.0)
        instant = action_params.get('instant', False)

        carb.log_info(f"[CustomMessageManager] Navigate to: {destination} (speed={speed}, instant={instant})")

        if not destination:
            self._send_chat_response(
                session_id=session_id,
                request_id=request_id,
                message=response.message or "I need a destination to navigate to.",
                metadata={"error": "no_destination"}
            )
            return

        # Send the agent's message first (e.g., "Taking you to the Pringles section...")
        if response.message:
            self._send_chat_response(
                session_id=session_id,
                request_id=request_id,
                message=response.message,
                metadata={
                    **(response.metadata or {}),
                    "navigating_to": destination,
                    "navigation_started": True
                }
            )

        # Perform the navigation
        success = await self._camera_navigation.navigate_to(
            destination=destination,
            speed=speed,
            instant=instant
        )

        if success:
            carb.log_info(f"[CustomMessageManager] Navigation complete: {destination}")
            # Optionally send arrival notification
            # self._send_navigation_arrived(session_id, destination)
        else:
            carb.log_warn(f"[CustomMessageManager] Navigation failed: {destination}")
            # Send error message if navigation failed
            available = list(self._camera_navigation.get_positions().keys())
            self._send_chat_response(
                session_id=session_id,
                request_id=request_id,
                message=f"Sorry, I couldn't navigate to '{destination}'. Available locations: {', '.join(available[:10])}",
                metadata={"error": "navigation_failed", "destination": destination}
            )

    def get_available_locations(self) -> Dict[str, Dict[str, Any]]:
        """Get all available navigation locations"""
        return self._camera_navigation.get_positions()

    # ===== CAMERA TRACKING =====

    def _get_camera_position(self) -> Optional[Dict[str, float]]:
        """Get current camera position from viewport capture utility."""
        camera_info = self._viewport_capture.get_camera_info()
        if camera_info and camera_info.get("valid") and camera_info.get("position"):
            return camera_info["position"]
        return None

    def _calculate_camera_distance(
        self,
        pos1: Dict[str, float],
        pos2: Dict[str, float]
    ) -> float:
        """Calculate Euclidean distance between two camera positions."""
        dx = pos1.get("x", 0) - pos2.get("x", 0)
        dy = pos1.get("y", 0) - pos2.get("y", 0)
        dz = pos1.get("z", 0) - pos2.get("z", 0)
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def _detect_camera_movement(
        self,
        session_id: str,
        current_position: Optional[Dict[str, float]]
    ) -> Tuple[bool, Optional[float]]:
        """
        Detect if camera has moved since last message.

        Returns:
            Tuple of (has_moved: bool, distance: Optional[float])
        """
        if current_position is None:
            return False, None

        last_position = self._last_camera_positions.get(session_id)
        if last_position is None:
            # First message in session, no movement to detect
            return False, None

        distance = self._calculate_camera_distance(current_position, last_position)
        has_moved = distance > self.CAMERA_MOVEMENT_THRESHOLD

        if has_moved:
            carb.log_info(
                f"[CustomMessageManager] Camera moved {distance:.2f} units "
                f"(threshold: {self.CAMERA_MOVEMENT_THRESHOLD})"
            )

        return has_moved, distance

    def _update_camera_position(
        self,
        session_id: str,
        position: Optional[Dict[str, float]]
    ):
        """Store the current camera position for a session."""
        if position:
            self._last_camera_positions[session_id] = position

    def _is_request_cancelled(self, request_id: str) -> bool:
        """Check if a request has been cancelled"""
        request = self._pending_requests.get(request_id)
        return request is None or request.get('cancelled', False)

    def _send_typing_indicator(self, session_id: str, is_typing: bool):
        """Send typing indicator to web client"""
        get_eventdispatcher().dispatch_event(
            "chatTyping",
            payload={
                'session_id': session_id,
                'is_typing': is_typing
            }
        )

    def _send_chat_response(
        self,
        session_id: str,
        request_id: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None,
        captured_frame: Optional[str] = None,
        image_url: Optional[str] = None
    ):
        """Send chat response to web client"""
        payload = {
            'session_id': session_id,
            'request_id': request_id,
            'message': message,
            'metadata': metadata or {},
            'status': 'success'
        }

        # Add optional fields if present
        if reasoning:
            payload['reasoning'] = reasoning
        if captured_frame:
            payload['captured_frame'] = captured_frame
            carb.log_info(f"[CustomMessageManager] Including captured frame ({len(captured_frame)} chars)")

        # Add image_url as top-level field for frontend visualization
        # Also extract from metadata if not explicitly provided
        final_image_url = image_url or (metadata.get('image_url') if metadata else None)
        if final_image_url:
            payload['image_url'] = final_image_url
            carb.log_info(f"[CustomMessageManager] Including image URL: {final_image_url}")

        get_eventdispatcher().dispatch_event("chatResponse", payload=payload)
        carb.log_info(f"[CustomMessageManager] Chat response sent: {message[:50]}...")

    def _send_chat_error(self, session_id: str, request_id: str, error: str):
        """Send chat error to web client"""
        get_eventdispatcher().dispatch_event(
            "chatError",
            payload={
                'session_id': session_id,
                'request_id': request_id,
                'error': error,
                'status': 'error'
            }
        )
        carb.log_error(f"[CustomMessageManager] Chat error: {error}")

    def on_shutdown(self):
        """Clean up when the manager is shut down"""
        carb.log_info("[CustomMessageManager] Shutting down...")

        # Cancel pending requests
        for request_id in list(self._pending_requests.keys()):
            self._pending_requests[request_id]['cancelled'] = True
        self._pending_requests.clear()

        # Clear camera position tracking
        self._last_camera_positions.clear()

        # Clean up subscriptions
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()