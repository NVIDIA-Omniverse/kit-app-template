# Feature: Transform Adjustment, Scale Support, and Z-Up Spawn Fix

## Overview

Three related features were added across the Kit extension (Python) and the browser frontend (TypeScript):

1. **Per-asset scale correction** — spawn-time and live scale adjustments saved to disk
2. **Unified Transform Adjustment Panel** — rotation, translation, and scale merged into one UI panel
3. **Z-up coordinate system support** — spawn position correctly lands on the floor in both Y-up and Z-up USD scenes

All changes were applied to:
- `source/extensions/shashika.my_usd_viewer_messaging_extension/` (live extension)
- `templates/extensions/usd_viewer.messaging/template/` (new-extension template)
- `source/extensions/pic.711bot_usd_viewer_messaging_extension/` (711 shop extension, new file)

---

## 1. Per-Asset Scale Correction

### Files changed
- `usd_spawner.py` (shashika extension, template, 711 extension)

### What changed

**New constants and helpers**
```python
_SCALE_CORRECTIONS_PATH = os.path.join(os.path.dirname(__file__), "scale_corrections.json")

def _load_scale_corrections() -> dict: ...
def _save_scale_corrections(corrections: dict) -> None: ...
```

**UsdSpawner `__init__`**
- Loads `self._scale_corrections = _load_scale_corrections()` on startup
- Registers the `adjustAssetScale` event listener

**`_spawn_usd()` — applies saved scale on the outer Xform**
```python
if prim_name in self._scale_corrections:
    sc = self._scale_corrections[prim_name]
    sx, sy, sz = sc["scale_x"], sc["scale_y"], sc["scale_z"]
    if sx != 1.0 or sy != 1.0 or sz != 1.0:
        xform.AddScaleOp(UsdGeom.XformOp.PrecisionFloat).Set(Gf.Vec3f(sx, sy, sz))
```
The outer Xform carries the user scale; the `/Ref` child still carries the fixed 100× unit-conversion scale.

**New handler `_on_adjust_asset_scale()`**
- Receives `{ prim_name, scale_x, scale_y, scale_z }` from the browser
- Persists to `scale_corrections.json`
- Finds all `/World/*` prims matching the name and sets/adds `xformOp:scale` live

**Persistence file format (`scale_corrections.json`)**
```json
{
  "recycle_bin": { "scale_x": 1.5, "scale_y": 1.5, "scale_z": 1.5 },
  "lipton_milktea": { "scale_x": 1.0, "scale_y": 1.0, "scale_z": 1.0 }
}
```

---

## 2. Unified Transform Adjustment Panel

### Files changed
- `omniverse-webviewer/src/Window.tsx`

### What changed

**Before:** Two separate toolbar buttons — one for rotation/translation, one for scale — opening two independent panels.

**After:** One toolbar button (rotate icon) opens a single scrollable "Transform Adjustment" panel containing all three sections.

**AppState type merged**
```typescript
rotationAdjust: {
  key: string;
  x: number; y: number; z: number;    // Euler rotation (°)
  ox: number; oy: number; oz: number; // Translation offset (cm)
  sx: number; sy: number; sz: number; // Scale multiplier
  uniform: boolean;                   // Lock all scale axes together
};
```
The old separate `scaleAdjust` / `scalePanelOpen` state was removed.

**Uniform scale lock**
```typescript
const setScale = (axis: 'sx' | 'sy' | 'sz', val: number) => {
    if (adj.uniform) {
        this.setState(prev => ({ rotationAdjust: { ...prev.rotationAdjust, sx: val, sy: val, sz: val } }));
    } else {
        this.setState(prev => ({ rotationAdjust: { ...prev.rotationAdjust, [axis]: val } }));
    }
};
```

**Panel layout (top → bottom)**
| Section | Color | Controls |
|---|---|---|
| Asset selector | — | dropdown shared by all sections |
| Rotation (°) | cyan `#00c2ff` | X / Y / Z sliders + Apply Rotation & Translation + Reset |
| Translation Offset (cm) | cyan `#00c2ff` | X / Y / Z sliders (part of the same Apply button) |
| Scale | green `#76e3a0` | Uniform checkbox + X / Y / Z sliders (0.1 – 5.0) + Apply Scale + Reset Scale |

**Messages sent**
- Apply Rotation & Translation → `adjustAssetRotation` event `{ prim_name, euler_x/y/z, offset_x/y/z }`
- Apply Scale → `adjustAssetScale` event `{ prim_name, scale_x/y/z }`

