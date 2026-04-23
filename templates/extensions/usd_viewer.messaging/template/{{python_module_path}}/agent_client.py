# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import json
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

import carb


class AgentAction(Enum):
    """Actions that the agent can request from the Kit application"""
    NONE = "none"
    CAPTURE_FRAME = "capture_frame"
    GET_SCENE_INFO = "get_scene_info"
    HIGHLIGHT_OBJECT = "highlight_object"
    NAVIGATE_TO = "navigate_to"  # Navigate camera to a location
    FORECAST_DEMAND = "forecast_demand"  # Demand forecast action
    SEARCH_EC = "search_ec"  # E-commerce search action
    SPAWN_USD = "spawn_usd"  # Spawn a USD asset at a user-clicked location


@dataclass
class AgentResponse:
    """Response from the agent backend"""
    message: str
    action: AgentAction = AgentAction.NONE
    action_params: Optional[Dict[str, Any]] = None
    requires_followup: bool = False
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None  # AI reasoning/thinking process
    captured_frame: Optional[str] = None  # Base64 encoded frame for UI display


@dataclass
class ChatRequest:
    """Chat request to send to agent backend"""
    message: str
    session_id: str
    frame_data: Optional[str] = None  # Base64 encoded image
    context: Optional[Dict[str, Any]] = None
    language: str = "en"


class AgentClient:
    """HTTP client for communicating with the agent backend"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0
    ):
        """
        Initialize the agent client.

        Args:
            base_url: Base URL of the agent backend
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout
        self._session_store: Dict[str, Dict[str, Any]] = {}

        carb.log_info(f"[AgentClient] Initialized with base URL: {self._base_url}")

    async def send_chat_message(self, request: ChatRequest) -> AgentResponse:
        """
        Send a chat message to the agent backend.

        Args:
            request: The chat request

        Returns:
            AgentResponse from the backend
        """
        try:
            import aiohttp
        except ImportError:
            carb.log_warn("[AgentClient] aiohttp not available, using urllib fallback")
            return await self._send_chat_urllib(request)

        url = f"{self._base_url}/api/chat"

        payload = {
            "message": request.message,
            "session_id": request.session_id,
            "context": request.context or {},
            "language": request.language,
        }

        if request.frame_data:
            payload["frame_data"] = request.frame_data

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_response(data)
                    else:
                        error_text = await response.text()
                        carb.log_error(f"[AgentClient] Request failed: {response.status} - {error_text}")
                        return AgentResponse(
                            message=f"Error: Server returned {response.status}",
                            action=AgentAction.NONE
                        )

        except asyncio.TimeoutError:
            carb.log_error("[AgentClient] Request timed out")
            return AgentResponse(
                message="Error: Request timed out. Please try again.",
                action=AgentAction.NONE
            )
        except Exception as e:
            carb.log_error(f"[AgentClient] Request failed: {e}")
            return AgentResponse(
                message=f"Error: {str(e)}",
                action=AgentAction.NONE
            )

    async def _send_chat_urllib(self, request: ChatRequest) -> AgentResponse:
        """Fallback using urllib for when aiohttp is not available"""
        import urllib.request
        import urllib.error

        url = f"{self._base_url}/api/chat"

        payload = {
            "message": request.message,
            "session_id": request.session_id,
            "context": request.context or {},
            "language": request.language,
        }

        if request.frame_data:
            payload["frame_data"] = request.frame_data

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            # Run in executor to not block
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=self._timeout)
            )

            response_data = json.loads(response.read().decode('utf-8'))
            return self._parse_response(response_data)

        except urllib.error.HTTPError as e:
            carb.log_error(f"[AgentClient] HTTP error: {e.code}")
            return AgentResponse(
                message=f"Error: Server returned {e.code}",
                action=AgentAction.NONE
            )
        except Exception as e:
            carb.log_error(f"[AgentClient] Request failed: {e}")
            return AgentResponse(
                message=f"Error: {str(e)}",
                action=AgentAction.NONE
            )

    async def send_frame_for_analysis(
        self,
        frame_data: str,
        original_query: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> AgentResponse:
        """
        Send a captured frame to the vision agent for analysis.

        Args:
            frame_data: Base64 encoded image
            original_query: The original user query
            session_id: Session identifier
            context: Additional context
            language: Response language code

        Returns:
            AgentResponse with the analysis
        """
        try:
            import aiohttp
        except ImportError:
            return await self._send_analysis_urllib(
                frame_data, original_query, session_id, context, language
            )

        url = f"{self._base_url}/api/analyze"

        payload = {
            "frame_data": frame_data,
            "query": original_query,
            "session_id": session_id,
            "context": context or {},
            "language": language,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        carb.log_info(f"[AgentClient] Analysis response received: {data}")
                        return self._parse_response(data)
                    else:
                        error_text = await response.text()
                        carb.log_error(f"[AgentClient] Analysis failed: {response.status}")
                        return AgentResponse(
                            message=f"Error analyzing image: {error_text}",
                            action=AgentAction.NONE
                        )

        except Exception as e:
            carb.log_error(f"[AgentClient] Analysis request failed: {e}")
            return AgentResponse(
                message=f"Error: {str(e)}",
                action=AgentAction.NONE
            )

    async def _send_analysis_urllib(
        self,
        frame_data: str,
        original_query: str,
        session_id: str,
        context: Optional[Dict[str, Any]],
        language: str,
    ) -> AgentResponse:
        """Fallback analysis using urllib"""
        import urllib.request
        import urllib.error

        url = f"{self._base_url}/api/analyze"

        payload = {
            "frame_data": frame_data,
            "query": original_query,
            "session_id": session_id,
            "context": context or {},
            "language": language,
        }

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=self._timeout)
            )

            response_data = json.loads(response.read().decode('utf-8'))
            return self._parse_response(response_data)

        except Exception as e:
            carb.log_error(f"[AgentClient] Analysis request failed: {e}")
            return AgentResponse(
                message=f"Error: {str(e)}",
                action=AgentAction.NONE
            )

    def _parse_response(self, data: Dict[str, Any]) -> AgentResponse:
        """Parse the backend response into an AgentResponse object"""
        action_str = data.get('action', 'none')
        try:
            action = AgentAction(action_str)
        except ValueError:
            action = AgentAction.NONE

        return AgentResponse(
            message=data.get('message', ''),
            action=action,
            action_params=data.get('action_params'),
            requires_followup=data.get('requires_followup', False),
            session_id=data.get('session_id'),
            metadata=data.get('metadata'),
            reasoning=data.get('reasoning'),
            captured_frame=data.get('captured_frame')
        )

    async def health_check(self) -> bool:
        """Check if the agent backend is available"""
        try:
            import urllib.request

            url = f"{self._base_url}/health"
            req = urllib.request.Request(url, method='GET')

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=5.0)
            )
            return response.status == 200

        except Exception as e:
            carb.log_warn(f"[AgentClient] Health check failed: {e}")
            return False

    def set_base_url(self, url: str):
        """Update the base URL for the agent backend"""
        self._base_url = url.rstrip('/')
        carb.log_info(f"[AgentClient] Base URL updated to: {self._base_url}")
