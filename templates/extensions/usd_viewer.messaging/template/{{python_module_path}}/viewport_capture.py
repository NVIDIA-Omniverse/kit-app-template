# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import base64
import io
from typing import Optional, Callable

import carb
import omni.kit.app


class ViewportCapture:
    """Utility class for capturing viewport frames as images"""

    def __init__(self):
        self._capture_in_progress = False

    async def capture_frame_async(
        self,
        width: int = 1280,
        height: int = 720,
        viewport_name: str = "Viewport"
    ) -> Optional[str]:
        """
        Capture the current viewport frame as a base64-encoded PNG image.

        Args:
            width: Output image width
            height: Output image height
            viewport_name: Name of the viewport to capture

        Returns:
            Base64-encoded PNG image string, or None if capture failed
        """
        if self._capture_in_progress:
            carb.log_warn("[ViewportCapture] Capture already in progress")
            return None

        self._capture_in_progress = True

        try:
            # Try to use omni.kit.viewport.utility for capture
            try:
                from omni.kit.viewport.utility import capture_viewport_to_buffer

                # Capture viewport to buffer
                buffer = await capture_viewport_to_buffer(
                    viewport_api_name=viewport_name,
                    width=width,
                    height=height
                )

                if buffer is not None:
                    # Convert buffer to base64
                    base64_image = base64.b64encode(buffer).decode('utf-8')
                    carb.log_info(f"[ViewportCapture] Captured frame: {len(base64_image)} bytes")
                    return base64_image

            except ImportError:
                carb.log_warn("[ViewportCapture] omni.kit.viewport.utility not available, trying alternative")
                return await self._capture_via_renderer(width, height)

        except Exception as e:
            carb.log_error(f"[ViewportCapture] Capture failed: {e}")
            return None
        finally:
            self._capture_in_progress = False

    async def _capture_via_renderer(self, width: int, height: int) -> Optional[str]:
        """Alternative capture method using renderer directly"""
        try:
            import omni.renderer_capture

            # Get the capture interface
            capture = omni.renderer_capture.acquire_renderer_capture_interface()

            # Create a future to wait for capture completion
            future = asyncio.get_event_loop().create_future()
            captured_data = None

            def on_capture_complete(buffer, buffer_size, width, height, format):
                nonlocal captured_data
                if buffer:
                    # Convert to bytes and encode as base64
                    import ctypes
                    data = ctypes.string_at(buffer, buffer_size)
                    captured_data = base64.b64encode(data).decode('utf-8')
                if not future.done():
                    future.set_result(captured_data)

            # Request capture
            capture.capture_next_frame_swapchain_callback(on_capture_complete)

            # Wait for completion with timeout
            try:
                result = await asyncio.wait_for(future, timeout=5.0)
                return result
            except asyncio.TimeoutError:
                carb.log_error("[ViewportCapture] Capture timed out")
                return None

        except ImportError:
            carb.log_error("[ViewportCapture] No capture method available")
            return None

    def capture_frame_sync(
        self,
        callback: Callable[[Optional[str]], None],
        width: int = 1280,
        height: int = 720,
        viewport_name: str = "Viewport"
    ):
        """
        Capture frame synchronously with callback.

        Args:
            callback: Function to call with the base64 image data
            width: Output image width
            height: Output image height
            viewport_name: Name of the viewport to capture
        """
        async def _do_capture():
            result = await self.capture_frame_async(width, height, viewport_name)
            callback(result)

        asyncio.ensure_future(_do_capture())

    async def capture_frame_to_file(
        self,
        file_path: str,
        width: int = 1920,
        height: int = 1080,
        viewport_name: str = "Viewport"
    ) -> bool:
        """
        Capture viewport frame and save to file.

        Args:
            file_path: Path to save the image
            width: Output image width
            height: Output image height
            viewport_name: Name of the viewport to capture

        Returns:
            True if successful, False otherwise
        """
        try:
            from omni.kit.viewport.utility import capture_viewport_to_file

            await capture_viewport_to_file(
                viewport_api_name=viewport_name,
                file_path=file_path,
                width=width,
                height=height
            )
            carb.log_info(f"[ViewportCapture] Saved frame to: {file_path}")
            return True

        except Exception as e:
            carb.log_error(f"[ViewportCapture] Failed to save frame: {e}")
            return False
