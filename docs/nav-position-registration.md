# Navigation Position Registration — Implementation Notes

This document covers all changes made to implement the UI-based camera navigation position
registration feature, including chat-driven navigation sync and the WebRTC streaming port fix.

---

## Feature Overview

Users can open a navigation panel in the web viewer to:
1. Read their current camera position from the Kit viewport
2. Save it with a name and description
3. Navigate back to any saved or built-in location via UI buttons
4. Ask the AI agent ("go to entrance") to navigate to saved locations

---

## Files Changed

### 1. Kit Extension — `camera_navigation.py`

**Path:**
`source/extensions/version37.my_usd_viewer_messaging_extension/version37/my_usd_viewer_messaging_extension/camera_navigation.py`

**What was added:**

- `import json, os` at top
- `NAV_PRESETS_FILE` constant pointing to `nav_presets.json` next to the module
- `_custom_positions: Dict[str, Dict]` — in-memory store for user-registered positions
- `_load_custom_positions()` — loads from `nav_presets.json` on init
- `_save_custom_to_disk()` — persists to `nav_presets.json`
- `save_position(name, location, rotation, description)` — adds/updates a custom position
- `delete_position(name)` — removes a custom position by key
- `clear_custom_positions()` — removes all custom positions
- `get_all_positions_with_metadata()` — merges built-in + custom positions, tagging each with `is_custom: bool`
- `get_custom_positions()` — returns only the custom dict (used by sync helpers)

**Why:** Custom positions need to survive extension restarts via JSON persistence, and need to be
distinguishable from built-in locations in the UI.

---

### 2. Kit Extension — `custom_messaging.py`

**Path:**
`source/extensions/version37.my_usd_viewer_messaging_extension/version37/my_usd_viewer_messaging_extension/custom_messaging.py`

**Outgoing messages registered (Kit → Browser):**

| Message type | Purpose |
|---|---|
| `navPositionsResponse` | Sends full position list after any CRUD operation |
| `cameraPositionResponse` | Sends current camera position query result |

**Incoming event handlers added (Browser → Kit):**

| Event type | Handler | Action |
|---|---|---|
| `getNavPositions` | `_on_get_nav_positions` | Returns all positions (built-in + custom) |
| `registerNavPosition` | `_on_register_nav_position` | Saves position, syncs to backend |
| `deleteNavPosition` | `_on_delete_nav_position` | Deletes position, syncs to backend |
| `clearNavPositions` | `_on_clear_nav_positions` | Clears all custom positions, syncs to backend |
| `getCameraPosition` | `_on_get_camera_position` | Reads current viewport camera and responds |
| `navigateTo` | `_on_navigate_to_direct` | Moves camera to named position |

**Key implementation details:**

- `_dispatch_nav_positions(extra)` — shared helper that calls `get_all_positions_with_metadata()`
  and dispatches `navPositionsResponse` to the browser
- `_read_camera_position_robust()` — uses the viewport API with a world-transform fallback and
  Euler decomposition to return `{location: [x,y,z], rotation: [rx,ry,rz]}` reliably; avoids
  returning `None` silently (which caused the "Reading..." freeze bug)
- Backend sync helpers use `asyncio.ensure_future` + `loop.run_in_executor` to make non-blocking
  HTTP calls to the agent backend:
  - `_sync_nav_position_to_backend(name, location, rotation, description)` — POST
  - `_delete_nav_position_from_backend(name)` — DELETE
  - `_clear_nav_positions_from_backend()` — DELETE all
- `_startup_sync_nav_positions()` method was written but **intentionally not called** from
  `__init__` — it caused HTTP calls during Kit streaming SDK initialization which destabilized
  the WebRTC session.

---

### 3. Web Viewer — `Window.tsx`

**Path:** `omniverse-webviewer/src/Window.tsx`

**Interface added:**

```typescript
interface NavPositionEntry {
    location: number[];
    rotation: number[];
    description?: string;
    is_custom: boolean;
}
```

**State fields added:**

| Field | Type | Purpose |
|---|---|---|
| `navPanelOpen` | `boolean` | Toggle nav panel visibility |
| `navPositions` | `Record<string, NavPositionEntry>` | All positions from Kit |
| `navCurrentPos` | `{location, rotation} \| null` | Camera position just read |
| `navFetchingPos` | `boolean` | Loading state for camera read |
| `navRegName` | `string` | Name input for new position |
| `navRegDesc` | `string` | Description input for new position |
| `navNavigating` | `string \| null` | Key of position being navigated to |

**Methods added:**

- `_navGetCurrentPos()` — sends `getCameraPosition` to Kit, sets 6-second safety timeout to
  clear the loading state if Kit doesn't respond
- `_navRegisterPosition()` — sends `registerNavPosition` with name, description, location, rotation
- `_navDeletePosition(key)` — sends `deleteNavPosition`
- `_navClearAll()` — sends `clearNavPositions` with confirmation guard
- `_navNavigateTo(key, instant)` — sends `navigateTo` with destination key

**Event handlers updated** (`_handleCustomEvent`):

- `navPositionsResponse` — updates `navPositions` state, clears `navNavigating`
- `cameraPositionResponse` — reads flat `{success, location, rotation}` payload, updates
  `navCurrentPos` and clears `navFetchingPos`

