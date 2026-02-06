# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import base64
import io
from typing import Optional, Callable, Dict, Any

import carb
import omni.kit.app


class ViewportCapture:
    """Utility class for capturing viewport frames as images using omni.kit.viewport.utility"""

    def __init__(self):
        self._capture_in_progress = False

    def _get_active_viewport(self):
        """Get the active viewport using the new API"""
        try:
            from omni.kit.viewport.utility import get_active_viewport
            viewport = get_active_viewport()
            if viewport is None:
                carb.log_warn("[ViewportCapture] No active viewport found")
            return viewport
        except ImportError:
            carb.log_error("[ViewportCapture] omni.kit.viewport.utility not available")
            return None
        except Exception as e:
            carb.log_error(f"[ViewportCapture] Failed to get active viewport: {e}")
            return None

    def get_camera_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current camera information from the active viewport.

        Returns:
            Dictionary with camera path and position info, or None if unavailable
        """
        try:
            from omni.kit.viewport.utility import (
                get_active_viewport_camera_path,
                get_active_viewport_camera_string
            )
            import omni.usd
            from pxr import UsdGeom

            camera_path = get_active_viewport_camera_path()
            camera_string = get_active_viewport_camera_string()

            if not camera_path:
                return None

            # Get camera transform
            ctx = omni.usd.get_context()
            stage = ctx.get_stage()
            if not stage:
                return {"path": camera_string, "valid": False}

            camera_prim = stage.GetPrimAtPath(camera_path)
            if not camera_prim:
                return {"path": camera_string, "valid": False}

            # Get world transform
            xformable = UsdGeom.Xformable(camera_prim)
            world_transform = xformable.ComputeLocalToWorldTransform(0)
            translation = world_transform.ExtractTranslation()

            return {
                "path": camera_string,
                "position": {
                    "x": float(translation[0]),
                    "y": float(translation[1]),
                    "z": float(translation[2])
                },
                "valid": True
            }

        except Exception as e:
            carb.log_warn(f"[ViewportCapture] Failed to get camera info: {e}")
            return None

    async def capture_frame_async(
        self,
        width: int = 1280,
        height: int = 720,
        viewport_name: str = "Viewport"
    ) -> Optional[str]:
        """
        Capture the current viewport frame as a base64-encoded PNG image.

        Args:
            width: Output image width (not used in new API, captures at viewport resolution)
            height: Output image height (not used in new API, captures at viewport resolution)
            viewport_name: Name of the viewport to capture

        Returns:
            Base64-encoded PNG image string, or None if capture failed
        """
        if self._capture_in_progress:
            carb.log_warn("[ViewportCapture] Capture already in progress")
            return None

        self._capture_in_progress = True

        try:
            from omni.kit.viewport.utility import (
                capture_viewport_to_buffer,
                get_active_viewport,
                get_viewport_from_window_name,
                next_viewport_frame_async
            )

            # Get viewport - try specific window first, then active
            viewport = get_viewport_from_window_name(viewport_name)
            if viewport is None:
                viewport = get_active_viewport()

            if viewport is None:
                carb.log_error("[ViewportCapture] No viewport available")
                return None

            # Wait for viewport to be ready
            await next_viewport_frame_async(viewport)

            # Create a future to wait for capture completion
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            captured_data = None

            def on_capture_complete(buffer, buffer_size, img_width, img_height, img_format):
                """Callback when capture is complete"""
                nonlocal captured_data
                try:
                    if buffer is not None and buffer_size > 0:
                        import ctypes

                        # Determine buffer type and extract bytes
                        buffer_type = type(buffer).__name__
                        carb.log_info(f"[ViewportCapture] Buffer type: {buffer_type}, size: {buffer_size}")

                        if buffer_type == 'PyCapsule':
                            # Extract pointer from PyCapsule
                            ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
                            ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
                            ptr = ctypes.pythonapi.PyCapsule_GetPointer(buffer, None)
                            if ptr:
                                data = ctypes.string_at(ptr, buffer_size)
                            else:
                                carb.log_error("[ViewportCapture] Failed to get pointer from PyCapsule")
                                return
                        elif isinstance(buffer, ctypes.c_void_p):
                            data = ctypes.string_at(buffer.value, buffer_size)
                        elif isinstance(buffer, int):
                            data = ctypes.string_at(buffer, buffer_size)
                        elif isinstance(buffer, (bytes, bytearray)):
                            data = bytes(buffer)
                        elif hasattr(buffer, '__array_interface__'):
                            # Handle numpy array or similar
                            import numpy as np
                            arr = np.array(buffer, copy=False)
                            data = arr.tobytes()
                        else:
                            # Last resort: try memoryview
                            try:
                                data = bytes(memoryview(buffer))
                            except TypeError:
                                carb.log_error(f"[ViewportCapture] Unsupported buffer type: {buffer_type}")
                                return

                        # Convert to PNG if needed and encode as base64
                        captured_data = self._convert_to_base64_png(data, img_width, img_height, img_format)
                        carb.log_info(f"[ViewportCapture] Captured frame: {img_width}x{img_height}")
                    else:
                        carb.log_warn("[ViewportCapture] Capture returned empty buffer")
                except Exception as e:
                    carb.log_error(f"[ViewportCapture] Error processing capture: {e}")
                    import traceback
                    carb.log_error(f"[ViewportCapture] Traceback: {traceback.format_exc()}")
                finally:
                    if not future.done():
                        future.set_result(captured_data)

            # Capture to buffer with callback
            capture_viewport_to_buffer(viewport, on_capture_complete)

            # Wait for completion with timeout
            try:
                result = await asyncio.wait_for(future, timeout=10.0)
                return result
            except asyncio.TimeoutError:
                carb.log_error("[ViewportCapture] Capture timed out")
                return None

        except ImportError as e:
            carb.log_warn(f"[ViewportCapture] Import error: {e}, trying alternative method")
            return await self._capture_via_renderer(width, height)
        except Exception as e:
            carb.log_error(f"[ViewportCapture] Capture failed: {e}")
            import traceback
            carb.log_error(f"[ViewportCapture] Traceback: {traceback.format_exc()}")
            return None
        finally:
            self._capture_in_progress = False

    def _convert_to_base64_png(
        self,
        data: bytes,
        width: int,
        height: int,
        img_format
    ) -> Optional[str]:
        """Convert raw image data to base64-encoded PNG"""
        try:
            from PIL import Image

            # Convert TextureFormat enum to string if needed
            format_str = ""
            if img_format is not None:
                if hasattr(img_format, 'name'):
                    # It's a TextureFormat enum
                    format_str = img_format.name.upper()
                elif isinstance(img_format, str):
                    format_str = img_format.upper()
                else:
                    format_str = str(img_format).upper()

            carb.log_info(f"[ViewportCapture] Image format: {format_str}")

            # Determine PIL mode based on format
            # Common formats: RGBA8_UNORM, BGRA8_UNORM, RGBA8_SRGB, etc.
            if 'BGRA' in format_str:
                # BGRA format - need to swap channels
                img = Image.frombytes('RGBA', (width, height), data)
                # Swap R and B channels
                r, g, b, a = img.split()
                img = Image.merge('RGBA', (b, g, r, a))
            elif 'RGBA' in format_str:
                # RGBA format
                img = Image.frombytes('RGBA', (width, height), data)
            elif 'RGB' in format_str and 'RGBA' not in format_str:
                # RGB format (no alpha)
                img = Image.frombytes('RGB', (width, height), data)
            else:
                # Default: try RGBA first (most common for viewport capture)
                try:
                    img = Image.frombytes('RGBA', (width, height), data)
                except ValueError:
                    try:
                        img = Image.frombytes('RGB', (width, height), data)
                    except ValueError as e:
                        carb.log_error(f"[ViewportCapture] Cannot decode image data: {e}")
                        return None

            # Convert to PNG in memory
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            # Encode as base64
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

        except ImportError:
            carb.log_error("[ViewportCapture] PIL not available for PNG conversion")
            # Return raw data as base64 if PIL not available
            return base64.b64encode(data).decode('utf-8')
        except Exception as e:
            carb.log_error(f"[ViewportCapture] Failed to convert to PNG: {e}")
            import traceback
            carb.log_error(f"[ViewportCapture] Traceback: {traceback.format_exc()}")
            return None

    async def _capture_via_renderer(self, width: int, height: int) -> Optional[str]:
        """Alternative capture method using renderer directly (fallback)"""
        try:
            import omni.renderer_capture

            # Get the capture interface
            capture = omni.renderer_capture.acquire_renderer_capture_interface()

            # Create a future to wait for capture completion
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            captured_data = None

            def on_capture_complete(buffer, buffer_size, width, height, format):
                nonlocal captured_data
                if buffer:
                    import ctypes
                    buffer_type = type(buffer).__name__

                    if buffer_type == 'PyCapsule':
                        # Extract pointer from PyCapsule
                        ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
                        ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
                        ptr = ctypes.pythonapi.PyCapsule_GetPointer(buffer, None)
                        if ptr:
                            data = ctypes.string_at(ptr, buffer_size)
                        else:
                            if not future.done():
                                future.set_result(None)
                            return
                    elif isinstance(buffer, int):
                        data = ctypes.string_at(buffer, buffer_size)
                    else:
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
                carb.log_error("[ViewportCapture] Renderer capture timed out")
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
            width: Output image width (not used in new API)
            height: Output image height (not used in new API)
            viewport_name: Name of the viewport to capture

        Returns:
            True if successful, False otherwise
        """
        try:
            from omni.kit.viewport.utility import (
                capture_viewport_to_file,
                get_active_viewport,
                get_viewport_from_window_name,
                next_viewport_frame_async
            )

            # Get viewport
            viewport = get_viewport_from_window_name(viewport_name)
            if viewport is None:
                viewport = get_active_viewport()

            if viewport is None:
                carb.log_error("[ViewportCapture] No viewport available for file capture")
                return False

            # Wait for viewport to be ready
            await next_viewport_frame_async(viewport)

            # Capture to file using new API
            capture_helper = capture_viewport_to_file(viewport, file_path=file_path)

            # Wait for the capture to complete
            await capture_helper.wait_for_result(completion_frames=30)

            carb.log_info(f"[ViewportCapture] Saved frame to: {file_path}")
            return True

        except Exception as e:
            carb.log_error(f"[ViewportCapture] Failed to save frame: {e}")
            import traceback
            carb.log_error(f"[ViewportCapture] Traceback: {traceback.format_exc()}")
            return False

    async def capture_frame_hdr(
        self,
        file_path: str,
        viewport_name: str = "Viewport"
    ) -> bool:
        """
        Capture viewport frame with HDR enabled and save to EXR file.

        Args:
            file_path: Path to save the EXR image (should end with .exr)
            viewport_name: Name of the viewport to capture

        Returns:
            True if successful, False otherwise
        """
        try:
            from omni.kit.viewport.utility import (
                capture_viewport_to_file,
                get_active_viewport,
                get_viewport_from_window_name,
                next_viewport_frame_async
            )

            # Get viewport
            viewport = get_viewport_from_window_name(viewport_name)
            if viewport is None:
                viewport = get_active_viewport()

            if viewport is None:
                carb.log_error("[ViewportCapture] No viewport available for HDR capture")
                return False

            # Wait for viewport to be ready
            await next_viewport_frame_async(viewport)

            # Capture with HDR enabled
            capture_helper = capture_viewport_to_file(
                viewport,
                file_path,
                is_hdr=True
            )

            # Wait for the capture to complete
            await capture_helper.wait_for_result(completion_frames=30)

            carb.log_info(f"[ViewportCapture] Saved HDR frame to: {file_path}")
            return True

        except Exception as e:
            carb.log_error(f"[ViewportCapture] Failed to save HDR frame: {e}")
            return False
