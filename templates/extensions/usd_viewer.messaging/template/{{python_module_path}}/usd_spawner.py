"""
UsdSpawner — handles click-to-spawn USD assets from the browser chatbot.

Message flow:
  Browser sends  → "spawnUsdRequest"  { screen_x, screen_y, usd_path, prim_name }
  Kit replies    → "spawnUsdResponse" { result, prim_path, position, error }

Screen coordinates are normalized [0..1], origin at top-left of the viewport.
A camera frustum ray is cast and intersected with the Y=0 ground plane to
obtain the 3D world position where the asset will be placed.
"""

import json
import os
import re
import time

import carb
import carb.events
import omni.kit.app
import omni.kit.livestream.messaging as messaging
import omni.usd
from carb.eventdispatcher import get_eventdispatcher
from pxr import Gf, Usd, UsdGeom


# ---------------------------------------------------------------------------
# Hardcoded asset library — keys are canonical names the agent can reference.
# Paths should be absolute, relative to the Kit app root, or Omniverse URLs.
# The agent backend resolves natural-language names ("recycle bin") to a key
# in this dict and sends it via metadata.usd_path.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Config — load paths from usd_config.json (sits next to this file).
# Edit usd_config.json to point at the correct USD directory for your machine.
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "usd_config.json")
try:
    with open(_CONFIG_PATH) as _f:
        _cfg = json.load(_f)
except Exception as _cfg_err:
    import carb as _carb_early
    _carb_early.log_warn(f"[UsdSpawner] Could not load usd_config.json: {_cfg_err} — using built-in defaults")
    _cfg = {}

_USD_BASE        = _cfg.get("usd_base",        "/workspace/shashika-ws/github-ws/omniverse-vs-agent-backend/usd")
_INVENTORY_FILE  = _cfg.get("inventory_file",  "/workspace/shashika-ws/github-ws/omniverse-vs-agent-backend/asset_list_shop_already.json")
_STAGE_PRIMS_FILE = _cfg.get("stage_prims_file", "/workspace/shashika-ws/github-ws/omniverse-vs-agent-backend/stage_prims.json")

ASSET_LIBRARY: dict[str, str] = {k: f"{_USD_BASE}/{f}" for k, f in [
    # Tea & Milk Tea
    ("lipton_milktea",           "Lipton_Milktea.usdz"),
    ("lipton_iced_tea",          "Lipton_Fruit_Iced_Tea.usdz"),
    ("nittotea_milktea",         "NittoTea_Royal_Milktea.usdz"),
    ("freshdel_strawberry_tea",  "FreshDelight_Strawberry_MilkTea.usdz"),
    ("freshdel_coco_tea",        "FreshDelight_Coco_MilkTea.usdz"),
    ("dezheng_oolong_tea",       "De_Zheng_Roasted_Oolong_Milk_Tea.usdz"),
    ("afternoon_cream_milktea",  "AfternoonTeaTime_Heavy_Cream_Milktea.usdz"),
    ("afternoon_jasmine_tea",    "AfternoonTeaTime_Heavy_Cream_Jasmine_Milktea.usdz"),
    ("real_leaf_green_tea",      "Real_Leaf_Green_Tea_Gyokuro.usdz"),
    ("real_leaf_green_tea_pet",  "Real_Leaf_Green_Tea_Gyokuro_PET580.usdz"),
    ("chai_li_won_green_tea",    "Chai_Li_Won_Taiwanese_Green_Tea_PET975.usdz"),
    ("maixiang_black_tea",       "MaiXiang_Black_Tea_TP375.usdz"),
    ("yuancui_black_tea",        "yuancui_black_tea.usdz"),
    ("jasmine_guava_green_tea",  "JasmineTeaGarden_Guava_Lemon_Greentea.usdz"),
    ("jasmine_apple_black_tea",  "JasmineTeaGarden_Apple_Black_tea.usdz"),
    ("honey_apple_orange_tea",   "Honey_Apple_Orange_GreyTea.usdz"),
    ("green_drink",              "green_drink.usdz"),
    # Soy Milk & Oat
    ("uni_soymilk",              "Uni_Sunshine_SoyMilk.usdz"),
    ("uni_brownrice_milk",       "Uni_Sunshine_BrownRiceMilk.usdz"),
    ("kuangchuan_black_soymilk", "KuangChuan_Sugarfree_BlackSoyMilk.usdz"),
    ("kuangchuan_soymilk",       "KuangChuan_Milk_SoyMilk.usdz"),
    ("fuhang_soymilk",           "FuHang_SoyMilk_Unsweetened.usdz"),
    ("kuangchuan_soymilk_357",   "Kuang_Chuan_Unsweetened_SoyMilk_357ml.usdz"),
    ("quaker_soymilk_oat",       "Quaker_SoyMilkOatdrink.usdz"),
    ("agv_milk_oat",             "A_G_V_MilkOatdrink.usdz"),
    ("agv_honey_oat",            "A_G_V_HoneyOatdrink.usdz"),
    ("agv_milk_peanut",          "AGV_Milk_Peanut_Can340.usdz"),
    ("g_nut_milk",               "g_nut_milk.usdz"),
    # Juice & Yogurt
    ("jinjin_asparagus_juice",   "JinJin_Asparagus_Juice.usdz"),
    ("guava_mixed_juice",        "Fresh_Picked_Orchard_Guava_Mixed_Juice.usdz"),
    ("pomi_fruit_veg_juice",     "Pomi_Oneday_Fruit_Vegetable_Juice.usdz"),
    ("ab_strawberry_yogurt",     "ab_strawberry_yogurt.usdz"),
    # Sports & Water
    ("pocari_sweat",             "A_Pocari_Sweat_PET580.usdz"),
    ("supersup_sports_drink",    "A_SuperSup_Sports_Drink_PET590.usdz"),
    ("heysong_fin_drink",        "A_HeySong_FIN_Supply_Drink_PET580.usdz"),
    ("staycool_charcoal_water",  "StayCool_Alkaline_Bamboo_Charcoal_Water_PET700.usdz"),
    ("uni_h2o_water",            "UNI_H2O_Pure_Water_PET600.usdz"),
    ("ufc_coconut_water",        "UFC_Refresh_CoconutWater.usdz"),
    # Snacks
    ("pringles_cheese",          "Pringles_Cheese_Flavor_Potato_Chips.usdz"),
    ("pringles_bbq",             "Pringles_Charcoal_BBQ_Flavor_Large.usdz"),
    ("pringles_pizza",           "Pringles_Pizza_Flavor_Large.usdz"),
    ("pringles_lobster",         "Pringles_Spicy_Stir-Fried_Garlic_Lobster_Flavor_Potato_Chips.usdz"),
    ("cheetos_double_cheese",    "Cheetos_Double_Cheese_Flavor_Corn_Stick.usdz"),
    ("guai_guai_coconut",        "Guai_Guai_Coconut_Flavor_Large.usdz"),
    # Noodles
    ("uni_minced_meat_noodle",   "Uni_Noodles_Minced_Meat_Flavor_Bowl.usdz"),
    ("uni_braised_beef_noodle",  "Uni_Noodles_Green_Onion_Braised_Beef_Flavor_Bowl.usdz"),
    ("manhan_beef_noodles",      "A_ManHan_Green_Onion_Braised_Beef_Noodles.usdz"),
    ("grab_beef_veg_noodle",     "Grab_Cup_Noodles_Beef_and_Vegetable_Flavor.usdz"),
    ("grab_pork_spinach_noodle", "Grab_Cup_Noodles_Minced_Pork_and_Spinach_Flavor.usdz"),
    ("ramen_do_miso",            "Ramen_Do_Japanese_Miso_Flavor.usdz"),
    ("ramen_do_tonkatsu",        "Ramen_Do_Japanese_Tonkatsu_Flavor.usdz"),
    ("ahq_red_pepper_noodle",    "A_Ah_Q_Cup_Noodles_Red_Pepper_Beef_Flavor.usdz"),
    ("ahq_seafood_noodle",       "Ah_Q_Cup_Noodles_Fresh_Seafood_Flavor.usdz"),
    ("double_bang_satay_noodle", "Double_Bang_Satay_Hotpot_Soup_Noodles.usdz"),
    ("weili_soybean_noodle",     "A_Wei_Li_Fried_Soybean_Paste_Noodles_Bowl.usdz"),
    ("yidu_beef_noodle",         "Yidu_Zan_Aged_Jar_Beef_Noodles.usdz"),
    # Food
    ("royal_deli_braised_egg",   "Royal_Deli_Shian_Farm_Fragrant_Braised_Egg_White_Diced.usdz"),
    ("taiwanese_braised_veg",    "Taiwanese_Braised_Dish_Seasonal_Vegetables.usdz"),
    ("manhan_garlic_sausages",   "ManHan_Mini_Sausages_Garlic_Flavor.usdz"),
    # Props
    ("recycle_bin",              "recycle-bin.usdz"),
    ("shelf",                    "shelf.usdz"),
]}


