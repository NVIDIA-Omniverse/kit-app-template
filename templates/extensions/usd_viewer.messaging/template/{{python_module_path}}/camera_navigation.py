# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import json
import math
import os
from typing import Dict, Any, Optional, Tuple, Callable

import carb

# JSON file to persist user-registered camera positions (sibling of this .py file)
NAV_PRESETS_FILE = os.path.join(os.path.dirname(__file__), "nav_presets.json")

# Directory that holds one JSON file per store key (e.g. pipc.json, 711.json)
STORE_PRESETS_DIR = os.path.join(os.path.dirname(__file__), "store_presets")


class CameraNavigation:
    """Handles smooth camera navigation to predefined store locations"""

    def __init__(self, camera_path: str = "/World/Camera"):
        self._camera_path = camera_path
        self._animation_running = False
        self._on_arrival_callback: Optional[Callable[[str], None]] = None

        # Built-in positions loaded from the active store's JSON preset file
        self._builtin_positions: Dict[str, Dict[str, Any]] = {}
        # User-registered (custom) positions — persisted to nav_presets.json
        self._custom_positions: Dict[str, Dict[str, Any]] = {}
        # Active store key (e.g. "pipc", "711") — set via set_active_store()
        self._active_store: Optional[str] = None

        # Merged view used for navigation
        self._positions: Dict[str, Dict[str, Any]] = {}

        # Load custom positions from disk and merge
        self._load_custom_positions()
        self._rebuild_positions()

        carb.log_info(f"[CameraNavigation] Initialized with camera: {camera_path}")
        carb.log_info(f"[CameraNavigation] Available locations: {list(self._positions.keys())}")

    # ===== STORE PRESET MANAGEMENT =====

    def set_active_store(self, store_key: str) -> bool:
        """
        Load built-in positions for the given store key from store_presets/<key>.json.
        Resets builtin positions; custom positions are preserved.
        Returns True if the preset file was found and loaded.
        """
        key = store_key.lower().strip()
        preset_file = os.path.join(STORE_PRESETS_DIR, f"{key}.json")

        self._builtin_positions = {}
        if os.path.exists(preset_file):
            try:
                with open(preset_file, "r") as f:
                    data = json.load(f)
                self._builtin_positions = {k.lower(): v for k, v in data.items()}
                carb.log_info(
                    f"[CameraNavigation] Loaded {len(self._builtin_positions)} "
                    f"built-in positions for store '{key}'"
                )
            except Exception as e:
                carb.log_error(f"[CameraNavigation] Failed to load preset for '{key}': {e}")
                self._active_store = key
                self._rebuild_positions()
                return False
        else:
            carb.log_info(
                f"[CameraNavigation] No preset file for store '{key}' — starting with empty built-ins"
            )

        self._active_store = key
        self._rebuild_positions()
        carb.log_info(f"[CameraNavigation] Active store set to '{key}'. "
                      f"Total positions: {len(self._positions)}")
        return True

    def promote_to_builtin(self, name: str) -> bool:
        """
        Promote a single custom position to the built-in preset for the active store.
        Removes it from custom positions so it appears only in Built-in Locations.
        Saves both the store preset and custom positions file to disk.
        """
        key = name.lower().strip().replace(" ", "_")
        if key not in self._custom_positions:
            carb.log_warn(f"[CameraNavigation] Cannot promote unknown custom position: '{key}'")
            return False
        if not self._active_store:
            carb.log_warn("[CameraNavigation] No active store — cannot promote to built-in")
            return False
        self._builtin_positions[key] = self._custom_positions.pop(key)
        self._rebuild_positions()
        saved = self._save_store_presets() and self._save_custom_to_disk()
        carb.log_info(f"[CameraNavigation] Promoted '{key}' to built-in for store '{self._active_store}'")
        return saved

    def save_all_custom_as_builtin(self) -> bool:
        """
        Promote ALL current custom positions to the built-in preset for the active store.
        Removes them from custom positions so they appear only in Built-in Locations.
        Saves both the store preset and custom positions file to disk.
        """
        if not self._active_store:
            carb.log_warn("[CameraNavigation] No active store — cannot promote to built-in")
            return False
        count = len(self._custom_positions)
        self._builtin_positions.update(self._custom_positions)
        self._custom_positions.clear()
        self._rebuild_positions()
        saved = self._save_store_presets() and self._save_custom_to_disk()
        carb.log_info(
            f"[CameraNavigation] Saved {count} custom positions "
            f"as built-ins for store '{self._active_store}'"
        )
        return saved

    def _save_store_presets(self) -> bool:
        """Persist the current built-in positions to store_presets/<active_store>.json."""
        if not self._active_store:
            carb.log_warn("[CameraNavigation] _save_store_presets: no active store")
            return False
        os.makedirs(STORE_PRESETS_DIR, exist_ok=True)
        preset_file = os.path.join(STORE_PRESETS_DIR, f"{self._active_store}.json")
        try:
            with open(preset_file, "w") as f:
                json.dump(self._builtin_positions, f, indent=2)
            carb.log_info(
                f"[CameraNavigation] Saved {len(self._builtin_positions)} built-ins "
                f"for store '{self._active_store}' → {preset_file}"
            )
            return True
        except Exception as e:
            carb.log_error(f"[CameraNavigation] Failed to save store presets: {e}")
            return False

    def _rebuild_positions(self) -> None:
        """Merge builtin + custom into _positions (custom wins on conflict)."""
        self._positions = {**self._builtin_positions, **self._custom_positions}

    # ===== JSON PERSISTENCE (custom positions) =====

    def _load_custom_positions(self) -> None:
        """Load user-registered positions from nav_presets.json."""
        if not os.path.exists(NAV_PRESETS_FILE):
            return
        try:
            with open(NAV_PRESETS_FILE, "r") as f:
                data: Dict[str, Any] = json.load(f)
            for name, pos_data in data.items():
                key = name.lower()
                self._custom_positions[key] = pos_data
            carb.log_info(f"[CameraNavigation] Loaded {len(data)} custom positions from disk")
        except Exception as e:
            carb.log_error(f"[CameraNavigation] Failed to load nav_presets.json: {e}")

    def _save_custom_to_disk(self) -> bool:
        """Persist _custom_positions to nav_presets.json."""
        try:
            with open(NAV_PRESETS_FILE, "w") as f:
                json.dump(self._custom_positions, f, indent=2)
            return True
        except Exception as e:
            carb.log_error(f"[CameraNavigation] Failed to write nav_presets.json: {e}")
            return False

    def save_position(
        self,
        name: str,
        location: Tuple[float, float, float],
        rotation: Tuple[float, float, float],
        description: str = ""
    ) -> bool:
        """Register a new custom camera position and persist it to disk."""
        key = name.lower().strip().replace(" ", "_")
        pos_data = {
            "location": list(location),
            "rotation": list(rotation),
            "description": description or name,
        }
        self._custom_positions[key] = pos_data
        self._rebuild_positions()
        saved = self._save_custom_to_disk()
        carb.log_info(f"[CameraNavigation] Registered position '{key}': {pos_data}")
        return saved

    def delete_position(self, name: str) -> bool:
        """Remove a user-registered position and update the JSON file."""
        key = name.lower()
        if key not in self._custom_positions:
            carb.log_warn(f"[CameraNavigation] Cannot delete built-in or unknown position: {key}")
            return False
        del self._custom_positions[key]
        self._rebuild_positions()
        return self._save_custom_to_disk()

    def clear_custom_positions(self) -> bool:
        """Remove all user-registered positions, restore only built-ins."""
        self._custom_positions.clear()
        self._rebuild_positions()
        return self._save_custom_to_disk()

    def get_all_positions_with_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Return all positions annotated with is_custom and is_builtin flags."""
        result: Dict[str, Dict[str, Any]] = {}
        for key, data in self._positions.items():
            result[key] = {
                **data,
                "is_custom": key in self._custom_positions,
                "is_builtin": key in self._builtin_positions,
            }
        return result

    # ===== END JSON PERSISTENCE =====

    def set_on_arrival_callback(self, callback: Callable[[str], None]):
        """Set callback to be called when camera arrives at destination"""
        self._on_arrival_callback = callback

    def add_position(self, name: str, location: Tuple[float, float, float],
                     rotation: Tuple[float, float, float], description: str = ""):
        """Add a new position to the navigation system (in-memory only)."""
        self._positions[name.lower()] = {
            "location": location,
            "rotation": rotation,
            "description": description
        }
        carb.log_info(f"[CameraNavigation] Added position: {name}")

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all available positions"""
        return self._positions.copy()

    def get_active_store(self) -> Optional[str]:
        """Return the currently active store key, or None if not set."""
        return self._active_store

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
        """
        Get camera prim and transform operations.
        Prefers the active viewport camera over the configured path.
        Ensures the camera has clean xformOp:translate + xformOp:rotateXYZ ops.
        If the camera uses a matrix op (xformOp:transform), or any required op is
        missing, the entire xform stack is rebuilt from the current world transform
        to avoid double-transform compounding and zero-rotation seeding bugs.
        """
        try:
            import math
            import omni.usd
            from pxr import UsdGeom, Gf

            stage = omni.usd.get_context().get_stage()
            if not stage:
                carb.log_error("[CameraNavigation] No stage available")
                return None, None, None

            # Prefer the camera the viewport is actually showing
            camera = None
            try:
                from omni.kit.viewport.utility import get_active_viewport_camera_path
                active_path = get_active_viewport_camera_path()
                if active_path:
                    candidate = stage.GetPrimAtPath(active_path)
                    if candidate and candidate.IsValid():
                        camera = candidate
                        carb.log_info(f"[CameraNavigation] Using active viewport camera: {active_path}")
            except Exception as e:
                carb.log_warn(f"[CameraNavigation] Could not get viewport camera path: {e}")

            # Fall back to the configured path
            if not camera or not camera.IsValid():
                camera = stage.GetPrimAtPath(self._camera_path)
                if camera and camera.IsValid():
                    carb.log_info(f"[CameraNavigation] Using configured camera: {self._camera_path}")

            if not camera or not camera.IsValid():
                carb.log_error(f"[CameraNavigation] Camera not found at {self._camera_path}")
                return None, None, None

            xformable = UsdGeom.Xformable(camera)

            translate_op = None
            rotate_op = None
            has_matrix_op = False

            for op in xformable.GetOrderedXformOps():
                op_name = op.GetOpName()
                if op_name == "xformOp:translate":
                    translate_op = op
                elif "rotate" in op_name.lower():
                    rotate_op = op
                elif "transform" in op_name.lower():
                    has_matrix_op = True

            # If the camera uses a matrix op OR either required op is missing,
            # rebuild the xform stack from the current world transform so that:
            #   1. No double-transform (matrix op + translate/rotate compounding)
            #   2. rotateXYZ is seeded with the actual camera rotation, not zeros
            if has_matrix_op or translate_op is None or rotate_op is None:
                carb.log_info("[CameraNavigation] Rebuilding xform ops from world transform")

                # Capture world transform BEFORE clearing any ops
                world_xform = xformable.ComputeLocalToWorldTransform(0)
                t = world_xform.ExtractTranslation()

                # Decompose rotation matrix → Euler XYZ degrees
                m = world_xform.ExtractRotationMatrix()
                # USD uses row-vector convention: M = Rx * Ry * Rz
                # so sy = |cos(ry)| from the first row
                sy = math.sqrt(m[0][0] ** 2 + m[0][1] ** 2)
                if sy > 1e-6:
                    rx = math.degrees(math.atan2(m[1][2], m[2][2]))
                    ry = math.degrees(math.atan2(-m[0][2], sy))
                    rz = math.degrees(math.atan2(m[0][1], m[0][0]))
                else:
                    rx = math.degrees(math.atan2(-m[2][1], m[1][1]))
                    ry = math.degrees(math.atan2(-m[0][2], sy))
                    rz = 0.0

                # Wipe all existing ops to prevent compounding
                xformable.SetXformOpOrder([])

                # Re-add clean translate + rotateXYZ seeded with actual world values
                translate_op = xformable.AddTranslateOp()
                translate_op.Set(Gf.Vec3d(t[0], t[1], t[2]))

                rotate_op = xformable.AddRotateXYZOp()
                rotate_op.Set(Gf.Vec3f(rx, ry, rz))

                carb.log_info(
                    f"[CameraNavigation] Rebuilt ops: "
                    f"t=({t[0]:.1f},{t[1]:.1f},{t[2]:.1f}) "
                    f"r=({rx:.2f},{ry:.2f},{rz:.2f})"
                )

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
