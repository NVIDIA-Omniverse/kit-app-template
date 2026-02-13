# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import math
from typing import Dict, Any, Optional, Tuple, Callable

import carb


# Store location presets - can be loaded from config or scene
STORE_POSITIONS = {
    "pringles": {
        "location": (202.81, 153.37, -57.66),
        "rotation": (-2.75, 0.71, 0.03),
        "description": "Pringles snack shelf"
    },
    "cheetos": {
        "location": (180.60, 140.30, -62.09),
        "rotation": (-21.39, -2.35, -0.86),
        "description": "Cheetos snack area"
    },
    "coffee_station": {
        "location": (-108.34, 270.27, -812.71),
        "rotation": (1.96, 2.77, -0.09),
        "description": "Coffee station"
    },
    "ufc_refresh_coconut_water": {
        "location": (-151.78, 262.27, -647.68),
        "rotation": (0.35, 91.57, 12.58),
        "description": "UFC Refresh coconut water"
    },
    "coconut_water": {
        "location": (-151.78, 262.27, -647.68),
        "rotation": (0.35, 91.57, 12.58),
        "description": "Coconut water section"
    },
    "atm_machine": {
        "location": (298.48, 271.14, 380.75),
        "rotation": (0.04, -90.23, -8.74),
        "description": "ATM machine"
    },
    "atm": {
        "location": (298.48, 271.14, 380.75),
        "rotation": (0.04, -90.23, -8.74),
        "description": "ATM machine"
    },
    "ibon_machine": {
        "location": (357.39, 270.87, 28.77),
        "rotation": (0.05, -90.52, -5.34),
        "description": "iBon machine"
    },
    "ibon": {
        "location": (357.39, 270.87, 28.77),
        "rotation": (0.05, -90.52, -5.34),
        "description": "iBon machine"
    },
    "cashier": {
        "location": (328.39, 268.79, -492.29),
        "rotation": (0.43, -84.74, 4.67),
        "description": "Cashier counter"
    },
    "checkout": {
        "location": (328.39, 268.79, -492.29),
        "rotation": (0.43, -84.74, 4.67),
        "description": "Checkout counter"
    },
    "olive_oil": {
        "location": (-119.81, 148.37, -450.42),
        "rotation": (-0.04, 89.20, 2.48),
        "description": "Olive oil section"
    },
    "snacks": {
        "location": (202.81, 153.37, -57.66),
        "rotation": (-2.75, 0.71, 0.03),
        "description": "Snacks section"
    },
    "beverages": {
        "location": (-151.78, 262.27, -647.68),
        "rotation": (0.35, 91.57, 12.58),
        "description": "Beverages section"
    },
    "drinks": {
        "location": (-151.78, 262.27, -647.68),
        "rotation": (0.35, 91.57, 12.58),
        "description": "Drinks section"
    },
}


