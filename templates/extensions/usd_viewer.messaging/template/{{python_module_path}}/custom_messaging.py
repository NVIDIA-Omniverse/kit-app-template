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
from .usd_spawner import UsdSpawner


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
        self._usd_spawner = UsdSpawner()
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
            # Planogram
            "planogramCaptureResponse",  # Small thumbnail after frame capture
            "planogramAnalysisResult",   # Structured row analysis from backend
            "analyzeShelfResponse",      # Combined vision + row-detection planogram
            # Camera nav position registry
            "navPositionsResponse",      # Full positions list (after any CRUD operation)
            "cameraPositionResponse",    # Current camera position query result
            "navRoutesResponse",         # Waypoint routes list
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
            # Planogram
            'planogramCaptureRequest': self._on_planogram_capture_request,
            'planogramAnalyzeRequest': self._on_planogram_analyze_request,
            'analyzeShelfRequest':     self._on_analyze_shelf_request,
            # Camera nav position registry
            'getNavPositions':     self._on_get_nav_positions,
            'registerNavPosition': self._on_register_nav_position,
            'deleteNavPosition':   self._on_delete_nav_position,
            'clearNavPositions':   self._on_clear_nav_positions,
            'getCameraPosition':   self._on_get_camera_position,
            'navigateTo':          self._on_navigate_to_direct,
            # Per-store built-in preset management
            'setActiveStore':      self._on_set_active_store,
            'promoteNavPosition':  self._on_promote_nav_position,
            'saveAllAsBuiltin':    self._on_save_all_as_builtin,
            # Waypoint route management
            'saveNavRoute':        self._on_save_nav_route,
            'deleteNavRoute':      self._on_delete_nav_route,
            'getNavRoutes':        self._on_get_nav_routes,
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
        language = payload.get('language') or context.get('language') or 'en'

        carb.log_info(f"[CustomMessageManager] Chat message received: {message[:50]}...")

        # Send typing indicator
        self._send_typing_indicator(session_id, True)

        # Store the pending request
        self._pending_requests[request_id] = {
            'message': message,
            'session_id': session_id,
            'context': context,
            'language': language,
            'cancelled': False
        }

        # Process chat asynchronously
        asyncio.ensure_future(
            self._process_chat_message(request_id, message, session_id, context, language)
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
        context: Dict[str, Any],
        language: str,
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
                context=enriched_context,
                language=language,
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
                    context=enriched_context,
                    language=language,
                )
            elif response.action == AgentAction.GET_SCENE_INFO:
                # Agent requested scene information
                await self._handle_get_scene_info_action(
                    request_id=request_id,
                    original_message=message,
                    session_id=session_id,
                    response=response,
                    context=enriched_context,
                    language=language,
                )
            elif response.action == AgentAction.NAVIGATE_TO:
                # Agent requested camera navigation to a location
                await self._handle_navigate_to_action(
                    request_id=request_id,
                    session_id=session_id,
                    response=response,
                    action_params=response.action_params or {}
                )
            elif response.action == AgentAction.FORECAST_DEMAND:
                # Demand forecast action - send status and response
                self._send_typing_indicator(
                    session_id=session_id,
                    is_typing=False,
                    agent_type='demand_forecast',
                    agent_name='Demand Forecast Agent'
                )
                self._send_chat_response(
                    session_id=session_id,
                    request_id=request_id,
                    message=response.message,
                    metadata=response.metadata
                )
            elif response.action == AgentAction.SEARCH_EC:
                # E-commerce search action - send status and response
                self._send_typing_indicator(
                    session_id=session_id,
                    is_typing=False,
                    agent_type='ec_search',
                    agent_name='E-Commerce Search Agent'
                )
                self._send_chat_response(
                    session_id=session_id,
                    request_id=request_id,
                    message=response.message,
                    metadata=response.metadata
                )
            elif response.action == AgentAction.SPAWN_USD:
                # Agent wants to spawn a USD asset — tell the browser to enter
                # spawn-mode so the user can click a location in the viewport.
                params = response.action_params or {}
                self._send_chat_response(
                    session_id=session_id,
                    request_id=request_id,
                    message=response.message,
                    metadata={
                        **(response.metadata or {}),
                        "action":     "spawn_mode",
                        "usd_path":   params.get("usd_path", ""),
                        "asset_name": params.get("asset_name", "Asset"),
                    }
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
        context: Dict[str, Any],
        language: str,
    ):
        """Handle the capture_frame action from agent"""
        carb.log_info("[CustomMessageManager] Capturing viewport frame for analysis...")

        # Get capture parameters
        width = action_params.get('width', 1280)
        height = action_params.get('height', 720)
        followup_intent = action_params.get('followup_intent')  # e.g., 'demand_forecast', 'ec_search'
        # Use the intent-classifier's resolved_query (self-contained rewrite) so the
        # vision agent receives a fully contextualised question.
        resolved_query = action_params.get('resolved_query', original_message)

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

        # If there's a followup_intent (demand_forecast, ec_search), send back to /api/chat
        # with the frame data so it can be processed by the proper handler
        if followup_intent:
            carb.log_info(f"[CustomMessageManager] Followup intent: {followup_intent}, sending to /api/chat with frame...")

            # Send back to chat endpoint with frame data (use resolved_query)
            chat_request = ChatRequest(
                message=resolved_query,
                session_id=session_id,
                frame_data=frame_data,
                context=context,
                language=language,
            )

            response = await self._agent_client.send_chat_message(chat_request)

            if self._is_request_cancelled(request_id):
                return

            # Send the response
            self._send_chat_response(
                session_id=session_id,
                request_id=request_id,
                message=response.message,
                metadata=response.metadata,
                reasoning=response.reasoning
            )
            return

        # Standard flow: Send frame to vision agent for analysis
        carb.log_info("[CustomMessageManager] Sending frame to vision agent...")

        analysis_response = await self._agent_client.send_frame_for_analysis(
            frame_data=frame_data,
            original_query=resolved_query,
            session_id=session_id,
            context=context,
            language=language,
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
        context: Dict[str, Any],
        language: str,
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
            context=updated_context,
            language=language,
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

    def _send_typing_indicator(
        self,
        session_id: str,
        is_typing: bool,
        agent_type: Optional[str] = None,
        agent_name: Optional[str] = None
    ):
        """Send typing indicator with optional agent status to web client"""
        payload = {
            'session_id': session_id,
            'is_typing': is_typing
        }

        # Add agent status information if provided
        if agent_type:
            payload['agent_type'] = agent_type
        if agent_name:
            payload['agent_name'] = agent_name

        get_eventdispatcher().dispatch_event("chatTyping", payload=payload)

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

    # ===== PLANOGRAM CAPTURE =====
    # The full viewport frame is too large (~1-4 MB) for the WebRTC data channel
    # (~64 KB limit).  Strategy:
    #   1. planogramCaptureRequest  → Kit captures, stores full JPEG in memory,
    #                                 sends a small thumbnail (~15 KB) to browser.
    #   2. planogramAnalyzeRequest  → Kit sends stored full JPEG to backend,
    #                                 returns structured result to browser.
    # The large image never travels over WebRTC.

    def _on_planogram_capture_request(self, event: carb.events.IEvent):
        """Handle planogramCaptureRequest — capture and store frame, send thumbnail."""
        carb.log_info("[CustomMessageManager] planogramCaptureRequest received")
        asyncio.ensure_future(self._capture_and_send_planogram_frame())

    def _on_planogram_analyze_request(self, event: carb.events.IEvent):
        """Handle planogramAnalyzeRequest — POST stored frame to backend, return result."""
        payload = event.payload
        carb.log_info(f"[CustomMessageManager] planogramAnalyzeRequest: {payload}")
        asyncio.ensure_future(self._run_planogram_analysis(payload))

    async def _capture_and_send_planogram_frame(self):
        """Capture viewport, compress to JPEG, store full-res, send small thumbnail."""
        try:
            frame_b64 = await self._viewport_capture.capture_frame_async()
            if frame_b64 is None:
                get_eventdispatcher().dispatch_event(
                    "planogramCaptureResponse",
                    payload={"success": False, "error": "Frame capture failed"},
                )
                carb.log_warn("[CustomMessageManager] Planogram capture returned no data")
                return

            thumbnail_b64, vision_b64 = self._compress_planogram_frame(frame_b64)
            self._planogram_frame: Optional[str] = vision_b64

            carb.log_info(
                f"[CustomMessageManager] Planogram captured — "
                f"vision={len(vision_b64)//1024} KB, thumb={len(thumbnail_b64)//1024} KB"
            )

            get_eventdispatcher().dispatch_event(
                "planogramCaptureResponse",
                payload={"success": True, "thumbnail": thumbnail_b64},
            )
        except Exception as exc:
            carb.log_error(f"[CustomMessageManager] Planogram capture error: {exc}")
            get_eventdispatcher().dispatch_event(
                "planogramCaptureResponse",
                payload={"success": False, "error": str(exc)},
            )

    async def _run_planogram_analysis(self, payload: dict):
        """POST stored full-res frame to backend and dispatch result to browser."""
        vision_b64 = getattr(self, '_planogram_frame', None)
        if not vision_b64:
            get_eventdispatcher().dispatch_event(
                "planogramAnalysisResult",
                payload={"success": False, "error": "No captured frame — capture first"},
            )
            return

        model     = payload.get("model", "qwen")
        num_rows  = int(payload.get("num_rows", 4))
        shelf_id  = payload.get("shelf_id", "Shelf_1")
        backend   = self._agent_client._base_url
        url       = f"{backend}/api/planogram/analyze"
        body      = {"frame_data": vision_b64, "model": model, "num_rows": num_rows, "shelf_id": shelf_id}

        carb.log_info(f"[CustomMessageManager] Posting planogram to {url} model={model} rows={num_rows}")

        try:
            import json as _json
            import urllib.request as _urllib
            data = _json.dumps(body).encode("utf-8")
            req  = _urllib.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            loop = asyncio.get_event_loop()
            resp_data = await loop.run_in_executor(
                None,
                lambda: _json.loads(_urllib.urlopen(req, timeout=300).read().decode("utf-8"))
            )
            carb.log_info(f"[CustomMessageManager] Planogram result: {str(resp_data)[:200]}")
            get_eventdispatcher().dispatch_event(
                "planogramAnalysisResult",
                payload={"success": True, **resp_data},
            )
        except Exception as exc:
            carb.log_error(f"[CustomMessageManager] Planogram analysis error: {exc}")
            get_eventdispatcher().dispatch_event(
                "planogramAnalysisResult",
                payload={"success": False, "error": str(exc)},
            )

    @staticmethod
    def _compress_planogram_frame(frame_b64: str):
        """
        Return (thumbnail_b64, vision_b64).
        thumbnail  ~15 KB (400 px wide, q65) — safe for WebRTC data channel
        vision     full-res q90 JPEG         — sent server-side only
        """
        import base64 as _b64
        import io as _io
        try:
            from PIL import Image as _Image
            raw = _b64.b64decode(frame_b64)
            img = _Image.open(_io.BytesIO(raw)).convert("RGB")

            vis_buf = _io.BytesIO()
            img.save(vis_buf, format="JPEG", quality=90)
            vision_b64 = _b64.b64encode(vis_buf.getvalue()).decode("utf-8")

            ratio = 400 / img.width if img.width > 400 else 1.0
            thumb = img.resize((int(img.width * ratio), int(img.height * ratio)), _Image.LANCZOS)
            th_buf = _io.BytesIO()
            thumb.save(th_buf, format="JPEG", quality=65)
            thumbnail_b64 = _b64.b64encode(th_buf.getvalue()).decode("utf-8")

            return thumbnail_b64, vision_b64
        except Exception as exc:
            carb.log_warn(f"[CustomMessageManager] Frame compression failed ({exc}), using raw")
            return frame_b64, frame_b64

    # ===== ANALYZE SHELF (vision product ID + row detection planogram) =====

    def _on_analyze_shelf_request(self, event: carb.events.IEvent):
        """Handle analyzeShelfRequest — capture frame, identify products, detect rows."""
        carb.log_info("[CustomMessageManager] analyzeShelfRequest received")
        asyncio.ensure_future(self._run_shelf_analysis(dict(event.payload)))

    async def _run_shelf_analysis(self, payload: dict):
        """
        Full pipeline:
        1. Capture viewport frame
        2. POST to /api/identify-shelf-products → list of asset_keys
        3. For each key, call usd_spawner.detect_rows_for_key()
        4. Merge per-product rows into unified shelf levels by floor_z
        5. Dispatch analyzeShelfResponse
        """
        import json as _json
        import urllib.request as _urllib

        tolerance  = float(payload.get("tolerance_cm", 8.0))
        model      = payload.get("model", "qwen")
        asset_keys = payload.get("asset_keys")  # pre-filled → skip vision (refresh mode)

        def _err(msg: str):
            get_eventdispatcher().dispatch_event(
                "analyzeShelfResponse", payload={"success": False, "error": msg}
            )

        # 1. Capture frame (always — need a fresh thumbnail)
        frame_b64 = await self._viewport_capture.capture_frame_async()
        if not frame_b64:
            _err("Frame capture failed")
            return

        thumbnail_b64, vision_b64 = self._compress_planogram_frame(frame_b64)

        # 2. Identify products (skipped in refresh mode when asset_keys already known)
        if not asset_keys:
            backend = self._agent_client._base_url
            url     = f"{backend}/api/identify-shelf-products"
            body    = _json.dumps({"frame_data": vision_b64, "model": model}).encode("utf-8")
            try:
                loop = asyncio.get_event_loop()
                resp = await loop.run_in_executor(
                    None,
                    lambda: _json.loads(
                        _urllib.urlopen(
                            _urllib.Request(url, data=body,
                                            headers={"Content-Type": "application/json"},
                                            method="POST"),
                            timeout=120,
                        ).read().decode("utf-8")
                    ),
                )
                asset_keys = resp.get("products", [])
            except Exception as exc:
                carb.log_error(f"[CustomMessageManager] identify-shelf-products failed: {exc}")
                _err(f"Product identification failed: {exc}")
                return

            if not asset_keys:
                _err("No products recognised in the captured frame")
                return

        carb.log_info(f"[CustomMessageManager] analyzeShelf ({'refresh' if payload.get('asset_keys') else 'full'}): {len(asset_keys)} products → {asset_keys}")

        # 3. Row detection per product
        all_rows: dict = {}
        for key in asset_keys:
            result = self._usd_spawner.detect_rows_for_key(key, tolerance)
            if result and result.get("rows"):
                all_rows[key] = result["rows"]
                carb.log_info(f"[CustomMessageManager] analyzeShelf: {key} → {len(result['rows'])} rows")

        if not all_rows:
            _err("No shelf rows detected for any identified product")
            return

        # 4. Merge into unified shelf levels aligned by floor_z
        shelf_levels = self._merge_shelf_levels(all_rows, tolerance)

        # Strip prim_paths before sending — arrays can exceed the 65 KB WebRTC limit
        for lv in shelf_levels:
            for prod in lv.get("products", {}).values():
                prod.pop("prim_paths", None)

        # 5. Respond
        get_eventdispatcher().dispatch_event(
            "analyzeShelfResponse",
            payload={
                "success":      True,
                "shelf_levels": shelf_levels,
                "asset_keys":   list(all_rows.keys()),
                "thumbnail":    thumbnail_b64,
                "tolerance_cm": tolerance,
            },
        )

    @staticmethod
    def _merge_shelf_levels(all_rows: dict, tolerance: float) -> list:
        """
        Align per-product rows into shared shelf levels by floor_z proximity.
        Returns [{level, floor_z, products: {asset_key: {count, prim_paths}}}]
        """
        entries = sorted(
            [(row["floor_z"], key, row)
             for key, rows in all_rows.items()
             for row in rows],
            key=lambda x: x[0],
            reverse=True,
        )
        if not entries:
            return []

        # Cluster by floor_z gap (2× tolerance since products on the same shelf
        # level may not share exactly the same Z origin)
        clusters: list = []
        cur = [entries[0]]
        for entry in entries[1:]:
            if abs(entry[0] - cur[-1][0]) <= tolerance * 2:
                cur.append(entry)
            else:
                clusters.append(cur)
                cur = [entry]
        clusters.append(cur)

        shelf_levels = []
        for level_num, cluster in enumerate(clusters, start=1):
            avg_z = round(sum(e[0] for e in cluster) / len(cluster), 2)
            products: dict = {}
            for _, key, row in cluster:
                if key not in products:
                    products[key] = {"count": 0, "prim_paths": []}
                products[key]["count"]      += row["prim_count"]
                products[key]["prim_paths"] += row["prim_paths"]
            shelf_levels.append({"level": level_num, "floor_z": avg_z, "products": products})

        return shelf_levels

    # ===== CAMERA NAV POSITION REGISTRY =====

    def _dispatch_nav_positions(self, extra: dict = None) -> None:
        """Send positions list to the web client, chunked to stay under WebRTC 65535-byte limit."""
        positions = self._camera_navigation.get_all_positions_with_metadata()
        keys = list(positions.keys())
        CHUNK_SIZE = 10
        total_chunks = max(1, (len(keys) + CHUNK_SIZE - 1) // CHUNK_SIZE)

        for i in range(0, len(keys), CHUNK_SIZE):
            chunk_keys = keys[i:i + CHUNK_SIZE]
            chunk = {k: positions[k] for k in chunk_keys}
            chunk_index = i // CHUNK_SIZE
            payload = {
                "positions": chunk,
                "chunk": chunk_index,
                "total_chunks": total_chunks,
                "is_last_chunk": chunk_index == total_chunks - 1,
                **(extra or {} if chunk_index == total_chunks - 1 else {}),
            }
            get_eventdispatcher().dispatch_event("navPositionsResponse", payload=payload)

    def _on_get_nav_positions(self, event: carb.events.IEvent) -> None:
        carb.log_info("[CustomMessageManager] getNavPositions received")
        self._dispatch_nav_positions()

    def _on_register_nav_position(self, event: carb.events.IEvent) -> None:
        payload = event.payload
        name = payload.get("name", "").strip()
        location = tuple(payload.get("location", [0.0, 0.0, 0.0]))
        rotation = tuple(payload.get("rotation", [0.0, 0.0, 0.0]))
        description = payload.get("description", name)

        if not name:
            carb.log_warn("[CustomMessageManager] registerNavPosition: empty name ignored")
            return

        success = self._camera_navigation.save_position(name, location, rotation, description)
        carb.log_info(f"[CustomMessageManager] registerNavPosition '{name}' → saved={success}")

        # Sync to agent backend so chat can navigate to this position by name
        key = name.lower().strip().replace(" ", "_")
        asyncio.ensure_future(self._sync_nav_position_to_backend(
            key, list(location), list(rotation), description
        ))

        self._dispatch_nav_positions({"saved": success, "name": name})

    def _on_delete_nav_position(self, event: carb.events.IEvent) -> None:
        name = event.payload.get("name", "")
        success = self._camera_navigation.delete_position(name)
        carb.log_info(f"[CustomMessageManager] deleteNavPosition '{name}' → success={success}")

        asyncio.ensure_future(self._delete_nav_position_from_backend(name.lower()))

        self._dispatch_nav_positions({"deleted": success, "name": name})

    def _on_clear_nav_positions(self, event: carb.events.IEvent) -> None:
        success = self._camera_navigation.clear_custom_positions()
        carb.log_info(f"[CustomMessageManager] clearNavPositions → success={success}")

        asyncio.ensure_future(self._clear_nav_positions_from_backend())

        self._dispatch_nav_positions({"cleared": success})

    # ── Backend sync helpers ──────────────────────────────────────────────────

    async def _sync_nav_position_to_backend(
        self, name: str, location: list, rotation: list, description: str
    ) -> None:
        """POST a registered nav position to the agent backend."""
        import json as _json
        import urllib.request as _urllib
        url = f"{self._agent_client._base_url}/api/nav-positions"
        body = _json.dumps({
            "name": name, "description": description,
            "location": location, "rotation": rotation,
        }).encode("utf-8")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: _urllib.urlopen(
                    _urllib.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST"),
                    timeout=5
                )
            )
            carb.log_info(f"[CustomMessageManager] Synced nav position '{name}' to backend")
        except Exception as e:
            carb.log_warn(f"[CustomMessageManager] Could not sync nav position to backend: {e}")

    async def _delete_nav_position_from_backend(self, name: str) -> None:
        """DELETE a nav position from the agent backend."""
        import urllib.request as _urllib
        url = f"{self._agent_client._base_url}/api/nav-positions/{name}"
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: _urllib.urlopen(
                    _urllib.Request(url, method="DELETE"),
                    timeout=5
                )
            )
            carb.log_info(f"[CustomMessageManager] Deleted nav position '{name}' from backend")
        except Exception as e:
            carb.log_warn(f"[CustomMessageManager] Could not delete nav position from backend: {e}")

    async def _clear_nav_positions_from_backend(self) -> None:
        """DELETE all custom nav positions from the agent backend."""
        import urllib.request as _urllib
        url = f"{self._agent_client._base_url}/api/nav-positions"
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: _urllib.urlopen(
                    _urllib.Request(url, method="DELETE"),
                    timeout=5
                )
            )
            carb.log_info("[CustomMessageManager] Cleared all nav positions from backend")
        except Exception as e:
            carb.log_warn(f"[CustomMessageManager] Could not clear nav positions from backend: {e}")

    def _on_get_camera_position(self, event: carb.events.IEvent) -> None:
        try:
            pos = self._read_camera_position_robust()
            carb.log_info(f"[CustomMessageManager] getCameraPosition → {pos}")
            if pos:
                get_eventdispatcher().dispatch_event(
                    "cameraPositionResponse",
                    payload={
                        "success": True,
                        "location": pos["location"],
                        "rotation": pos["rotation"],
                    }
                )
            else:
                get_eventdispatcher().dispatch_event(
                    "cameraPositionResponse",
                    payload={"success": False, "error": "Camera position unavailable"}
                )
        except Exception as exc:
            carb.log_error(f"[CustomMessageManager] getCameraPosition error: {exc}")
            get_eventdispatcher().dispatch_event(
                "cameraPositionResponse",
                payload={"success": False, "error": str(exc)}
            )

    def _read_camera_position_robust(self):
        """
        Read camera position + rotation via world-transform matrix decomposition.
        Always decomposes the world matrix for rotation — never reads raw op values,
        which can be stale or zero-initialized if ops were just created.
        Returns dict with 'location' (list[float,3]) and 'rotation' (list[float,3]).
        """
        import math
        try:
            import omni.usd
            from pxr import UsdGeom

            stage = omni.usd.get_context().get_stage()
            if not stage:
                carb.log_warn("[CustomMessageManager] No stage for camera position")
                return None

            # Prefer the active viewport camera path so we read what the user sees
            camera_prim = None
            try:
                from omni.kit.viewport.utility import get_active_viewport_camera_path
                cam_path = get_active_viewport_camera_path()
                if cam_path:
                    camera_prim = stage.GetPrimAtPath(cam_path)
                    carb.log_info(f"[CustomMessageManager] Using viewport camera: {cam_path}")
            except Exception as e:
                carb.log_warn(f"[CustomMessageManager] Could not get viewport camera path: {e}")

            # Fall back to the configured camera path
            if not camera_prim or not camera_prim.IsValid():
                fallback = self._camera_navigation._camera_path
                camera_prim = stage.GetPrimAtPath(fallback)
                carb.log_info(f"[CustomMessageManager] Using configured camera: {fallback}")

            if not camera_prim or not camera_prim.IsValid():
                carb.log_warn("[CustomMessageManager] No valid camera prim found")
                return None

            xformable = UsdGeom.Xformable(camera_prim)

            # Always use world transform — it reflects the true camera state regardless
            # of whether ops are translate/rotate or a combined matrix op.
            world_xform = xformable.ComputeLocalToWorldTransform(0)
            t = world_xform.ExtractTranslation()
            location = [float(t[0]), float(t[1]), float(t[2])]

            # Decompose rotation matrix → Euler XYZ degrees
            m = world_xform.ExtractRotationMatrix()
            # USD uses row-vector convention: M = Rx * Ry * Rz
            # sy = |cos(ry)| comes from the first row of M
            sy = math.sqrt(m[0][0] ** 2 + m[0][1] ** 2)
            if sy > 1e-6:
                rx = math.degrees(math.atan2(m[1][2], m[2][2]))
                ry = math.degrees(math.atan2(-m[0][2], sy))
                rz = math.degrees(math.atan2(m[0][1], m[0][0]))
            else:
                rx = math.degrees(math.atan2(-m[2][1], m[1][1]))
                ry = math.degrees(math.atan2(-m[0][2], sy))
                rz = 0.0
            rotation = [rx, ry, rz]

            carb.log_info(
                f"[CustomMessageManager] Camera: "
                f"t=({location[0]:.1f},{location[1]:.1f},{location[2]:.1f}) "
                f"r=({rotation[0]:.2f},{rotation[1]:.2f},{rotation[2]:.2f})"
            )
            return {"location": location, "rotation": rotation}

        except Exception as e:
            import traceback
            carb.log_error(f"[CustomMessageManager] _read_camera_position_robust failed: {e}")
            carb.log_error(traceback.format_exc())
            return None

    def _on_navigate_to_direct(self, event: carb.events.IEvent) -> None:
        """Direct navigation from the UI panel (bypasses the chat agent)."""
        destination = event.payload.get("destination", "")
        instant = event.payload.get("instant", False)
        speed = float(event.payload.get("speed", 1.0))
        carb.log_info(f"[CustomMessageManager] navigateTo '{destination}' instant={instant}")
        asyncio.ensure_future(self._do_navigate_direct(destination, instant, speed))

    async def _do_navigate_direct(self, destination: str|Dict, instant: bool, speed: float) -> None:
        success = await self._camera_navigation.navigate_to(
            destination=destination, instant=instant, speed=speed
        )
        if not success:
            carb.log_warn(f"[CustomMessageManager] Direct navigation failed: '{destination}'")

    # ── Per-store built-in preset handlers ──────────────────────────────────

    # ── Waypoint route handlers ────────────────────────────────────────────

    def _on_save_nav_route(self, event: carb.events.IEvent) -> None:
        """
        Handle saveNavRoute message.
        Payload: {
            destination: "pringles",
            waypoints: [{location:[x,y,z], rotation:[rx,ry,rz]}, ...],
            start: {location:[x,y,z], rotation:[rx,ry,rz]}  // optional
        }
        """
        destination = event.payload.get("destination", "").strip()
        waypoints = event.payload.get("waypoints", [])
        if not destination:
            carb.log_warn("[CustomMessageManager] saveNavRoute: empty destination ignored")
            return
        # Convert flat dicts from WebRTC payload
        wp_list = []
        for wp in waypoints:
            loc = wp.get("location", [0, 0, 0])
            rot = wp.get("rotation", [0, 0, 0])
            wp_list.append({"location": list(loc), "rotation": list(rot)})

        # Optional start position
        start_raw = event.payload.get("start")
        start = None
        if start_raw and isinstance(start_raw, dict):
            start = {
                "location": list(start_raw.get("location", [0, 0, 0])),
                "rotation": list(start_raw.get("rotation", [0, 0, 0])),
            }

        success = self._camera_navigation.save_route(destination, wp_list, start=start)
        carb.log_info(
            f"[CustomMessageManager] saveNavRoute '{destination}' "
            f"({len(wp_list)} waypoints, start={'yes' if start else 'no'}) → saved={success}"
        )
        self._dispatch_nav_routes({"saved": success, "destination": destination})

    def _on_delete_nav_route(self, event: carb.events.IEvent) -> None:
        """Handle deleteNavRoute message.  Payload: { destination: "pringles" }"""
        destination = event.payload.get("destination", "").strip()
        if not destination:
            return
        success = self._camera_navigation.delete_route(destination)
        carb.log_info(f"[CustomMessageManager] deleteNavRoute '{destination}' → success={success}")
        self._dispatch_nav_routes({"deleted": success, "destination": destination})

    def _on_get_nav_routes(self, event: carb.events.IEvent) -> None:
        carb.log_info("[CustomMessageManager] getNavRoutes received")
        self._dispatch_nav_routes()

    def _dispatch_nav_routes(self, extra: dict = None) -> None:
        """Send all routes to the web client."""
        routes = self._camera_navigation.get_all_routes()
        payload = {"routes": routes, **(extra or {})}
        get_eventdispatcher().dispatch_event("navRoutesResponse", payload=payload)

    # ── End waypoint route handlers ────────────────────────────────────────

    def _on_set_active_store(self, event: carb.events.IEvent) -> None:
        """
        Handle setActiveStore message from the web client.
        Payload: { store_key: "pipc" | "711" | ... }
        Loads the store's built-in positions from store_presets/<key>.json.
        """
        store_key = event.payload.get("store_key", "").strip()
        if not store_key:
            carb.log_warn("[CustomMessageManager] setActiveStore: empty store_key ignored")
            return
        carb.log_info(f"[CustomMessageManager] setActiveStore '{store_key}'")
        self._camera_navigation.set_active_store(store_key)
        self._dispatch_nav_positions({"store_key": store_key})
        self._dispatch_nav_routes({"store_key": store_key})

    def _on_promote_nav_position(self, event: carb.events.IEvent) -> None:
        """
        Handle promoteNavPosition message — promote a single custom position to built-in
        for the currently active store.
        Payload: { name: "entrance" }
        """
        name = event.payload.get("name", "").strip()
        if not name:
            carb.log_warn("[CustomMessageManager] promoteNavPosition: empty name ignored")
            return
        carb.log_info(f"[CustomMessageManager] promoteNavPosition '{name}'")
        success = self._camera_navigation.promote_to_builtin(name)
        self._dispatch_nav_positions({"promoted": success, "name": name})

    def _on_save_all_as_builtin(self, event: carb.events.IEvent) -> None:
        """
        Handle saveAllAsBuiltin message — promote ALL current custom positions to
        built-in for the currently active store.
        Payload: {} (no parameters needed)
        """
        carb.log_info("[CustomMessageManager] saveAllAsBuiltin")
        success = self._camera_navigation.save_all_custom_as_builtin()
        self._dispatch_nav_positions({"all_saved_as_builtin": success})

    # ===== END CAMERA NAV POSITION REGISTRY =====

    def on_shutdown(self):
        """Clean up when the manager is shut down"""
        carb.log_info("[CustomMessageManager] Shutting down...")

        # Cancel pending requests
        for request_id in list(self._pending_requests.keys()):
            self._pending_requests[request_id]['cancelled'] = True
        self._pending_requests.clear()

        # Clear camera position tracking
        self._last_camera_positions.clear()

        # Shut down USD spawner
        if self._usd_spawner:
            self._usd_spawner.on_shutdown()
            self._usd_spawner = None

        # Clean up subscriptions
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()