**UI panel** (rendered when `navPanelOpen`):

- Toggle button (🗺) in chat header
- **Read Camera Position** button with loading indicator
- **Register** form: name input, description input, Save button (disabled until position is read
  and name is filled)
- **My Positions** list: each entry has Go / Jump (instant) / Delete buttons
- **Built-in Locations** list: Go / Jump buttons
- **Clear All** button at the bottom

---

### 4. Agent Backend — `nav_registry.py` (new file)

**Path:** `omniverse-vs-agent-backend/app/services/nav_registry.py`

A standalone in-memory store that avoids circular imports between `main.py` and `chat_graph.py`.

```python
_positions: dict = {}

def get_all() -> dict   # return all registered positions
def register(name, description, location, rotation)
def delete(name) -> bool
def clear()
```

**Why a separate module:** `chat_graph.py` is imported by `main.py`. If `chat_graph.py` imported
from `main.py`, Python would raise a circular import error. A neutral third module solves this.

---

### 5. Agent Backend — `main.py`

**Path:** `omniverse-vs-agent-backend/app/main.py`

**4 endpoints added** (all use `nav_registry`):

| Method | Path | Action |
|---|---|---|
| `GET` | `/api/nav-positions` | Return all registered positions |
| `POST` | `/api/nav-positions` | Register a position `{name, description, location, rotation}` |
| `DELETE` | `/api/nav-positions/{name}` | Delete one position by name |
| `DELETE` | `/api/nav-positions` | Clear all positions |

These endpoints are called by Kit's `_sync_nav_position_to_backend` / `_delete_nav_position_from_backend` /
`_clear_nav_positions_from_backend` helpers whenever the user saves, deletes, or clears positions
in the UI panel.

---

### 6. Agent Backend — `chat_graph.py`

**Path:** `omniverse-vs-agent-backend/app/agents/chat_graph.py`

**Added:**

```python
def _get_all_nav_locations() -> dict:
    """Merge built-in STORE_LOCATIONS with custom positions from nav_registry."""
    from app.services.nav_registry import get_all as _nav_get_all
    merged = dict(STORE_LOCATIONS)
    merged.update(_nav_get_all())
    return merged
```

**Updated** `find_navigation_destination()`, `find_navigation_destination_llm()`, and
`handle_navigation()` to call `_get_all_nav_locations()` instead of using `STORE_LOCATIONS`
directly.

**Why:** Without this, chat commands like "go to entrance" only searched the hardcoded
`STORE_LOCATIONS` dict and could never find positions the user registered via the UI panel.

---

### 7. Streaming Kit Config — `version37.my_usd_viewer_streaming.kit`

**Path:** `source/apps/version37.my_usd_viewer_streaming.kit`

**Changed:**

```toml
# Fix NVST_R_ERROR_UDP_RTP_SOURCE_OPEN_FAILED_NO_PORTS_AVAILABLE
# Root cause: Omniverse Hub (launched by Kit's hub-client) binds UDP 47998 on startup
# and NVST SDK's default streamPort is also 47998 → conflict.
# Solution: move the streaming ports well outside Hub's range.
[settings.exts."omni.kit.livestream.app".primaryStream]
streamPort = 62000   # UDP port for RTP media (default 47998 conflicts with Hub)
signalPort = 49100   # TCP signaling port (keep at default)
```

**Root cause of the WebRTC error:**

- Kit's kernel contains a built-in `hub-client` Rust library that **always** spawns Omniverse Hub
  as a background daemon when Kit starts.
- Hub grabs **UDP 47998** and holds it even after Kit shuts down (Hub daemonizes itself).
- NVST SDK's default `streamPort` is also **47998** → `bind()` fails →
  `NVST_R_ERROR_UDP_RTP_SOURCE_OPEN_FAILED_NO_PORTS_AVAILABLE`.
- The correct carb settings key is `exts."omni.kit.livestream.app".primaryStream.streamPort`,
  **not** `exts."omni.kit.livestream.webrtc".portRangeStart` (wrong extension, key doesn't exist).

---

## Data Flow

```
Browser UI
  │  getCameraPosition ──────────────────────────────► Kit
  │                           _read_camera_position_robust()
  │  ◄────────────────────────────── cameraPositionResponse (location, rotation)
  │
  │  registerNavPosition ────────────────────────────► Kit
  │                           camera_navigation.save_position()
  │                           nav_presets.json updated
  │                           _sync_nav_position_to_backend() ──► POST /api/nav-positions
  │  ◄────────────────────────────── navPositionsResponse (all positions)
  │
  │  navigateTo ─────────────────────────────────────► Kit
  │                           camera_navigation.navigate_to()

Chat (Browser)
  │  "go to entrance" ──────────────────────────────► Agent Backend
  │                           _get_all_nav_locations()
  │                             = STORE_LOCATIONS + nav_registry.get_all()
  │                           navigate_to action ──────────────────► Kit (via chatResponse)
```

---

## Persistence

- Custom positions are saved to `nav_presets.json` in the Kit extension's Python package directory.
- The agent backend's `nav_registry` is **in-memory only** — it is populated via API calls from
  Kit each time the user registers/deletes a position. On backend restart, positions need to be
  re-registered from the UI (or a future startup sync could be re-enabled).