class CameraNavigation:
    """Handles smooth camera navigation to predefined store locations"""

    def __init__(self, camera_path: str = "/World/Camera"):
        self._camera_path = camera_path
        self._animation_running = False
        self._positions = STORE_POSITIONS.copy()
        self._on_arrival_callback: Optional[Callable[[str], None]] = None

        carb.log_info(f"[CameraNavigation] Initialized with camera: {camera_path}")
        carb.log_info(f"[CameraNavigation] Available locations: {list(self._positions.keys())}")

    def set_on_arrival_callback(self, callback: Callable[[str], None]):
        """Set callback to be called when camera arrives at destination"""
        self._on_arrival_callback = callback

    def add_position(self, name: str, location: Tuple[float, float, float],
                     rotation: Tuple[float, float, float], description: str = ""):
        """Add a new position to the navigation system"""
        self._positions[name.lower()] = {
            "location": location,
            "rotation": rotation,
            "description": description
        }
        carb.log_info(f"[CameraNavigation] Added position: {name}")

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all available positions"""
        return self._positions.copy()

    def find_position(self, name: str) -> Optional[str]:
        """Find a position by name (fuzzy matching)"""
        name_lower = name.lower().strip()

        # Exact match
        if name_lower in self._positions:
            return name_lower

        # Partial match
        for key in self._positions:
            if name_lower in key or key in name_lower:
                return key

        # Word match
        for key in self._positions:
            key_words = key.replace("_", " ").split()
            name_words = name_lower.replace("_", " ").split()
            if any(w in key_words for w in name_words):
                return key

        return None

    def _get_camera_and_ops(self):
        """Get camera prim and transform operations"""
        try:
            import omni.usd
            from pxr import UsdGeom

            stage = omni.usd.get_context().get_stage()
            if not stage:
                carb.log_error("[CameraNavigation] No stage available")
                return None, None, None

            camera = stage.GetPrimAtPath(self._camera_path)
            if not camera or not camera.IsValid():
                carb.log_error(f"[CameraNavigation] Camera not found at {self._camera_path}")
                return None, None, None

            xformable = UsdGeom.Xformable(camera)

            translate_op = None
            rotate_op = None

            for op in xformable.GetOrderedXformOps():
                op_name = op.GetOpName()
                if op_name == "xformOp:translate":
                    translate_op = op
                elif "rotate" in op_name.lower():
                    rotate_op = op

            return xformable, translate_op, rotate_op

        except Exception as e:
            carb.log_error(f"[CameraNavigation] Error getting camera: {e}")
            return None, None, None

    def _disable_action_graph(self):
        """Disable any action graph that might interfere with camera control"""
        try:
            import omni.graph.core as og

            # Common action graph paths
            graph_paths = [
                "/World/PrimClickCamera",
                "/World/ActionGraph",
                "/World/CameraController"
            ]

            for path in graph_paths:
                try:
                    graph = og.get_graph_by_path(path)
                    if graph and graph.is_valid():
                        graph.set_disabled(True)
                        carb.log_info(f"[CameraNavigation] Disabled action graph: {path}")
                except:
                    pass

        except ImportError:
            carb.log_warn("[CameraNavigation] omni.graph.core not available")
        except Exception as e:
            carb.log_warn(f"[CameraNavigation] Could not disable action graph: {e}")

    def get_current_position(self) -> Optional[Dict[str, Tuple[float, float, float]]]:
        """Get current camera position and rotation"""
        _, translate_op, rotate_op = self._get_camera_and_ops()

        if not translate_op or not rotate_op:
            return None

        try:
            pos = translate_op.Get()
            rot = rotate_op.Get()

            return {
                "location": (float(pos[0]), float(pos[1]), float(pos[2])),
                "rotation": (float(rot[0]), float(rot[1]), float(rot[2]))
            }
        except Exception as e:
            carb.log_error(f"[CameraNavigation] Error getting position: {e}")
            return None

    async def navigate_to(
        self,
        destination: str,
        speed: float = 1.0,
        instant: bool = False
    ) -> bool:
        """
        Navigate camera to a named destination.

        Args:
            destination: Name of the destination (e.g., "pringles", "coffee")
            speed: Animation speed multiplier (default 1.0)
            instant: If True, teleport instantly without animation

        Returns:
            True if navigation started successfully, False otherwise
        """
        matched = self.find_position(destination)

        if not matched:
            carb.log_warn(f"[CameraNavigation] Unknown destination: {destination}")
            carb.log_info(f"[CameraNavigation] Available: {list(self._positions.keys())}")
            return False

        # Stop any running animation
        self._animation_running = False
        await asyncio.sleep(0.05)  # Brief pause to let previous animation stop

        # Disable action graphs
        self._disable_action_graph()

        # Get camera operations
        _, translate_op, rotate_op = self._get_camera_and_ops()

        if not translate_op or not rotate_op:
            carb.log_error("[CameraNavigation] Could not get camera transform ops")
            return False

        target = self._positions[matched]
        tx, ty, tz = target["location"]
        rx, ry, rz = target["rotation"]

        if instant:
            # Instant teleport
            try:
                from pxr import Gf
                translate_op.Set(Gf.Vec3d(tx, ty, tz))
                rotate_op.Set(Gf.Vec3f(rx, ry, rz))
                carb.log_info(f"[CameraNavigation] Teleported to: {matched}")

                if self._on_arrival_callback:
                    self._on_arrival_callback(matched)

                return True
            except Exception as e:
                carb.log_error(f"[CameraNavigation] Teleport failed: {e}")
                return False

        # Animated movement
        try:
            from pxr import Gf

            current_pos = translate_op.Get()
            current_rot = rotate_op.Get()

            # Calculate distance and frames
            dist = math.sqrt(
                (tx - current_pos[0])**2 +
                (ty - current_pos[1])**2 +
                (tz - current_pos[2])**2
            )

            # More frames for longer distances, adjusted by speed
            frames = max(60, min(180, int(dist / 4.0 / speed)))

            carb.log_info(f"[CameraNavigation] Navigating to {matched} ({frames} frames)")

            self._animation_running = True

            for i in range(frames + 1):
                if not self._animation_running:
                    carb.log_info("[CameraNavigation] Animation stopped")
                    return False

                # Ease-out exponential for smooth deceleration
                t = i / frames
                t = 1.0 - math.pow(2.0, -10.0 * t) if t < 1.0 else 1.0

                # Interpolate position
                new_pos = Gf.Vec3d(
                    current_pos[0] + (tx - current_pos[0]) * t,
                    current_pos[1] + (ty - current_pos[1]) * t,
                    current_pos[2] + (tz - current_pos[2]) * t,
                )
                translate_op.Set(new_pos)

                # Interpolate rotation
                new_rot = Gf.Vec3f(
                    current_rot[0] + (rx - current_rot[0]) * t,
                    current_rot[1] + (ry - current_rot[1]) * t,
                    current_rot[2] + (rz - current_rot[2]) * t,
                )
                rotate_op.Set(new_rot)

                await asyncio.sleep(1/60)  # ~60 FPS

            # Ensure final position is exact
            translate_op.Set(Gf.Vec3d(tx, ty, tz))
            rotate_op.Set(Gf.Vec3f(rx, ry, rz))

            self._animation_running = False
            carb.log_info(f"[CameraNavigation] Arrived at: {matched}")

            if self._on_arrival_callback:
                self._on_arrival_callback(matched)

            return True

        except Exception as e:
            carb.log_error(f"[CameraNavigation] Animation failed: {e}")
            import traceback
            carb.log_error(f"[CameraNavigation] Traceback: {traceback.format_exc()}")
            self._animation_running = False
            return False

    def stop(self):
        """Stop any running camera animation"""
        self._animation_running = False
        carb.log_info("[CameraNavigation] Animation stopped")

    def is_animating(self) -> bool:
        """Check if camera is currently animating"""
        return self._animation_running


# Singleton instance
_camera_navigation: Optional[CameraNavigation] = None


def get_camera_navigation(camera_path: str = "/World/Camera") -> CameraNavigation:
    """Get or create camera navigation instance"""
    global _camera_navigation
    if _camera_navigation is None:
        _camera_navigation = CameraNavigation(camera_path)
    return _camera_navigation