# ---------------------------------------------------------------------------
# Inventory file — persists spawned prims across extension reloads/restarts.
# Format: { "/World/prim_path": { "asset_key": "...", "asset_name": "...",
#                                 "usd_path": "...", "position": [x,y,z] } }
# ---------------------------------------------------------------------------
INVENTORY_FILE   = _INVENTORY_FILE
STAGE_PRIMS_FILE = _STAGE_PRIMS_FILE

# Brand groups: brand prefix → list of asset keys with that prefix.
# e.g. "pringles" → ["pringles_cheese","pringles_bbq","pringles_pizza","pringles_lobster"]
# Enables "delete all pringles" to match every pringles variant.
_BRAND_GROUPS: dict = {}
for _k in ASSET_LIBRARY:
    _parts = _k.split("_")
    for _n in range(1, len(_parts)):
        _prefix = "_".join(_parts[:_n])
        _BRAND_GROUPS.setdefault(_prefix, []).append(_k)
_BRAND_GROUPS = {k: v for k, v in _BRAND_GROUPS.items() if len(v) > 1}

# Per-asset spawn rotation corrections.
# Some USDZ assets are authored with a non-standard "up" axis and appear
# "fallen" when spawned.  These corrections are composed on top of any
# world-rotation inherited from the replaced prim.
#
# Format: prim_name → (axis_vec3, angle_degrees)
# The rotation is applied as: effective_rot = inherited_rot * correction_rot
#
# How to find the right correction:
#   Inspect the spawned item's bbox.  If X-span >> Y-span the asset is
#   authored X-up → rotate +90° around Z to stand it upright (X→Y).
#   If Y-span >> Z-span but item looks tilted, try ±90° around X or Y.
# Per-asset spawn rotation corrections.
# Each entry is a LIST of (axis_vec3, angle_degrees) applied in order.
# Corrections are composed on top of any world-rotation inherited from the replaced prim.
#
# How to find the right values:
#   1. After a replace, select the spawned prim in the Kit viewport.
#   2. Press R to activate the rotate gizmo.  Spin around Y to fix face direction.
#   3. Read the resulting xformOp:orient quaternion in the Properties panel.
#   4. Convert or just try ±90° / 180° around Y until it faces the shelf correctly.
#
# Correction 1 — stand up:  -90° around Z maps X-axis (long axis) → -Y (vertical).
# Correction 2 — face fix:   rotate around Y to point the front face toward the aisle.
#   Try 0, 90, -90, or 180 degrees.  Change only this value while iterating.
ASSET_SPAWN_ROTATION_CORRECTION: dict[str, list] = {
    "lipton_milktea": [
        ((0, 0, 1), -90),   # Stand up (X→up)
        ((0, 1, 0),  90),   # Face the shelf front — try 0 / 90 / -90 / 180 if wrong
    ],
}

# ---------------------------------------------------------------------------
# Persistent rotation corrections (saved/loaded from JSON)
# ---------------------------------------------------------------------------
# JSON file lives alongside this module so edits survive extension reloads.
# Format: { "prim_name": { "euler_x": 0, "euler_y": 90, "euler_z": -90 } }
# When a key exists here it takes priority over ASSET_SPAWN_ROTATION_CORRECTION.
_ROTATION_CORRECTIONS_PATH = os.path.join(os.path.dirname(__file__), "rotation_corrections.json")


def _load_rotation_corrections() -> dict:
    """Load saved Euler rotation corrections from JSON, return empty dict on failure."""
    try:
        if os.path.exists(_ROTATION_CORRECTIONS_PATH):
            with open(_ROTATION_CORRECTIONS_PATH, "r") as f:
                data = json.load(f)
            carb.log_info(f"[UsdSpawner] Loaded rotation_corrections.json ({len(data)} entries)")
            return data
    except Exception as exc:
        carb.log_warn(f"[UsdSpawner] Could not load rotation_corrections.json: {exc}")
    return {}


def _save_rotation_corrections(corrections: dict) -> None:
    """Persist rotation corrections dict to JSON file."""
    try:
        with open(_ROTATION_CORRECTIONS_PATH, "w") as f:
            json.dump(corrections, f, indent=2)
        carb.log_info(f"[UsdSpawner] Saved rotation_corrections.json ({len(corrections)} entries)")
    except Exception as exc:
        carb.log_warn(f"[UsdSpawner] Could not save rotation_corrections.json: {exc}")


# Reverse map: USD filename stem → asset key.
# e.g. "NittoTea_Royal_Milktea" → "nittotea_milktea"
# Used to scan stage for prims matching a given asset key.
_STEM_TO_KEY: dict = {}
_KEY_TO_STEM: dict = {}
for _k, _fp in ASSET_LIBRARY.items():
    _stem = os.path.splitext(os.path.basename(_fp))[0]
    _STEM_TO_KEY[_stem] = _k
    _STEM_TO_KEY[_stem.replace("-", "_")] = _k
    _KEY_TO_STEM[_k] = _stem


