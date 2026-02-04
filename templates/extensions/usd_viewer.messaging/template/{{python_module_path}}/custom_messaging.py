# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import uuid
from typing import Dict, Any, Optional

import carb
import carb.events
from carb.eventdispatcher import get_eventdispatcher
import omni.kit.app
import omni.kit.livestream.messaging as messaging
from omni.timeline import get_timeline_interface

from .viewport_capture import ViewportCapture
from .agent_client import AgentClient, AgentAction, ChatRequest, AgentResponse


class CustomMessageManager:
    """Manages custom messages between web client and Kit application"""

    def __init__(self, agent_backend_url: str = "http://localhost:8000"):
        """Initialize the custom message manager"""
        self._subscriptions = []
        self._timeline = get_timeline_interface()
        self._viewport_capture = ViewportCapture()
        self._agent_client = AgentClient(base_url=agent_backend_url)
        self._pending_requests: Dict[str, Dict[str, Any]] = {}  # Track pending chat requests
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

            # Send initial message to agent
            chat_request = ChatRequest(
                message=message,
                session_id=session_id,
                context=context
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
                    context=context
                )
            elif response.action == AgentAction.GET_SCENE_INFO:
                # Agent requested scene information
                await self._handle_get_scene_info_action(
                    request_id=request_id,
                    original_message=message,
                    session_id=session_id,
                    response=response,
                    context=context
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

        # Send final response to client
        self._send_chat_response(
            session_id=session_id,
            request_id=request_id,
            message=analysis_response.message,
            metadata={
                **(analysis_response.metadata or {}),
                "frame_analyzed": True
            }
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
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Send chat response to web client"""
        get_eventdispatcher().dispatch_event(
            "chatResponse",
            payload={
                'session_id': session_id,
                'request_id': request_id,
                'message': message,
                'metadata': metadata or {},
                'status': 'success'
            }
        )
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

        # Clean up subscriptions
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()