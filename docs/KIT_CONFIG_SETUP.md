# Kit App Configuration — `usd_config.json` Setup Guide

Every extension that handles USD spawning reads a `usd_config.json` file that sits next to `usd_spawner.py`. When setting up the Kit app on a new machine, **this is the only file you need to edit** — no Python code changes are required.

---

## Where the file lives

| Extension | Config path |
|---|---|
| Active PIPC extension (e.g. `version54`) | `source/extensions/version54.my_usd_viewer_messaging_extension/version54/my_usd_viewer_messaging_extension/usd_config.json` |
| Shashika dev extension | `source/extensions/shashika.my_usd_viewer_messaging_extension/shashika/my_usd_viewer_messaging_extension/usd_config.json` |
| New extension template | `templates/extensions/usd_viewer.messaging/template/{{python_module_path}}/usd_config.json` |
| 711 bot extension | `source/extensions/pic.711bot_usd_viewer_messaging_extension/pic/711bot_usd_viewer_messaging_extension/usd_config.json` |

---

## Variable Reference

```json
{
  "usd_base":   "/path/to/primary/usd/folder",
  "usd_assets": "/path/to/USD-Assets/folder",

  "inventory_file":   "/path/to/asset_list_shop_already.json",
  "stage_prims_file": "/path/to/stage_prims.json",

  "spawn_height_offset": 0
}
```

### `usd_base`
**Required.** Absolute path to the folder containing the original 61-asset USD library (`.usdz` files).

In this workspace:
```
/workspace/shashika-ws/github-ws/omniverse-vs-agent-backend/usd
```

On a new machine, point this to wherever you copied that `usd/` folder.

---

### `usd_assets`
**Required for new assets.** Absolute path to the `USD-Assets` folder containing the 11 additional assets (Lays, Doritos variants, Cheetos variants, Wine & Liquor bottles).

In this workspace:
```
/workspace/shashika-ws/github-ws/usd-ws/USD-Assets
```

Assets in this folder are mapped to `ASSET_LIBRARY` in `usd_spawner.py` automatically — Kit will look here when the agent requests one of the new keys (e.g. `cheetos_puffs`, `lays_bags`).

---

### `inventory_file`
**Required.** Absolute path to the JSON file where Kit writes the list of products currently placed in the scene. The agent backend reads this file to answer questions like "what's on the shelf?".

In this workspace:
```
/workspace/shashika-ws/github-ws/omniverse-vs-agent-backend/asset_list_shop_already.json
```

Must be the **same path** set in the backend's `.env` → `INVENTORY_FILE`.

---

### `stage_prims_file`
**Required.** Absolute path to the JSON file that tracks all spawned USD prims currently on the stage. Used by the agent backend to resolve "delete this" and "replace all X" commands.

In this workspace:
```
/workspace/shashika-ws/github-ws/omniverse-vs-agent-backend/stage_prims.json
```

Must be the **same path** set in the backend's `.env` → `STAGE_PRIMS_FILE`.

---

### `spawn_height_offset`
**Optional.** Extra height (in cm) added to every spawned asset along the up-axis. Compensates for models whose USD origin is at their centre rather than their base.

- Default: `0`
- The 711 bot extension uses `80` because the 711 store scene's floor is elevated

---

### `floor_z` / `floor_y` *(optional override)*
Only needed if auto-detection of floor level is unreliable for your scene.

- `floor_z` — pins floor level for Z-up scenes (e.g. the 711 shop)
- `floor_y` — pins floor level for Y-up scenes (e.g. PIPC)

If not set, Kit detects the floor by reading the `/World/Floor` prim translation, then falls back to `0.0`.

---

## Example — New Machine Setup

1. Copy the `usd/` folder from the original machine to the new one, e.g. `/home/user/usd-assets/usd/`
2. Copy the `USD-Assets` folder, e.g. `/home/user/usd-assets/USD-Assets/`
3. Update `usd_config.json` in the active extension:

```json
{
  "usd_base":   "/home/user/usd-assets/usd",
  "usd_assets": "/home/user/usd-assets/USD-Assets",

  "inventory_file":   "/home/user/omniverse-vs-agent-backend/asset_list_shop_already.json",
  "stage_prims_file": "/home/user/omniverse-vs-agent-backend/stage_prims.json",

  "spawn_height_offset": 0
}
```

4. Update the backend `.env` to match the same `inventory_file` and `stage_prims_file` paths (see `omniverse-vs-agent-backend/docs/ENV_SETUP.md`).

5. Reload the extension in Kit's Extension Manager (disable → enable) — no rebuild needed.

---

## Which extension is currently active?

Check the Kit app's `premake5.lua` or look at the Extension Manager inside the running Kit app. The active extension name appears in Kit's log output, e.g.:

```
[version54.my_usd_viewer_messaging_extension.usd_spawner] replaceAllUsdRequest ...
```

Only the **active extension's** `usd_config.json` needs to be updated. The template's config is used only when generating a new extension with `repo template`.