class UsdSpawner:
    """Listens for spawnUsdRequest messages and spawns USD assets on the stage."""

    def __init__(self):
        self._subscriptions = []
        self._spawn_counter: dict[str, int] = {}
        # Tracks prim paths created per asset key so we can delete them later.
        self._spawned_prims: dict[str, list] = {}
        # Persistent per-asset Euler rotation corrections (loaded from JSON).
        # Keys override ASSET_SPAWN_ROTATION_CORRECTION for those assets.
        self._rotation_corrections: dict = _load_rotation_corrections()

        # Register outgoing events
        for evt in ("spawnUsdResponse", "deleteUsdResponse", "replaceUsdResponse", "replaceAllUsdResponse"):
            messaging.register_event_type_to_send(evt)
            omni.kit.app.register_event_alias(
                carb.events.type_from_string(evt), evt
            )

        # Subscribe to spawn request
        omni.kit.app.register_event_alias(
            carb.events.type_from_string("spawnUsdRequest"),
            "spawnUsdRequest",
        )
        self._subscriptions.append(
            get_eventdispatcher().observe_event(
                observer_name="UsdSpawner:spawnUsdRequest",
                event_name="spawnUsdRequest",
                on_event=self._on_spawn_request,
            )
        )

        # Subscribe to delete request
        omni.kit.app.register_event_alias(
            carb.events.type_from_string("deleteUsdRequest"),
            "deleteUsdRequest",
        )
        self._subscriptions.append(
            get_eventdispatcher().observe_event(
                observer_name="UsdSpawner:deleteUsdRequest",
                event_name="deleteUsdRequest",
                on_event=self._on_delete_request,
            )
        )

        # Subscribe to replace request (single)
        omni.kit.app.register_event_alias(
            carb.events.type_from_string("replaceUsdRequest"),
            "replaceUsdRequest",
        )
        self._subscriptions.append(
            get_eventdispatcher().observe_event(
                observer_name="UsdSpawner:replaceUsdRequest",
                event_name="replaceUsdRequest",
                on_event=self._on_replace_request,
            )
        )

        # Subscribe to replace-all request (batch: source_paths + target asset)
        omni.kit.app.register_event_alias(
            carb.events.type_from_string("replaceAllUsdRequest"),
            "replaceAllUsdRequest",
        )
        self._subscriptions.append(
            get_eventdispatcher().observe_event(
                observer_name="UsdSpawner:replaceAllUsdRequest",
                event_name="replaceAllUsdRequest",
                on_event=self._on_replace_all_request,
            )
        )

        # Subscribe to adjust-asset-rotation request (browser rotation panel)
        omni.kit.app.register_event_alias(
            carb.events.type_from_string("adjustAssetRotation"),
            "adjustAssetRotation",
        )
        self._subscriptions.append(
            get_eventdispatcher().observe_event(
                observer_name="UsdSpawner:adjustAssetRotation",
                event_name="adjustAssetRotation",
                on_event=self._on_adjust_asset_rotation,
            )
        )

        # Deferred stage scan — populate stage_prims.json once the stage loads
        self._scan_pending = True
        self._update_sub = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(
                self._on_update,
                name="UsdSpawner:deferred_stage_scan",
                order=0,
            )
        )

        carb.log_info("[UsdSpawner] Ready. Asset library has "
                      f"{len(ASSET_LIBRARY)} entries.")

    # ------------------------------------------------------------------
    # Deferred stage scan
    # ------------------------------------------------------------------

    def _on_update(self, event) -> None:
        """Runs every frame until the stage is loaded, then scans once."""
        if not self._scan_pending:
            return
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return
        world = stage.GetPrimAtPath("/World")
        if not world:
            return
        if not list(world.GetChildren()):
            return
        # Stage is loaded and has content — scan it now
        self._scan_stage_to_inventory()
        self._scan_pending = False
        self._update_sub = None  # release subscription

    def _scan_stage_to_inventory(self) -> None:
        """
        Scan every /World/* prim on the current stage and write stage_prims.json
        with full metadata: asset_key, asset_name, usd_path, position, prim_name.

        This is the authoritative source for "what is on the shelf" — it covers
        items that were pre-placed in the USD file, not just chatbot-spawned ones.
        """
        stage = omni.usd.get_context().get_stage()
        if not stage:
            return
        world = stage.GetPrimAtPath("/World")
        if not world:
            return

        inventory: dict = {}
        xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())

        def _scan_prim(prim, shelf: str, depth: int) -> None:
            """Recursively scan prims; record known assets, recurse into groups."""
            if depth > 4:
                return
            prim_name = prim.GetName()
            prim_path = str(prim.GetPath())

            # Resolve asset_key from prim name (strip trailing _N suffix first)
            base = re.sub(r"_\d+$", "", prim_name)
            asset_key = (
                _STEM_TO_KEY.get(prim_name)
                or _STEM_TO_KEY.get(base)
                or _STEM_TO_KEY.get(prim_name.replace("-", "_"))
                or _STEM_TO_KEY.get(base.replace("-", "_"))
                or ""
            )

            if asset_key:
                # Known product — record with position and shelf group
                position = [0.0, 0.0, 0.0]
                try:
                    xform_api = UsdGeom.Xformable(prim)
                    translate_op = next(
                        (op for op in xform_api.GetOrderedXformOps()
                         if op.GetOpType() == UsdGeom.XformOp.TypeTranslate),
                        None,
                    )
                    if translate_op:
                        val = translate_op.Get(Usd.TimeCode.Default())
                        position = [round(val[0], 3), round(val[1], 3), round(val[2], 3)]
                    else:
                        world_xf = xf_cache.GetLocalToWorldTransform(prim)
                        trans = world_xf.ExtractTranslation()
                        position = [round(trans[0], 3), round(trans[1], 3), round(trans[2], 3)]
                except Exception as exc:
                    carb.log_warn(f"[UsdSpawner] Stage scan: pos read failed for {prim_path}: {exc}")

                # Count visual units: some models pack multiple cans into one prim
                # where each can is a separate Mesh_N child under a Geometry scope.
                # e.g. Pringles_Lobster has Geometry/Mesh, Mesh_01 … Mesh_07 = 8 cans.
                unit_count = 1
                try:
                    for ch in prim.GetChildren():
                        if ch.GetName().lower() == "geometry":
                            mesh_children = [
                                m for m in ch.GetChildren()
                                if m.GetName().startswith("Mesh")
                            ]
                            if len(mesh_children) > 1:
                                unit_count = len(mesh_children)
                            break
                except Exception:
                    pass

                inventory[prim_path] = {
                    "asset_key":   asset_key,
                    "asset_name":  asset_key.replace("_", " ").title(),
                    "usd_path":    ASSET_LIBRARY.get(asset_key, ""),
                    "position":    position,
                    "prim_name":   prim_name,
                    "shelf":       shelf,
                    "unit_count":  unit_count,
                    "source":      "stage_scan",
                }
            else:
                # Not a known product — treat as a group/shelf and recurse.
                # At depth=1 (direct child of /World) use its name as the shelf label.
                child_shelf = prim_name if depth == 1 else shelf
                for child in prim.GetChildren():
                    _scan_prim(child, child_shelf, depth + 1)

        for child in world.GetChildren():
            _scan_prim(child, "", 1)

        try:
            os.makedirs(os.path.dirname(STAGE_PRIMS_FILE), exist_ok=True)
            with open(STAGE_PRIMS_FILE, "w") as f:
                json.dump(inventory, f, indent=2)
            known = sum(1 for v in inventory.values() if v.get("asset_key"))
            total_units = sum(v.get("unit_count", 1) for v in inventory.values() if v.get("asset_key"))
            carb.log_info(
                f"[UsdSpawner] Stage scan complete: {len(inventory)} prims → "
                f"stage_prims.json  ({known} known assets, {total_units} visual units)"
            )
        except Exception as exc:
            carb.log_warn(f"[UsdSpawner] Could not write stage_prims.json: {exc}")

        # Push the full inventory (with unit_count) directly to the agent backend.
        # Try several candidate URLs — Docker may map port 8000 to localhost or
        # a bridge IP depending on run flags.
        _BACKEND_CANDIDATES = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://172.17.0.1:8000",   # default Docker bridge gateway from host
            "http://172.20.0.1:8000",   # alternate Docker network gateway
        ]
        import urllib.request as _ur
        _payload = json.dumps({"inventory": inventory}).encode("utf-8")
        _posted = False
        for _base in _BACKEND_CANDIDATES:
            try:
                _req = _ur.Request(
                    f"{_base}/api/stage-prims-kit",
                    data=_payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _ur.urlopen(_req, timeout=3) as _resp:
                    _body = _resp.read().decode()
                    carb.log_info(f"[UsdSpawner] Inventory POSTed to backend at {_base}: {_body}")
                    _posted = True
                    break
            except Exception as _exc:
                carb.log_info(f"[UsdSpawner] Backend not reachable at {_base}: {_exc}")
        if not _posted:
            carb.log_warn(
                "[UsdSpawner] Could not reach agent backend — unit_count data will "
                "not be available until Kit restarts and backend is reachable. "
                f"Tried: {_BACKEND_CANDIDATES}"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_world_position(
        self, screen_x: float, screen_y: float
    ) -> "Gf.Vec3d | None":
        """
        Convert normalised screen coords → world-space position on Y=0 plane.

        screen_x, screen_y ∈ [0, 1], (0,0) = top-left corner of the viewport.
        Returns None when computation is not possible (no stage/camera).
        """
        try:
            from omni.kit.viewport.utility import get_active_viewport

            viewport = get_active_viewport()
            if viewport is None:
                carb.log_error("[UsdSpawner] No active viewport")
                return None

            stage = omni.usd.get_context().get_stage()
            camera_path = viewport.camera_path
            camera_prim = stage.GetPrimAtPath(camera_path)
            if not camera_prim:
                carb.log_error(f"[UsdSpawner] Camera prim not found: {camera_path}")
                return None

            # Build a Gf.Camera from the USD prim and get its frustum
            usd_camera = UsdGeom.Camera(camera_prim)
            gf_camera = usd_camera.GetCamera(Usd.TimeCode.Default())
            frustum = gf_camera.frustum

            # Screen [0,1] → NDC [-1,1].  Y is flipped: screen top = NDC +1.
            ndc_x = 2.0 * screen_x - 1.0
            ndc_y = 1.0 - 2.0 * screen_y

            ray = frustum.ComputePickRay(Gf.Vec2d(ndc_x, ndc_y))
            origin: Gf.Vec3d = ray.startPoint
            direction: Gf.Vec3d = ray.direction

            # Intersect ray with Y=0 ground plane:  origin.y + t * dir.y = 0
            if abs(direction[1]) < 1e-6:
                # Ray nearly parallel to ground — project 15 units forward
                carb.log_warn("[UsdSpawner] Ray parallel to ground, using fallback distance")
                t = 15.0
            else:
                t = -origin[1] / direction[1]
                if t < 0:
                    t = abs(t)  # camera below ground or looking away

            hit = origin + t * direction
            return Gf.Vec3d(hit[0], 0.0, hit[2])  # snap Y to ground

        except Exception as exc:
            carb.log_error(f"[UsdSpawner] Ray computation error: {exc}")
            return None

    def _make_unique_prim_path(self, prim_name: str) -> str:
        """Return a unique /World/<name> path, appending _N when needed.
        Checks the live stage so paths stay unique across extension reloads."""
        stage = omni.usd.get_context().get_stage()
        safe = re.sub(r"[^A-Za-z0-9_]", "_", prim_name).strip("_") or "Asset"
        while True:
            count = self._spawn_counter.get(safe, 0) + 1
            self._spawn_counter[safe] = count
            suffix = f"_{count}" if count > 1 else ""
            prim_path = f"/World/{safe}{suffix}"
            if not stage.GetPrimAtPath(prim_path):
                return prim_path

    def _spawn_usd(
        self, usd_path: str, prim_name: str, position: "Gf.Vec3d",
        rotation: "Gf.Rotation" = None,
        snap_y_to: float = None,
    ) -> str:
        """
        Reference `usd_path` into the current stage at `position`.
        Returns the stage prim path of the spawned asset.

        The reference is placed on a child prim so that our translate op
        on the outer Xform does not conflict with whatever xformOps the
        referenced USD defines on its default prim.

        Optional `rotation` (Gf.Rotation) preserves the world-space orientation
        of the original prim when performing a replace operation.

        Optional `snap_y_to` (float): when provided, the new item's world-space
        bottom (bbox y_min) is shifted to land exactly at this Y level.  Used
        during replace so the replacement sits at the same shelf height as the
        original item regardless of pivot offsets.  When omitted the existing
        floor-snap-to-Y=0 logic runs instead.
        """
        stage = omni.usd.get_context().get_stage()

        # Ensure /World Xform exists
        if not stage.GetPrimAtPath("/World"):
            UsdGeom.Xform.Define(stage, "/World")

        prim_path = self._make_unique_prim_path(prim_name)

        # Outer Xform — owns the world-space translation (and rotation when replacing).
        xform = UsdGeom.Xform.Define(stage, prim_path)

        # Safely get or add the translate op (avoids duplicate-op crash on reload)
        translate_op = next(
            (op for op in xform.GetOrderedXformOps()
             if op.GetOpType() == UsdGeom.XformOp.TypeTranslate),
            None
        )
        if translate_op is None:
            translate_op = xform.AddTranslateOp()
        translate_op.Set(position)

        # Compose any inherited world rotation with a per-asset correction rotation.
        # Some assets are authored with a non-standard up-axis and need a fixed
        # correction so they appear upright when spawned.
        #
        # Priority: JSON file (self._rotation_corrections) > ASSET_SPAWN_ROTATION_CORRECTION
        has_rotation_correction = (
            prim_name in self._rotation_corrections
            or prim_name in ASSET_SPAWN_ROTATION_CORRECTION
        )
        effective_rotation = rotation  # may be None

        if prim_name in self._rotation_corrections:
            # JSON-saved absolute Euler correction (set via browser rotation panel).
            # Applied as absolute orientation — overrides world rotation for this asset.
            rc = self._rotation_corrections[prim_name]
            ex = float(rc.get("euler_x", 0))
            ey = float(rc.get("euler_y", 0))
            ez = float(rc.get("euler_z", 0))
            rot_z = Gf.Rotation(Gf.Vec3d(0, 0, 1), ez)
            rot_y = Gf.Rotation(Gf.Vec3d(0, 1, 0), ey)
            rot_x = Gf.Rotation(Gf.Vec3d(1, 0, 0), ex)
            effective_rotation = rot_x * rot_y * rot_z
            carb.log_warn(
                f"[UsdSpawner] Spawn: using saved rotation correction"
                f" X={ex}° Y={ey}° Z={ez}° for '{prim_name}'"
            )
        else:
            correction_entries = ASSET_SPAWN_ROTATION_CORRECTION.get(prim_name) or []
            # Normalise: a single tuple → list of one
            if correction_entries and isinstance(correction_entries[0], (int, float)):
                correction_entries = [correction_entries]
            for correction_entry in correction_entries:
                try:
                    axis, angle_deg = correction_entry
                    correction_rot = Gf.Rotation(Gf.Vec3d(*axis), angle_deg)
                    if effective_rotation is not None:
                        # Apply correction first (in asset-local space), then world rotation.
                        effective_rotation = effective_rotation * correction_rot
                    else:
                        effective_rotation = correction_rot
                    carb.log_warn(
                        f"[UsdSpawner] Spawn: applying correction rot {angle_deg}° "
                        f"around {axis} for '{prim_name}'"
                    )
                except Exception as corr_err:
                    carb.log_warn(f"[UsdSpawner] Spawn: correction rotation failed: {corr_err}")

        # Apply effective rotation (inherited + correction) if any.
        if effective_rotation is not None:
            try:
                quat_raw = effective_rotation.GetQuaternion()
                q = Gf.Quatd(quat_raw.GetReal(), Gf.Vec3d(quat_raw.GetImaginary()))
                orient_op = xform.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
                orient_op.Set(q)
                carb.log_warn(f"[UsdSpawner] Spawn: applied rotation quaternion {q} to '{prim_path}'")
            except Exception as rot_err:
                carb.log_warn(f"[UsdSpawner] Spawn: could not apply rotation: {rot_err}")

        # Child prim holds the reference; its internal xformOps are unaffected.
        # Scale by 100 to convert from meters (USDZ, metersPerUnit=1.0) to
        # centimeters (store stage, metersPerUnit=0.01).  Remove this if your
        # stage uses meters.
        ref_path = prim_path + "/Ref"
        ref_xform = UsdGeom.Xform.Define(stage, ref_path)
        ref_xform.AddScaleOp().Set(Gf.Vec3f(100.0, 100.0, 100.0))
        ref_xform.GetPrim().GetReferences().AddReference(usd_path)

        # Y-snap: adjust the outer Xform so the new asset's bottom sits at the
        # correct shelf/floor height.
        #
        #   snap_y_to is set  → replace mode: snap bottom to original item's bottom Y
        #   snap_y_to is None → fresh spawn:  snap bottom to Y=0 only if below ground
        try:
            bbox_cache = UsdGeom.BBoxCache(
                Usd.TimeCode.Default(),
                includedPurposes=[UsdGeom.Tokens.default_],
                useExtentsHint=False,
            )
            bbox = bbox_cache.ComputeWorldBound(xform.GetPrim())
            rng  = bbox.GetRange()
            if not rng.IsEmpty():
                y_min = rng.GetMin()[1]
                if snap_y_to is not None:
                    # Always align: shift translate so bbox bottom lands on snap_y_to
                    cur_translate_y = translate_op.Get(Usd.TimeCode.Default())[1]
                    snapped_y = cur_translate_y + (snap_y_to - y_min)
                    translate_op.Set(Gf.Vec3d(position[0], snapped_y, position[2]))
                    carb.log_warn(
                        f"[UsdSpawner] Shelf-snap: new_bbox_y_min={y_min:.2f}  "
                        f"snap_y_to={snap_y_to:.2f}  cur_translate_y={cur_translate_y:.2f}  "
                        f"→ snapped_y={snapped_y:.2f}"
                    )
                elif has_rotation_correction:
                    # Rotation correction was applied: the item's geometric center may
                    # have drifted from the translate position (pivot ≠ exact center).
                    # Snap so bbox center aligns with the requested position Y.
                    y_max = rng.GetMax()[1]
                    bbox_center_y = (y_min + y_max) / 2
                    center_drift = bbox_center_y - position[1]
                    if abs(center_drift) > 0.5:   # only correct if drift > 5 mm
                        cur_translate_y = translate_op.Get(Usd.TimeCode.Default())[1]
                        snapped_y = cur_translate_y - center_drift
                        translate_op.Set(Gf.Vec3d(position[0], snapped_y, position[2]))
                        carb.log_warn(
                            f"[UsdSpawner] Center-snap: bbox_center={bbox_center_y:.2f}  "
                            f"target_y={position[1]:.2f}  drift={center_drift:.2f}  "
                            f"→ translate_y {cur_translate_y:.2f} → {snapped_y:.2f}"
                        )
                elif y_min < -0.5:
                    # Fresh spawn only: lift to floor (Y=0) if item is below ground
                    snapped_y = position[1] - y_min
                    translate_op.Set(Gf.Vec3d(position[0], snapped_y, position[2]))
                    carb.log_warn(
                        f"[UsdSpawner] Floor-snap: y_min={y_min:.1f} → Y adjusted to {snapped_y:.1f}"
                    )
        except Exception as snap_err:
            carb.log_warn(f"[UsdSpawner] Y-snap failed (asset may be partially underground): {snap_err}")

        # Apply per-asset translation offset (saved via browser rotation panel).
        if prim_name in self._rotation_corrections:
            rc = self._rotation_corrections[prim_name]
            ox = float(rc.get("offset_x", 0))
            oy = float(rc.get("offset_y", 0))
            oz = float(rc.get("offset_z", 0))
            if ox or oy or oz:
                cur = translate_op.Get(Usd.TimeCode.Default())
                translate_op.Set(Gf.Vec3d(cur[0] + ox, cur[1] + oy, cur[2] + oz))
                carb.log_warn(
                    f"[UsdSpawner] Spawn: applied translation offset"
                    f" ({ox},{oy},{oz}) cm to '{prim_path}'"
                )

        carb.log_info(
            f"[UsdSpawner] Spawned '{usd_path}' → '{prim_path}'  pos={position}"
        )

        # Record for later deletion (in-memory + persistent inventory)
        self._spawned_prims.setdefault(prim_name, []).append(prim_path)
        self._inventory_add(prim_path, prim_name, usd_path, position)

        # ── Debug: report what actually landed on stage ──────────────────
        try:
            outer = stage.GetPrimAtPath(prim_path)
            ref   = ref_xform.GetPrim()
            ref_children = list(ref.GetChildren())

            carb.log_warn(
                f"[UsdSpawner][DEBUG] outer  valid={outer.IsValid()}  "
                f"active={outer.IsActive()}  type='{outer.GetTypeName()}'"
            )
            carb.log_warn(
                f"[UsdSpawner][DEBUG] ref    valid={ref.IsValid()}  "
                f"active={ref.IsActive()}  type='{ref.GetTypeName()}'  "
                f"children={len(ref_children)}"
            )
            if not ref_children:
                carb.log_error(
                    f"[UsdSpawner][DEBUG] Reference has NO children — "
                    f"the file may not be accessible at: {usd_path}"
                )
            else:
                for c in ref_children[:5]:
                    carb.log_warn(f"[UsdSpawner][DEBUG]   child: {c.GetPath()}  type={c.GetTypeName()}")

            # Check visibility
            imageable = UsdGeom.Imageable(outer)
            vis = imageable.ComputeVisibility(Usd.TimeCode.Default())
            carb.log_warn(f"[UsdSpawner][DEBUG] visibility='{vis}'")

            # Check world bounds (may be empty if geometry hasn't cooked yet)
            try:
                from pxr import UsdGeom as _UG
                bbox_cache = _UG.BBoxCache(
                    Usd.TimeCode.Default(),
                    includedPurposes=[_UG.Tokens.default_],
                    useExtentsHint=False,
                )
                bbox = bbox_cache.ComputeWorldBound(outer)
                rng  = bbox.GetRange()
                carb.log_warn(
                    f"[UsdSpawner][DEBUG] bbox min={rng.GetMin()}  max={rng.GetMax()}  "
                    f"empty={rng.IsEmpty()}"
                )
            except Exception as bbox_err:
                carb.log_warn(f"[UsdSpawner][DEBUG] bbox error: {bbox_err}")

        except Exception as dbg_err:
            carb.log_error(f"[UsdSpawner][DEBUG] debug block failed: {dbg_err}")
        # ─────────────────────────────────────────────────────────────────

        return prim_path

    def _reply(self, payload: dict) -> None:
        get_eventdispatcher().dispatch_event("spawnUsdResponse", payload=payload)

    def _reply_delete(self, payload: dict) -> None:
        get_eventdispatcher().dispatch_event("deleteUsdResponse", payload=payload)

    def _reply_replace(self, payload: dict) -> None:
        get_eventdispatcher().dispatch_event("replaceUsdResponse", payload=payload)

    # ------------------------------------------------------------------
    # Inventory helpers — persistent JSON tracking of spawned prims
    # ------------------------------------------------------------------

    def _load_inventory(self) -> dict:
        """Load the inventory JSON from disk. Returns {} on error."""
        try:
            if os.path.exists(INVENTORY_FILE):
                with open(INVENTORY_FILE, "r") as f:
                    return json.load(f)
        except Exception as exc:
            carb.log_warn(f"[UsdSpawner] Could not load inventory: {exc}")
        return {}

    def _save_inventory(self, inventory: dict) -> None:
        """Write the inventory JSON to disk."""
        try:
            os.makedirs(os.path.dirname(INVENTORY_FILE), exist_ok=True)
            with open(INVENTORY_FILE, "w") as f:
                json.dump(inventory, f, indent=2)
        except Exception as exc:
            carb.log_warn(f"[UsdSpawner] Could not save inventory: {exc}")

    def _inventory_add(self, prim_path: str, asset_key: str, usd_path: str,
                       position: "Gf.Vec3d") -> None:
        """Record a newly spawned prim in the inventory file."""
        inv = self._load_inventory()
        inv[prim_path] = {
            "asset_key":  asset_key,
            "asset_name": asset_key.replace("_", " ").title(),
            "usd_path":   usd_path,
            "position":   [round(position[0], 3), round(position[1], 3),
                           round(position[2], 3)],
            "spawned_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._save_inventory(inv)
        carb.log_info(f"[UsdSpawner] Inventory: added {prim_path}")

    def _inventory_remove(self, prim_paths) -> None:
        """Remove one or more prim paths from both inventory files."""
        if isinstance(prim_paths, str):
            prim_paths = [prim_paths]
        for inv_path in (INVENTORY_FILE, STAGE_PRIMS_FILE):
            try:
                if not os.path.exists(inv_path):
                    continue
                with open(inv_path, "r") as f:
                    inv = json.load(f)
                changed = False
                for pp in prim_paths:
                    if pp in inv:
                        del inv[pp]
                        changed = True
                        carb.log_info(f"[UsdSpawner] Inventory ({os.path.basename(inv_path)}): removed {pp}")
                if changed:
                    with open(inv_path, "w") as f:
                        json.dump(inv, f, indent=2)
            except Exception as exc:
                carb.log_warn(f"[UsdSpawner] Could not update {inv_path}: {exc}")

    def _inventory_find_by_brand(self, brand_or_key: str) -> list:
        """
        Return all prim paths whose asset_key matches brand_or_key.

        Searches both inventory files:
          - asset_list_shop_already.json  (chatbot-spawned items)
          - stage_prims.json              (full stage scan sent by browser on load)

        Matching rules:
          1. Exact asset_key match  (e.g. "pringles_cheese")
          2. Brand-group prefix     (e.g. "pringles" → pringles_cheese, pringles_bbq ...)
        """
        matched = []
        for inv_path in (INVENTORY_FILE, STAGE_PRIMS_FILE):
            try:
                if not os.path.exists(inv_path):
                    continue
                with open(inv_path, "r") as f:
                    inv = json.load(f)
                for prim_path, info in inv.items():
                    ak = info.get("asset_key", "")
                    if ak and (ak == brand_or_key or ak.startswith(brand_or_key + "_")):
                        if prim_path not in matched:
                            matched.append(prim_path)
            except Exception as exc:
                carb.log_warn(f"[UsdSpawner] Could not read {inv_path}: {exc}")
        return matched

    def _find_prims_by_asset_key(self, asset_key: str) -> list:
        """
        Return ALL /World/* prim paths that belong to the given asset_key.

        Combines results from every available source — no early return — so
        pre-placed stage items, chatbot-spawned items, and inventory entries
        are all included:
          1. In-memory _spawned_prims dict
          2. Both inventory files (asset_list_shop_already.json + stage_prims.json)
          3. Live stage scan using USD filename stem from ASSET_LIBRARY
        """
        stage = omni.usd.get_context().get_stage()
        found: set = set()

        # 1. In-memory tracker
        for p in self._spawned_prims.get(asset_key, []):
            if stage.GetPrimAtPath(p).IsValid():
                found.add(p)

        # 2. Inventory files
        for p in self._inventory_find_by_brand(asset_key):
            if stage.GetPrimAtPath(p).IsValid():
                found.add(p)

        # 3. Live stage scan via USD filename stem (recursive — handles shelf groups)
        stem = _KEY_TO_STEM.get(asset_key, "")
        if stem:
            stem_lower     = stem.lower()
            safe_stem_lower = stem.replace("-", "_").lower()

            def _scan_for_stem(parent_prim, depth: int = 0) -> None:
                if depth > 4:
                    return
                for c in parent_prim.GetChildren():
                    name       = c.GetName()
                    name_lower = name.lower()
                    base_lower = re.sub(r"_\d+$", "", name_lower)
                    if name_lower in (stem_lower, safe_stem_lower) or \
                       base_lower in (stem_lower, safe_stem_lower):
                        found.add(str(c.GetPath()))
                    else:
                        _scan_for_stem(c, depth + 1)

            world = stage.GetPrimAtPath("/World")
            if world:
                _scan_for_stem(world)

        result = sorted(found)
        carb.log_info(
            f"[UsdSpawner] _find_prims_by_asset_key('{asset_key}'): "
            f"{len(result)} prim(s) total"
        )
        return result

    # ------------------------------------------------------------------
    # Delete helpers
    # ------------------------------------------------------------------

    def _delete_usd(self, prim_name: str) -> tuple:
        """
        Remove the most recently spawned prim for the given asset key.
        Returns (success: bool, prim_path_or_error: str).

        Falls back to a stage scan when _spawned_prims is empty (e.g. after
        extension reload) so pre-existing prims can still be deleted.
        """
        stage = omni.usd.get_context().get_stage()
        paths = self._spawned_prims.get(prim_name, [])

        # Filter to paths still present on stage
        existing = [p for p in paths if stage.GetPrimAtPath(p).IsValid()]
        self._spawned_prims[prim_name] = existing

        # Fallback: scan /World for matching prims when nothing is tracked
        # (covers extension reloads or prims spawned in a previous session).
        if not existing:
            safe = re.sub(r"[^A-Za-z0-9_]", "_", prim_name).strip("_") or "Asset"
            world_prim = stage.GetPrimAtPath("/World")
            if world_prim:
                pattern = re.compile(rf"^/World/{re.escape(safe)}(_\d+)?$")
                for child in world_prim.GetChildren():
                    path_str = str(child.GetPath())
                    if pattern.match(path_str):
                        existing.append(path_str)
                existing.sort()   # ascending — pop() gives the highest-numbered one
                carb.log_info(
                    f"[UsdSpawner] Stage-scan found {len(existing)} "
                    f"'{prim_name}' prim(s): {existing}"
                )

        if not existing:
            return False, f"No spawned '{prim_name}' found on stage"

        # Remove the most recently spawned instance
        prim_path = existing.pop()
        self._spawned_prims[prim_name] = existing

        stage.RemovePrim(prim_path)
        self._inventory_remove(prim_path)
        carb.log_info(f"[UsdSpawner] Deleted '{prim_path}'")
        return True, prim_path

    def _on_delete_request(self, event) -> None:
        payload    = event.payload
        prim_name  = str(payload.get("prim_name", ""))
        prim_path  = str(payload.get("prim_path", ""))   # single direct path
        prim_paths = payload.get("prim_paths", [])        # batch: list of direct paths
        delete_all = bool(payload.get("delete_all", False))  # delete ALL of named type

        carb.log_info(
            f"[UsdSpawner] deleteUsdRequest  name={prim_name}  path={prim_path}"
            f"  batch={len(prim_paths)}  delete_all={delete_all}"
        )

        stage = omni.usd.get_context().get_stage()

        # ── Batch delete: list of direct paths (multi-selection) ──────────────
        if prim_paths:
            deleted = []
            for pp in prim_paths:
                if stage.GetPrimAtPath(pp).IsValid():
                    stage.RemovePrim(pp)
                    deleted.append(pp)
                    carb.log_info(f"[UsdSpawner] Batch-deleted '{pp}'")
            if deleted:
                self._inventory_remove(deleted)
            self._reply_delete({
                "result":    "success" if deleted else "error",
                "prim_path": deleted[0] if deleted else "",
                "count":     len(deleted),
                "error":     "" if deleted else "None of the specified prims exist on stage",
            })
            return

        # ── Delete all instances of a named brand/type from stage ─────────────
        if prim_name and delete_all:
            # Resolve all asset keys belonging to this brand/key.
            # e.g. "pringles" → ["pringles_cheese","pringles_bbq","pringles_pizza","pringles_lobster"]
            related_keys = _BRAND_GROUPS.get(prim_name, [])
            if not related_keys:
                # prim_name is already a specific key, not a brand prefix
                related_keys = [prim_name]

            # Collect every matching prim across all sources (inventory + stage scan),
            # using _find_prims_by_asset_key which is case-insensitive and exhaustive.
            to_delete_set: set = set()
            for rk in related_keys:
                for p in self._find_prims_by_asset_key(rk):
                    to_delete_set.add(p)

            # Also search by brand prefix directly (catches exact prim_name as asset_key)
            if prim_name not in related_keys:
                for p in self._find_prims_by_asset_key(prim_name):
                    to_delete_set.add(p)

            valid = sorted(to_delete_set)
            carb.log_info(
                f"[UsdSpawner] delete_all '{prim_name}': "
                f"found {len(valid)} prim(s) to delete: {valid}"
            )

            for pp in valid:
                stage.RemovePrim(pp)
            if valid:
                self._inventory_remove(valid)
            # Clear in-memory tracker for all related keys
            for rk in related_keys:
                self._spawned_prims.pop(rk, None)
            self._spawned_prims.pop(prim_name, None)

            self._reply_delete({
                "result":    "success" if valid else "error",
                "prim_path": valid[0] if valid else "",
                "count":     len(valid),
                "error":     "" if valid else f"Could not remove: No '{prim_name}' prims found on stage",
            })
            return

        # ── Single direct path (selected-prim delete) ─────────────────────────
        if prim_path:
            if stage.GetPrimAtPath(prim_path).IsValid():
                stage.RemovePrim(prim_path)
                self._inventory_remove(prim_path)
                carb.log_info(f"[UsdSpawner] Deleted selected prim '{prim_path}'")
                self._reply_delete({"result": "success", "prim_path": prim_path, "count": 1, "error": ""})
            else:
                self._reply_delete({"result": "error", "prim_path": "",
                                    "count": 0, "error": f"Prim not found: {prim_path}"})
            return

        # ── Single named asset (most-recent instance) ─────────────────────────
        if not prim_name:
            self._reply_delete({"result": "error", "count": 0,
                                 "error": "No prim_name, prim_path, or prim_paths provided",
                                 "prim_path": ""})
            return

        success, result = self._delete_usd(prim_name)
        if success:
            self._reply_delete({"result": "success", "prim_path": result, "count": 1, "error": ""})
        else:
            self._reply_delete({"result": "error", "prim_path": "", "count": 0, "error": result})

    # ------------------------------------------------------------------
    # Replace handler
    # ------------------------------------------------------------------

    def _on_replace_request(self, event) -> None:
        """
        replaceUsdRequest payload:
          { target_prim_path: str, prim_name: str }

        Steps:
          1. Get the world-space position of target_prim_path (outer Xform translate).
          2. Remove target_prim_path from the stage.
          3. Spawn the new asset at that same position.
        """
        payload          = event.payload
        target_path      = str(payload.get("target_prim_path", ""))
        prim_name        = str(payload.get("prim_name", ""))

        carb.log_info(
            f"[UsdSpawner] replaceUsdRequest  target={target_path}  new={prim_name}"
        )

        if not target_path or not prim_name:
            self._reply_replace({
                "result": "error",
                "error": "target_prim_path and prim_name are required",
                "prim_path": "", "position": [0, 0, 0],
            })
            return

        usd_path = ASSET_LIBRARY.get(prim_name)
        if not usd_path:
            self._reply_replace({
                "result": "error",
                "error": f"No USD path for asset '{prim_name}'. Add it to ASSET_LIBRARY.",
                "prim_path": "", "position": [0, 0, 0],
            })
            return

        stage = omni.usd.get_context().get_stage()
        target_prim = stage.GetPrimAtPath(target_path)
        if not target_prim or not target_prim.IsValid():
            self._reply_replace({
                "result": "error",
                "error": f"Target prim not found on stage: {target_path}",
                "prim_path": "", "position": [0, 0, 0],
            })
            return

        # Extract the world-space position and rotation of the target prim.
        # Always use XformCache so shelf-nested items (whose local translate is
        # relative to the parent shelf group) are placed correctly in /World.
        # Copy world rotation so replacement inherits the same orientation.
        position = Gf.Vec3d(0.0, 0.0, 0.0)
        rotation = None
        try:
            xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
            world_xf = xf_cache.GetLocalToWorldTransform(target_prim)
            position = Gf.Vec3d(world_xf.ExtractTranslation())
            rotation = world_xf.ExtractRotation()
            carb.log_warn(
                f"[UsdSpawner] Replace: world pos={position}  rot={rotation}  "
                f"from '{target_path}'"
            )
        except Exception as pos_err:
            carb.log_warn(f"[UsdSpawner] Replace: could not extract world transform: {pos_err}")

        # Determine whether the target is a pre-placed (shelf-nested) item.
        # Pre-placed items have their local origin AT the shelf surface, so
        # their world Y IS the shelf surface.  Snap the new item's bottom
        # to that Y so it sits on the shelf instead of being half-embedded.
        path_parts = target_path.split("/")   # ["", "World", "Shelf_N", "Item"]
        snap_y_to = position[1] if len(path_parts) > 3 else None

        # Remove the target prim and its inventory entry
        stage.RemovePrim(target_path)
        self._inventory_remove(target_path)
        carb.log_warn(f"[UsdSpawner] Replace: removed '{target_path}'  snap_y_to={snap_y_to}")

        # Spawn the new asset at the original world position with the same rotation.
        try:
            new_prim_path = self._spawn_usd(usd_path, prim_name, position, rotation=rotation, snap_y_to=snap_y_to)
            self._reply_replace({
                "result":    "success",
                "prim_path": new_prim_path,
                "position":  [round(position[0], 3), round(position[1], 3),
                               round(position[2], 3)],
                "error":     "",
            })
        except Exception as exc:
            carb.log_error(f"[UsdSpawner] Replace spawn failed: {exc}")
            self._reply_replace({
                "result": "error", "error": str(exc),
                "prim_path": "", "position": [0, 0, 0],
            })

    # ------------------------------------------------------------------
    # Batch replace handler
    # ------------------------------------------------------------------

    def _on_replace_all_request(self, event) -> None:
        """
        replaceAllUsdRequest payload:
          { source_paths: ["/World/NittoTea_Royal_Milktea", ...], prim_name: "pringles_cheese" }

        For each source path:
          1. Read the world-space position of the existing prim.
          2. Remove it from stage + inventory.
          3. Spawn the new asset at the same position.
        Replies with replaceAllUsdResponse { result, count, prim_paths, error }.
        """
        payload      = event.payload
        source_paths = list(payload.get("source_paths", []))
        source_key   = str(payload.get("source_key", ""))
        prim_name    = str(payload.get("prim_name", ""))

        carb.log_info(
            f"[UsdSpawner] replaceAllUsdRequest  target={prim_name}  "
            f"source_key={source_key}  backend_paths={len(source_paths)}: {source_paths}"
        )
        carb.log_info(f"[UsdSpawner] _spawned_prims: { {k: v for k, v in self._spawned_prims.items()} }")

        # Expand source_key to all brand-group members.
        # e.g. source_key="pringles_cheese" → also scan pringles_bbq, pringles_pizza, pringles_lobster.
        # e.g. source_key="pringles"        → scan all four pringles variants.
        related_source_keys: list = _BRAND_GROUPS.get(source_key, [])
        if not related_source_keys:
            # source_key is a specific key — check if it belongs to a brand group
            for _brand, _keys in _BRAND_GROUPS.items():
                if source_key in _keys:
                    related_source_keys = list(_keys)
                    break
        if not related_source_keys:
            related_source_keys = [source_key]

        # Always do an exhaustive Kit-side scan combining:
        #   - paths supplied by the backend (possibly stale after prior operations)
        #   - live stage scan for every related asset key (catches newly spawned prims)
        all_source: set = set(source_paths)
        for rk in related_source_keys:
            for p in self._find_prims_by_asset_key(rk):
                all_source.add(p)
        # If none of the above matched, also try source_key itself directly
        if not all_source and source_key:
            for p in self._find_prims_by_asset_key(source_key):
                all_source.add(p)
        source_paths = sorted(all_source)

        carb.log_warn(
            f"[UsdSpawner] replaceAllUsdRequest after expansion: "
            f"{len(source_paths)} prim(s) to replace: {source_paths}  →  new='{prim_name}'  usd='{ASSET_LIBRARY.get(prim_name)}'"
        )

        usd_path = ASSET_LIBRARY.get(prim_name)
        if not usd_path:
            get_eventdispatcher().dispatch_event("replaceAllUsdResponse", payload={
                "result": "error", "count": 0, "prim_paths": [],
                "error": f"No USD path for asset '{prim_name}'. Add it to ASSET_LIBRARY.",
            })
            return

        stage    = omni.usd.get_context().get_stage()
        replaced = []
        failed   = []

        for target_path in source_paths:
            target_prim = stage.GetPrimAtPath(target_path)
            if not target_prim or not target_prim.IsValid():
                carb.log_warn(f"[UsdSpawner] ReplaceAll: prim not on stage: {target_path}")
                failed.append(target_path)
                continue

            # Extract world-space position and rotation of the existing prim.
            # Always use XformCache — shelf-nested items have a LOCAL translate op
            # that is relative to their parent shelf group, not to /World.
            # Copy world rotation so the replacement inherits the same orientation.
            position = Gf.Vec3d(0.0, 0.0, 0.0)
            rotation = None
            try:
                xf_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
                world_xf = xf_cache.GetLocalToWorldTransform(target_prim)
                position = Gf.Vec3d(world_xf.ExtractTranslation())
                rotation = world_xf.ExtractRotation()
                carb.log_warn(
                    f"[UsdSpawner] ReplaceAll: world pos={position}  rot={rotation}  "
                    f"for '{target_path}'"
                )
            except Exception as pos_err:
                carb.log_warn(f"[UsdSpawner] ReplaceAll: world transform read failed for {target_path}: {pos_err}")

            # Determine whether the target is a pre-placed (shelf-nested) item.
            # Pre-placed items have their local origin AT the shelf surface, so
            # their world Y IS the shelf surface.  Snap the new item's bottom
            # to that Y so it sits on the shelf instead of being half-embedded.
            # Spawned items (/World/item) have their pivot at their geometric
            # center — use center-snap instead (handled in _spawn_usd).
            path_parts = target_path.split("/")  # ["", "World", "Shelf_N", "Item"]
            snap_y_to = position[1] if len(path_parts) > 3 else None

            # Remove old prim
            stage.RemovePrim(target_path)
            self._inventory_remove(target_path)

            # Spawn new asset at the original world position with the same rotation.
            try:
                new_path = self._spawn_usd(usd_path, prim_name, position, rotation=rotation, snap_y_to=snap_y_to)
                replaced.append(new_path)
                carb.log_warn(f"[UsdSpawner] ReplaceAll: OK  {target_path} → {new_path}  pos={position}")
            except Exception as spawn_err:
                carb.log_warn(f"[UsdSpawner] ReplaceAll: SPAWN FAILED for {target_path}: {spawn_err}")
                import traceback
                carb.log_warn(f"[UsdSpawner] ReplaceAll: traceback: {traceback.format_exc()}")
                failed.append(target_path)

        get_eventdispatcher().dispatch_event("replaceAllUsdResponse", payload={
            "result":    "success" if replaced else "error",
            "count":     len(replaced),
            "prim_paths": replaced,
            "error":     "" if replaced else f"Failed to replace any of {len(source_paths)} prims",
        })

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_spawn_request(self, event) -> None:
        payload = event.payload
        screen_x  = float(payload.get("screen_x",  0.5))
        screen_y  = float(payload.get("screen_y",  0.5))
        prim_name = str(payload.get("prim_name", "SpawnedAsset"))

        # Resolve asset path: prefer local ASSET_LIBRARY (Kit controls paths),
        # fall back to whatever usd_path the browser forwarded.
        usd_path = ASSET_LIBRARY.get(prim_name) or str(payload.get("usd_path", ""))

        carb.log_info(
            f"[UsdSpawner] spawnUsdRequest  screen=({screen_x:.3f},{screen_y:.3f})"
            f"  name={prim_name}  resolved_path={usd_path}"
        )

        if not usd_path:
            self._reply({"result": "error",
                         "error": f"No USD path for asset '{prim_name}'. "
                                   "Add it to ASSET_LIBRARY in usd_spawner.py.",
                         "prim_path": "", "position": [0, 0, 0]})
            return

        position = self._compute_world_position(screen_x, screen_y)
        if position is None:
            self._reply({"result": "error", "error": "Could not compute world position",
                         "prim_path": "", "position": [0, 0, 0]})
            return

        try:
            prim_path = self._spawn_usd(usd_path, prim_name, position)
            self._reply({
                "result":    "success",
                "prim_path": prim_path,
                "position":  [round(position[0], 3), round(position[1], 3),
                               round(position[2], 3)],
                "error":     "",
            })
        except Exception as exc:
            carb.log_error(f"[UsdSpawner] Spawn failed: {exc}")
            self._reply({"result": "error", "error": str(exc),
                         "prim_path": "", "position": [0, 0, 0]})

    # ------------------------------------------------------------------

    def _on_adjust_asset_rotation(self, event) -> None:
        """
        Browser Rotation Adjustment Panel → adjustAssetRotation event.

        Finds all /World/* prims whose prim name starts with prim_name and
        sets their orient op to the Euler angles (X, Y, Z degrees) received.
        The rotation is applied as an absolute orientation (ZYX order: Z first,
        then Y, then X) so re-running always gives a predictable result.
        """
        payload   = event.payload
        prim_name = str(payload.get("prim_name", ""))
        euler_x   = float(payload.get("euler_x", 0))
        euler_y   = float(payload.get("euler_y", 0))
        euler_z   = float(payload.get("euler_z", 0))
        offset_x  = float(payload.get("offset_x", 0))
        offset_y  = float(payload.get("offset_y", 0))
        offset_z  = float(payload.get("offset_z", 0))

        carb.log_warn(
            f"[UsdSpawner] adjustAssetRotation  prim_name={prim_name}"
            f"  rot=({euler_x}°,{euler_y}°,{euler_z}°)"
            f"  offset=({offset_x},{offset_y},{offset_z}) cm"
        )

        if not prim_name:
            carb.log_warn("[UsdSpawner] adjustAssetRotation: missing prim_name")
            return

        # Compute delta offset vs previously saved values (to update existing prims correctly).
        prev = self._rotation_corrections.get(prim_name, {})
        prev_ox = float(prev.get("offset_x", 0))
        prev_oy = float(prev.get("offset_y", 0))
        prev_oz = float(prev.get("offset_z", 0))
        delta_x = offset_x - prev_ox
        delta_y = offset_y - prev_oy
        delta_z = offset_z - prev_oz

        # Persist to JSON so future spawns use these values.
        self._rotation_corrections[prim_name] = {
            "euler_x": euler_x,
            "euler_y": euler_y,
            "euler_z": euler_z,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "offset_z": offset_z,
        }
        _save_rotation_corrections(self._rotation_corrections)

        stage = omni.usd.get_context().get_stage()
        if not stage:
            carb.log_warn("[UsdSpawner] adjustAssetRotation: no stage")
            return

        world = stage.GetPrimAtPath("/World")
        if not world:
            carb.log_warn("[UsdSpawner] adjustAssetRotation: /World not found")
            return

        # Build absolute quaternion from ZYX Euler angles
        rot_z = Gf.Rotation(Gf.Vec3d(0, 0, 1), euler_z)
        rot_y = Gf.Rotation(Gf.Vec3d(0, 1, 0), euler_y)
        rot_x = Gf.Rotation(Gf.Vec3d(1, 0, 0), euler_x)
        composed = rot_x * rot_y * rot_z
        cq = composed.GetQuaternion()
        new_q = Gf.Quatd(cq.GetReal(), Gf.Vec3d(cq.GetImaginary()))

        updated = 0
        for prim in world.GetAllChildren():
            if not prim.GetName().startswith(prim_name):
                continue
            xform = UsdGeom.Xform(prim)
            ops = xform.GetOrderedXformOps()

            # Update rotation
            orient_op = next(
                (op for op in ops if op.GetOpType() == UsdGeom.XformOp.TypeOrient),
                None,
            )
            if orient_op is not None:
                orient_op.Set(new_q)
            else:
                orient_op = xform.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
                orient_op.Set(new_q)

            # Apply translation delta (offset change since last save)
            translate_op = next(
                (op for op in ops if op.GetOpType() == UsdGeom.XformOp.TypeTranslate),
                None,
            )
            if translate_op is not None and (delta_x or delta_y or delta_z):
                cur = translate_op.Get(Usd.TimeCode.Default())
                translate_op.Set(Gf.Vec3d(
                    cur[0] + delta_x,
                    cur[1] + delta_y,
                    cur[2] + delta_z,
                ))

            carb.log_warn(
                f"[UsdSpawner] adjustAssetRotation  updated {prim.GetPath()}"
                f"  q={new_q}  translate_delta=({delta_x},{delta_y},{delta_z})"
            )
            updated += 1

        carb.log_warn(
            f"[UsdSpawner] adjustAssetRotation done — {updated} prim(s) updated"
        )

    # ------------------------------------------------------------------

    def on_shutdown(self) -> None:
        self._update_sub = None  # release deferred scan subscription
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()
        carb.log_info("[UsdSpawner] Shutdown")
