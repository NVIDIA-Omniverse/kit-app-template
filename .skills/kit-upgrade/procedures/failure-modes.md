# Failure Mode Diagnosis

> Part of the **kit-upgrade** skill (see `../SKILL.md` for the workflow). Use this when the user has **already** upgraded and has a specific error. `$DEPS_DIR` / `$BUILD` refer to the values detected in Step 1 (in `../SKILL.md`).

### Exit Code 55 (Dependency Solver Failure)
**Cause:** Removed extension still declared as a dependency, or stale extscache.
**Fix sequence:**
1. Clear extscache: `rm -rf _build/*/release/extscache/`
2. Search for removed extension names in `.kit` and `extension.toml` files (see `../references/removed_extensions.json`)
3. For Kit 110: check for `omni.kvdb`, `omni.localcache`, `omni.genproc.core`, `omni.hydra.iray.shadercache.*`, `omni.kit.viewport.iray`
4. Re-run `precache_exts`

### Build Fails with Undefined Symbol / Missing Method
**Cause:** ABI break — extension was compiled against an older version.
**Fix:** Recompile the extension against the current Kit SDK. Every stage has at least one ABI break.

### Runtime Crash on DLL Load (Windows)
**Cause after Stage 3:** mimalloc cross-DLL heap mismatch. Memory allocated on one side of a DLL boundary freed on the other.
**Fix:** Audit allocation ownership. Use `kit-sysalloc.exe` for compatibility testing.

### Python TypeError: unexpected keyword argument 'menu_compatibility'
**Cause (Stage 4):** `menu_compatibility` parameter removed from `ui.Menu` and `ui.Separator`.
**Fix:** Remove the `menu_compatibility=` argument from all call sites.

### Extension Loads But APIs Return None / AttributeError
**Cause:** Transitive loading of `omni.kit.ui`, `omni.resourcemonitor`, or `omni.kit.manipulator.prim.fabric` was removed.
**Fix:** Add explicit dependency in `extension.toml`.

### Render Output Differs (No Code Changes)
**Cause after Stage 3:** DomeLight orientation changed (USD 25.05), FSD enabled by default, or `mergeMaterials` default changed.
**Diagnosis:**
- Check for DomeLights in the scene: `grep -rn "DomeLight" . --include="*.usd" --include="*.usda"`
- Check FSD setting: `grep -rn "FabricSceneDelegate\|fsd" . --include="*.kit" --include="*.toml"`
- Check `mergeMaterials`: `grep -rn "mergeMaterials" . --include="*.kit" --include="*.toml"`

### if (optional_bool) No Longer Works (C++)
**Cause (Stage 4):** `optional<bool>` / `expected<bool, E>` now tests for *presence* in an if-condition, not the stored value.
**Fix:** Replace `if (b)` with `if (b.has_value() && b.value())`

### Build Fails in a Loop / the Same Error Repeats
**Cause:** Almost always a **stale toolchain** (Step 2.5 not applied — see `toolchain.md`) or a wrong assumption about the project's layout/build system — *not* the source code.
**Rule — do not keep editing source and rebuilding.** If the same build error recurs after **2 attempts**, STOP and re-check the fundamentals before changing any more code:
1. Is the **toolchain** aligned to the target Kit line? (Step 2.5, `toolchain.md` — the #1 cause of build loops.)
2. Is `$DEPS_DIR` the **actual** deps location and `$BUILD` the project's **actual** build entrypoint? (Step 1 in `../SKILL.md`.)
3. Did you do a **clean** rebuild (`$BUILD build --rebuild -r`), not just clear extscache? (Step 6, `validate.md`.)

Surface the exact error and these three checks to the user rather than looping — repeated speculative edits burn tokens and rarely fix a toolchain/layout problem.

### Project Uses a Custom / Integrated Build System
**Cause:** The project wraps or embeds the Kit build system in its own tooling, so `./repo.sh` / `repo.bat` don't exist or aren't the real entrypoint (common for customer integrations).
**Fix:** Do **not** fabricate `./repo.sh` commands. Use the `$BUILD` detected in Step 1 (check `repo.toml`, `Makefile`/`CMakeLists.txt`, `package.json` scripts, CI config, or ask the user). The upgrade steps (kernel pin, **toolchain update**, lock regen) still apply — invoke them through `$BUILD`.

### deps Directory Not Where Expected
**Cause:** The project layout differs from the SDK template, or the deps directory moved between releases (e.g. `deps/` at the project root vs under `tools/`).
**Fix:** Re-run the Step 1 detection (in `../SKILL.md`) to set `$DEPS_DIR`, then use it everywhere. Never hardcode `tools/deps/`.
