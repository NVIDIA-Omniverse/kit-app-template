# Step 5: Apply Fixes

> Part of the **kit-upgrade** skill (see `../SKILL.md` for the workflow). Assumes Step 1 detection has run (`$DEPS_DIR`, `$BUILD` are set).

> **Within-major / feature→production upgrade?** Run **only items 1, 2, 8** below (plus item 3 *if* a feature↔production registry swap is needed), then Step 6 (`validate.md`). **Skip items 4–7** — they apply only when a major boundary is crossed. See "Within-major upgrades" under Step 2 in `../SKILL.md`.

**Get user approval before modifying files.** Then apply in this order (a full major-boundary upgrade runs all eight):

1. **Clear extscache** first: `rm -rf _build/*/release/extscache/`
2. **Update version pin** in `$DEPS_DIR/kit-sdk.packman.xml`
3. **Update registry URLs** in `.kit` files (see `../references/config_changes.json`)
4. **Replace deprecated APIs** using patterns in `../references/api_replacements.json` — these are safe regex replacements
5. **Remove deprecated extension deps** from `extension.toml` and `.kit` files (see `../references/removed_extensions.json`).

   **For 109→110 specifically:** the following six extensions are removed with **no deprecation notice**, and any lingering reference causes a cryptic `exit code 55` dependency-solver failure. They MUST be removed from every `.kit` (and `extension.toml`) file:
   - `omni.kvdb`
   - `omni.localcache`
   - `omni.genproc.core`
   - `omni.hydra.iray.shadercache.d3d12`
   - `omni.hydra.iray.shadercache.vulkan`
   - `omni.kit.viewport.iray`

   ⚠️ **Check the generated version-lock block, not just `[dependencies]`.** In application `.kit` files these names almost always appear in the auto-generated `[settings.app.exts] enabled = [...]` lock (pinned at the old version, e.g. `omni.kvdb-109.0.10`), **not** the hand-authored dependency list. **Clearing extscache (step 1) does NOT remove them** — you must regenerate the lock: delete the `# BEGIN GENERATED PART` … `# END GENERATED PART` block (the `.kit` says "Remove from 'BEGIN' to 'END' to regenerate") and run `$BUILD precache_exts -c release` so it is rebuilt without the removed extensions. Then confirm a clean rebuild (the version stamp should advance to 110 and the six names should be gone). (If you are working in an internal `kit-app-template` checkout, the ETM lock file `templates/omni.all.template.extensions.kit` and any internal-registry entries are KAT-internal — wrapped in `# AUTOREMOVE` and stripped from external releases by `repo stage_for_github` — so external customer projects will not contain them.)
6. **Add explicit deps** where transitive loading was removed: `omni.kit.ui`, `omni.resourcemonitor`, `omni.kit.manipulator.prim.fabric`
7. **Update build config** in `repo.toml` (VS version, MSVC version, Windows SDK — see `../references/config_changes.json`)
8. **Trigger C++ rebuild** — ABI breaks at every stage require recompiling all native extensions

**Auto-fixable patterns** (use `sed` or editor find/replace with regex):
- `carb::detail::defineTupleCommon` → `carb::cpp::defineTupleCommon`
- `->setValue(` → `->setValueS(`
- `carb::cpp17::` → `carb::cpp::`
- `carb::cpp20::` → `carb::cpp::`
- `carb::thread::shared_lock` → `std::shared_lock`
- `MakeAtPathS` → `MakeAtPath`
- `compareStringsNoCase` → `caseInsensitiveCompare`
- `CARB_CHECK(` → `CARB_RELEASE_ASSERT(`  (also add ", \"assertion failed\""  argument)
- `omni.kit.ui.get_custom_glyph_code` → `omni.ui.get_custom_glyph_code`
- `context.get_layers()` → `omni.kit.usd.layers.get_layers()`
- `import omni.renderer_capture` → `import omni.kit.capture`
- `time/TscClock.h` → `clock/TscClock.h`

**Manual-only changes** (require human judgment):
- Carbonite Events 2.0 migration (dispatch model, payload access)
- NumPy 2.x type alias replacements (context-dependent)
- Cross-DLL mimalloc ownership audit (Windows)
- IFileSystem / ITokens 2.0 opt-in
- OmniGraph bundle node rewrites
- Hydra 2 / multi-node settings removal
- optional<bool> / expected<bool> if-test replacement

---

When fixes are applied, proceed to **Step 6** (`validate.md`).