---

## 3. Z-Up Coordinate System Support for Spawn Positioning

### Files changed
- `usd_spawner.py` (shashika extension, template, 711 extension — new file)

### Problem

`_compute_world_position()` hardcoded the floor as `Y = 0`:
```python
t = -origin[1] / direction[1]
return Gf.Vec3d(hit[0], 0.0, hit[2])
```
In a Z-up scene (e.g. the 711 shop) `Y = 0` is a vertical plane, not the floor.  
The ray intersection returned a point far from the actual floor, so spawned objects appeared below the floor surface.

### Fix — new helpers

**`_detect_up_axis()`** — reads stage metadata:
```python
def _detect_up_axis(self) -> str:
    stage = omni.usd.get_context().get_stage()
    up = stage.GetMetadata("upAxis")
    return str(up).upper() if up else "Y"
```

**`_get_floor_level(up_axis)`** — priority order:
1. `floor_z` / `floor_y` key in `usd_config.json`
2. Translation of `/World/Floor` prim along the up axis
3. `0.0` fallback

**`_compute_world_position()` — axis-aware plane intersection**
```python
if up_axis == "Z":
    t = (floor_level - origin[2]) / direction[2]
    return Gf.Vec3d(hit[0], hit[1], floor_level)   # Z-up: lock Z to floor
else:
    t = (floor_level - origin[1]) / direction[1]
    return Gf.Vec3d(hit[0], floor_level, hit[2])   # Y-up: lock Y to floor
```

**Floor-snap in `_spawn_usd()` — axis-aware**
```python
up_idx = 2 if up_axis == "Z" else 1   # Z index for Z-up, Y index for Y-up
v_min = rng.GetMin()[up_idx]
if v_min < floor_level - 0.5:
    cur = list(translate_op.Get())
    cur[up_idx] += floor_level - v_min
    translate_op.Set(Gf.Vec3d(*cur))
```

### Optional config override (`usd_config.json`)
```json
{
  "floor_z": 0.0
}
```
Set `floor_z` (Z-up) or `floor_y` (Y-up) to pin the floor level without relying on prim detection.

---

## 4. 711 Shop — New USD Spawner Extension

### Files added
- `source/extensions/pic.711bot_usd_viewer_messaging_extension/pic/711bot_usd_viewer_messaging_extension/usd_spawner.py`
- `source/extensions/pic.711bot_usd_viewer_messaging_extension/pic/711bot_usd_viewer_messaging_extension/usd_config.json`

### Files changed
- `source/extensions/pic.711bot_usd_viewer_messaging_extension/pic/711bot_usd_viewer_messaging_extension/extension.py`

The 711 shop extension previously had no USD spawn support.  
`UsdSpawner` was created from scratch for this extension incorporating the Z-up fix from day one.

**Asset library root paths** (from `usd_config.json`):
```json
{
  "usd_common": ".../7eleven-v2/.../Common Asset Repo",
  "usd_scans":  ".../7eleven-v2/.../USD assets/usd_scans",
  "usd_assets": ".../7eleven-v2/.../usdz_assets"
}
```

**Events handled** (identical contract to the shashika extension):
| Event | Direction | Description |
|---|---|---|
| `spawnUsdRequest` | browser → Kit | Spawn asset at clicked screen position |
| `deleteUsdRequest` | browser → Kit | Remove a spawned prim |
| `replaceUsdRequest` | browser → Kit | Swap a prim with a different asset |
| `adjustAssetRotation` | browser → Kit | Update Euler rotation + translation offset |
| `adjustAssetScale` | browser → Kit | Update scale correction |
| `spawnUsdResponse` | Kit → browser | Spawn result + world position |
| `deleteUsdResponse` | Kit → browser | Delete result |
| `replaceUsdResponse` | Kit → browser | Replace result |

**`extension.py` updated** to instantiate `UsdSpawner` alongside existing managers:
```python
from .usd_spawner import UsdSpawner
...
self._usd_spawner: UsdSpawner = UsdSpawner()
```

---

## 5. Template Propagation

All changes above were also applied to:

```
templates/extensions/usd_viewer.messaging/template/{{python_module_path}}/usd_spawner.py
```

New extensions generated with `repo template` will automatically include:
- Scale correction support
- Z-up aware spawn positioning
- `usd_config.json` (already present in template directory)
