# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

import asyncio
import json
import math
import os
from typing import Dict, Any, List, Optional, Tuple, Callable

import carb

# JSON file to persist user-registered camera positions (sibling of this .py file)
NAV_PRESETS_FILE = os.path.join(os.path.dirname(__file__), "nav_presets.json")

# JSON file to persist waypoint routes (sibling of this .py file)
NAV_ROUTES_FILE = os.path.join(os.path.dirname(__file__), "nav_routes.json")

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

        # Waypoint routes: keyed by destination name, each is a list of waypoints
        # that the camera visits in order before reaching the final destination.
        # Format: { "destination_key": { "waypoints": [{"location":[x,y,z], "rotation":[rx,ry,rz]}, ...] } }
        self._routes: Dict[str, Dict[str, Any]] = {}

        # Load custom positions and routes from disk and merge
        self._load_custom_positions()
        self._load_routes()
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

    # ===== ROUTE MANAGEMENT =====

    def _load_routes(self) -> None:
        """Load waypoint routes from nav_routes.json."""
        if not os.path.exists(NAV_ROUTES_FILE):
            return
        try:
            with open(NAV_ROUTES_FILE, "r") as f:
                data: Dict[str, Any] = json.load(f)
            self._routes = {k.lower(): v for k, v in data.items()}
            carb.log_info(f"[CameraNavigation] Loaded {len(self._routes)} routes from disk")
        except Exception as e:
            carb.log_error(f"[CameraNavigation] Failed to load nav_routes.json: {e}")

    def _save_routes_to_disk(self) -> bool:
        """Persist _routes to nav_routes.json."""
        try:
            with open(NAV_ROUTES_FILE, "w") as f:
                json.dump(self._routes, f, indent=2)
            return True
        except Exception as e:
            carb.log_error(f"[CameraNavigation] Failed to write nav_routes.json: {e}")
            return False

    def save_route(
        self,
        destination: str,
        waypoints: List[Dict[str, Any]],
        start: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register a waypoint route for a destination.

        Args:
            destination: The target position name (must exist in _positions).
            waypoints: Ordered list of intermediate points the camera visits
                       before arriving at the destination.  Each element:
                       {"location": [x,y,z], "rotation": [rx,ry,rz]}
            start: Optional starting pose.  If provided the camera will
                   move here before beginning the smooth
                   animation through the waypoints.  Same format as a
                   waypoint: {"location": [x,y,z], "rotation": [rx,ry,rz]}.
                   If omitted the camera lerps from its current position.
        """
        key = destination.lower().strip().replace(" ", "_")
        route_data: Dict[str, Any] = {"waypoints": waypoints}
        if start:
            route_data["start"] = start
        self._routes[key] = route_data
        saved = self._save_routes_to_disk()
        carb.log_info(
            f"[CameraNavigation] Saved route for '{key}' "
            f"with {len(waypoints)} waypoint(s)"
            f"{' + start position' if start else ''}"
        )
        return saved

    def delete_route(self, destination: str) -> bool:
        """Remove the waypoint route for a destination."""
        key = destination.lower().strip().replace(" ", "_")
        if key not in self._routes:
            return False
        del self._routes[key]
        return self._save_routes_to_disk()

    def get_route(self, destination: str) -> Optional[List[Dict[str, Any]]]:
        """Return the waypoint list for a destination, or None."""
        key = destination.lower().strip().replace(" ", "_")
        route = self._routes.get(key)
        return route["waypoints"] if route else None

    def get_route_start(self, destination: str) -> Optional[Dict[str, Any]]:
        """Return the start pose for a route, or None if not set."""
        key = destination.lower().strip().replace(" ", "_")
        route = self._routes.get(key)
        if route:
            return route.get("start")
        return None

    def find_route(self, name: str) -> Optional[str]:
        """Find a route by name (fuzzy matching), same logic as find_position."""
        name_lower = name.lower().strip()
        if name_lower in self._routes:
            return name_lower
        for key in self._routes:
            if name_lower in key or key in name_lower:
                return key
        for key in self._routes:
            key_words = key.replace("_", " ").split()
            name_words = name_lower.replace("_", " ").split()
            if any(w in key_words for w in name_words):
                return key
        return None

    def get_all_routes(self) -> Dict[str, Any]:
        """Return all registered routes."""
        return self._routes.copy()

    # ===== END ROUTE MANAGEMENT =====

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
        destination: str|Dict,
        speed: float = 1.0,
        instant: bool = False
    ) -> bool:
        """
        Navigate camera to a named destination.

        Args:
            destination: Name of the destination (e.g., "pringles", "coffee") or a dict with explicit location/rotation:
            speed: Animation speed multiplier (default 1.0)
            instant: If True, teleport instantly without animation

        Returns:
            True if navigation started successfully, False otherwise
        """
         # -------- Navigation to specified location & rotation --------
        if isinstance(destination, dict):
            tx, ty, tz = destination.get("location", (0.0, 0.0, 0.0))
            rx, ry, rz = destination.get("rotation", (0.0, 0.0, 0.0))
            destination_key = f"custom_{tx:.1f}_{ty:.1f}_{tz:.1f}"
            self.add_position(destination_key, (tx, ty, tz), (rx, ry, rz), description="Custom Target")
            destination = destination_key

            # Instant teleport
            try:
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

                from pxr import Gf
                translate_op.Set(Gf.Vec3d(tx, ty, tz))
                rotate_op.Set(Gf.Vec3f(rx, ry, rz))
                carb.log_info(f"[CameraNavigation] Teleported to: {destination_key}")

                if self._on_arrival_callback:
                    self._on_arrival_callback(destination_key)

                return True
            except Exception as e:
                carb.log_error(f"[CameraNavigation] Teleport failed: {e}")
                return False


        # -------- Navigation to named destination --------
        matched_position = self.find_position(destination)

        # Check if this destination is a route-only target (no matching position)
        matched_route = self.find_route(destination)
        is_route_only = matched_position is None and matched_route is not None

        if not matched_position and not is_route_only:
            carb.log_warn(f"[CameraNavigation] Unknown destination: {destination}")
            carb.log_info(f"[CameraNavigation] Available positions: {list(self._positions.keys())}")
            carb.log_info(f"[CameraNavigation] Available routes: {list(self._routes.keys())}")
            return False

        # For route-only destinations, use the route key for lookups
        nav_key = matched_position if matched_position else matched_route

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

        if matched_position:
            target = self._positions[matched_position]
            tx, ty, tz = target["location"]
            rx, ry, rz = target["rotation"]
        else:
            # Route-only: use the last waypoint of the route as the final target
            route_wps = self.get_route(nav_key) or []
            if not route_wps:
                carb.log_error(f"[CameraNavigation] Route '{nav_key}' has no waypoints")
                return False
            last_wp = route_wps[-1]
            tx, ty, tz = last_wp["location"]
            rx, ry, rz = last_wp["rotation"]

        if instant:
            # Instant teleport
            try:
                from pxr import Gf
                translate_op.Set(Gf.Vec3d(tx, ty, tz))
                rotate_op.Set(Gf.Vec3f(rx, ry, rz))
                carb.log_info(f"[CameraNavigation] Teleported to: {matched_position}")

                if self._on_arrival_callback:
                    self._on_arrival_callback(matched_position)

                return True
            except Exception as e:
                carb.log_error(f"[CameraNavigation] Teleport failed: {e}")
                return False

        # Build the list of poses to visit: route start (if any) + waypoints + final target
        route_waypoints = self.get_route(nav_key) or []
        route_start = self.get_route_start(nav_key)

        poses = []
        # If the route defines a start position, prepend it so the camera
        # smoothly navigates there first before following the waypoints.
        if route_start:
            poses.append({
                "location": list(route_start["location"]),
                "rotation": list(route_start["rotation"]),
            })

        poses.extend(
            {"location": list(wp["location"]), "rotation": list(wp["rotation"])}
            for wp in route_waypoints
        )

        if is_route_only:
            # For route-only destinations the last waypoint IS the destination,
            # so don't duplicate it.  If the route has a start or intermediate
            # waypoints we already have the full path.
            if len(poses) == 0:
                # Edge case: route with no waypoints and no start — nothing to animate
                carb.log_error(f"[CameraNavigation] Route '{nav_key}' is empty")
                return False
        else:
            # Append the position as final destination
            poses.append({"location": [tx, ty, tz], "rotation": [rx, ry, rz]})

        carb.log_info(
            f"[CameraNavigation] Navigating to {nav_key} via "
            f"{len(poses) - 1} waypoint(s)"
            f"{' (route-only)' if is_route_only else ''}"
            f"{' (with route start)' if route_start else ''}"
        )

        # Animated movement through all poses
        try:
            self._animation_running = True

            # Catmull-Rom spline interpolation
            # Add current position as the first pose to ensure smooth departure from the current location
            current_pos = translate_op.Get()
            current_rot = rotate_op.Get()
            poses.insert(0, {"location": list(current_pos), "rotation": list(current_rot)})
            segments = []
            for i in range(len(poses) - 1):
                p0 = poses[i - 1] if i - 1 >= 0 else poses[i]
                p1 = poses[i]
                p2 = poses[i + 1]
                p3 = poses[i + 2] if i + 2 < len(poses) else poses[i + 1]
                segments.append([p0, p1, p2, p3])
            
            for _, segment in enumerate(segments):
                ok = await self._animate_segment_catmull_rom(
                    translate_op, rotate_op, segment
                )
                if not ok:
                    return False
            

            self._animation_running = False
            carb.log_info(f"[CameraNavigation] Arrived at: {nav_key}")

            if self._on_arrival_callback:
                self._on_arrival_callback(nav_key)

            return True

        except Exception as e:
            carb.log_error(f"[CameraNavigation] Animation failed: {e}")
            import traceback
            carb.log_error(f"[CameraNavigation] Traceback: {traceback.format_exc()}")
            self._animation_running = False
            return False


    async def _animate_segment_catmull_rom(
        self,
        translate_op,
        rotate_op,
        segment: List[Dict[str, Any]],
    ) -> bool:
        """
        Animate the camera using Catmull-Rom splines for smooth position interpolation,
        and Shortest-Delta Euler interpolation for predictable rotation.
        """
        from pxr import Gf

        p0, p1, p2, p3 = segment
        num_frames = 60

        # --- PREPARE ROTATION DELTAS ---
        current_rot = p1["rotation"]
        target_rot = p2["rotation"]

        # Compute shortest-path rotation deltas (wrap to ±180°)
        def _shortest_delta(current_deg: float, target_deg: float) -> float:
            d = (target_deg - current_deg) % 360.0
            if d > 180.0:
                d -= 360.0
            return d

        drx = _shortest_delta(float(current_rot[0]), float(target_rot[0]))
        dry = _shortest_delta(float(current_rot[1]), float(target_rot[1]))
        drz = _shortest_delta(float(current_rot[2]), float(target_rot[2]))

        for i in range(num_frames):
            if not self._animation_running:
                carb.log_info("[CameraNavigation] Animation stopped")
                return False

            t = i / (num_frames - 1)

            # --- 1. POSITION (Catmull-Rom Curved Path) ---
            new_pos = self._catmull_rom_spline(
                Gf.Vec3d(*p0["location"]),
                Gf.Vec3d(*p1["location"]),
                Gf.Vec3d(*p2["location"]),
                Gf.Vec3d(*p3["location"]),
                t
            )
            translate_op.Set(new_pos)

            # --- 2. ROTATION (Predictable Euler Shortest-Path) ---
            new_rot = Gf.Vec3f(
                float(current_rot[0]) + drx * t,
                float(current_rot[1]) + dry * t,
                float(current_rot[2]) + drz * t,
            )
            rotate_op.Set(new_rot)

            await asyncio.sleep(1 / 60)
        
        # Snap to exact target at the end to prevent micro-drifts
        translate_op.Set(Gf.Vec3d(*p2["location"]))
        rotate_op.Set(Gf.Vec3f(*p2["rotation"]))
        
        return True



    def _catmull_rom_spline(self, p0, p1, p2, p3, t):
        t2 = t * t
        t3 = t2 * t
        return 0.5 * (
            (2.0 * p1) +
            (-p0 + p2) * t +
            (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 +
            (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
        )

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
