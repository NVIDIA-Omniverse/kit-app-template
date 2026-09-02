# Important Notes by Stage

> Part of the **kit-upgrade** skill (see `../SKILL.md` for the workflow). Per-stage reference for the breaking changes summarized in the Step 2 migration table. Read the stages that apply to the boundaries you cross.

### Stage 1: 106 → 107

- **Rebuild required** — Linux ABI changed (`_GLIBCXX_USE_CXX11_ABI=0` → `=1`). All prebuilt `.so` files will fail to load.
- **packman XML token**: Update the kit-kernel pin token to `${platform_target_abi}` in all `.packman.xml` files. Kit 106 uses the **`${platform}`** form (not `${platform_target}`); both must become `${platform_target_abi}`. *Build-verified:* leaving the old token makes the kit-kernel pull fail immediately with `Package not found on specified remote servers (…gl.linux-x86_64.release)`, because Kit 107's kernel is published only under the ABI string (`manylinux_2_35_x86_64`), not `linux-x86_64`.
- **Bump the repo toolchain too (required, easy to miss)** — see **Step 2.5** (`toolchain.md`): the token fix alone is **insufficient** — `${platform_target_abi}` only resolves to the ABI string under the newer `repo_man`. Update `$DEPS_DIR/repo-deps.packman.xml` to the 107-era tooling (`repo_man`, `repo_build`, `repo_kit_tools`, `repo_kit_template`, `repo_usd`) and the packman bootstrap. *Build-verified:* under 106.5's `repo_man` 1.86.0 the token still resolves to `linux-x86_64`; after the toolchain bump it resolves to `manylinux_2_35_x86_64` and the pull succeeds.
- **Carbonite Events 2.0**: The event system changed from push/pump to dispatch. No explicit pump calls needed. Python payload access changed from `e.payload['key']` to `e['key']`.
- **C++17 is now available** explicitly in Premake via `cppdialect = "C++17"`.

### Stage 2: 107 → 108

- **Kit 108 was never publicly released.** These changes still apply when upgrading 107→109.
- **Python 3.12** replaces 3.11. Update all Premake configs, CI configs, and boost_python links.
- **OpenUSD 25.02**: All C++ extensions linking OpenUSD must rebuild. GfMatrix imprecise overloads removed.
- **Livestream modularization**: `omni.kit.livestream` (monolithic) → `omni.kit.livestream.app` + `.aov` + `.core`. `omni.services.livestream.nvcf` → `omni.services.livestream.session`. Settings paths changed — see `../references/config_changes.json`.
- **Transitive deps removed**: `omni.kit.ui`, `omni.resourcemonitor`, `omni.kit.manipulator.prim.fabric` must now be declared explicitly.
- **ILayers ABI 1.0 → 1.1**: Recompile all extensions including `ILayers.h`.
- **USD scalar xform ops**: OpenUSD now supports scalar ops (e.g., `xformOp:translateX`). Code iterating over xform ops that assumes all are vector types may behave incorrectly.

### Stage 3: 108 → 109

- **CUDA 12.4.1 driver requirement**: Linux minimum 550.54.15, Windows minimum 551.78. Apps fail to start with older drivers.
- **NumPy 2.x**: Many breaking changes. On Windows, the default integer type changed from `int32` to `int64` — can cause silent correctness issues.
- **Fabric ABI break**: Even if no source changes needed (no TokenC/PathC usage), all extensions including Fabric headers must recompile — `Token`/`Path` became trivially copyable, which is a binary ABI change. Use `token.isNull()` instead of `kUninitializedToken`.
- **mimalloc (Windows)**: Cross-DLL allocation/free pairs that cross a DLL boundary may now crash. Use `kit-sysalloc.exe` for compatibility testing.
- **mergeMaterials**: Default changed — can cause significant load time regression with no code error. Set explicitly.
- **FSD default on**: If previously disabled FSD, test render output carefully.
- **DomeLight orientation**: USD 25.05 changed the default orientation. Visual change only — no code error. Use `UpgradeUsdLuxLightsCommand` for assisted migration.

### Stage 4: 109 → 110

- **Clear extscache first** — stale Kit 109 entries cause exit-55 dependency solver failure.
- **Silent extension removals**: `omni.kvdb`, `omni.localcache`, `omni.genproc.core`, `omni.hydra.iray.shadercache.d3d12`, `omni.hydra.iray.shadercache.vulkan`, `omni.kit.viewport.iray` — all removed with no deprecation notice. First symptom is a cryptic exit-55 dependency solver failure. **Remove every reference from `.kit`/`extension.toml` files — including the auto-generated `[settings.app.exts] enabled = [...]` version-lock block, where they usually hide pinned at the old version (clearing extscache alone won't drop them; regenerate the lock with `precache_exts` — see Step 5, item 5 in `apply-fixes.md`). Also scan `templates/` and ETM lock files** — these are easily missed by `source/`-only scans.
- **DomeLight orientation (inherited from Stage 3)**: If the project contains DomeLights and was not verified during a previous Stage 3 upgrade, the USD 25.05 orientation change is a permanent behavioral difference. Search with `grep -rn 'DomeLight' . --include='*.py' --include='*.usd'` and use `UpgradeUsdLuxLightsCommand` if scenes were not migrated.
- **`optional<bool>` semantics**: `if(b)` now tests *presence*, not *value*. Code that previously worked may now be wrong silently.
- **`g_carbClientName`**: Type changed to `zstring_view`. Any direct string assignment or comparison breaks.
- **Hydra 2 removed**: No migration path. Hydra 1 (Storm) and RTX remain.
- **OmniGraph bundle nodes**: Large set of bundle/attribute manipulation nodes deprecated. Deprecation warnings visible in editor from Kit 110.1+. `AttributeType` → `GetAttributeType`, `ArrayGetSize` → `ArrayLength`, `ExtractPrim` → `ReadPrim`, `GetAttributeNames` → `ReadPrimAttributes`, `InsertAttribute` → `WritePrimAttribute`. `BundleConstructor`, `RemoveAttribute`, `RenameAttribute` have no direct replacement — redesign graphs.
- **OpenUSD 25.11**: All C++ extensions linking OpenUSD must rebuild. Ndr/Sdr libraries consolidated — update include paths.
- **VS2022 required** on Windows (was VS2019). Update `repo.toml`.
- **New extensions in Kit 110**: `omni.grpc.lib`, `omni.protobuf.lib`, `omni.sensors.nv.*` (camera/lidar/radar/ultrasonic/ids/wpm), `omni.kit.xr.core` — available for use in Kit 110 apps.
