# Step 3: Scan the Project

> Part of the **kit-upgrade** skill (see `../SKILL.md` for the workflow). Assumes Step 1 detection has run (`$DEPS_DIR`, `$BUILD` are set). **Only run this step for major-version boundaries you cross** — a pure within-major / feature→production bump skips it.

Run these commands from the project root. Only run scans for the stages that apply to this upgrade. Collect all matches before generating the report.

> **⚠️ Scan scope:** Use `.` (project root) as the search root, not just `source/`. Many projects have `templates/`, `launcher-configs/`, or other directories containing `.kit` files and `extension.toml` files with real dependency declarations. Scanning only `source/` will miss these.
>
> **Windows note:** Commands below use bash syntax. On Windows, replace `for` loops with individual `findstr` or PowerShell `Select-String` commands, or run inside WSL/Git Bash.

### Python / Extension Dependencies

```bash
# === Stage 1 (106→107) ===

# Python 3.10 references (now 3.11)
grep -rn "python3\.10\|python310\|boost_python310" . premake5.lua --include="*.lua" --include="*.sh" --include="*.bat" --include="*.toml"

# Private omni.client API
grep -rn "omni\.client\._omniclient" . --include="*.py"

# carb.imgui (removed — use omni.kit.imgui)
grep -rn "carb\.imgui" . --include="*.py"

# Events 1.0 patterns (payload access, subscription style)
grep -rn "e\.payload\[" . --include="*.py"
grep -rn "create_subscription_to_pop" . --include="*.py"

# nv_usd references in build files
grep -rn "nv_usd" . premake5.lua repo.toml --include="*.lua" --include="*.toml"

# packman XML using a pre-ABI token (should be ${platform_target_abi}).
# NOTE: match BOTH the old ${platform} form (Kit 106) and the intermediate ${platform_target} form —
# the narrower 'platform_target[^_]' pattern misses ${platform}, which is what 106.5 actually uses and
# is a build-verified hard failure on 106->107 (kit-kernel pull: "Package not found ...gl.linux-x86_64").
grep -rnE '\$\{platform(_target)?\}' "$DEPS_DIR" --include="*.xml"

# Toolbar deprecated APIs
grep -rn "omni\.kit\.widget\.toolbar\|omni\.kit\.window\.toolbar" . --include="*.py" --include="*.toml"


# === Stage 2 (107→108) ===

# Python 3.11 references (now 3.12)
grep -rn "python3\.11\|python311\|boost_python311" . premake5.lua --include="*.lua" --include="*.sh" --include="*.bat"

# get_custom_glyph_code (moved to omni.ui)
grep -rn "omni\.kit\.ui.*get_custom_glyph_code" . --include="*.py"

# WindowHandle deprecated usage
grep -rn "WindowHandle" . --include="*.py"

# menu_compatibility (deprecated in 108, removed in 110)
grep -rn "menu_compatibility" . --include="*.py"

# Layer events (Events 1.0 style)
grep -rn "get_event_stream\|create_subscription_to_pop\|carb\.events" . --include="*.py"

# Livestream extension (monolithic — should be split)
grep -rn '"omni\.kit\.livestream"' . --include="*.kit" --include="*.toml"
grep -rn "omni\.services\.livestream\.nvcf" . --include="*.kit" --include="*.toml"

# Livestream settings (old path)
grep -rn "app/livestream\|app\.livestream" . --include="*.kit" --include="*.toml"

# Old omni.kit.ui transitive usage (no longer loaded transitively)
grep -rn "omni\.kit\.ui[^.]" . --include="*.py"


# === Stage 3 (108→109) ===

# NumPy 1.x type aliases (removed in 2.0)
grep -rn "np\.bool[^_]\|np\.int[^0-9_]\|np\.float[^0-9_]\|np\.complex[^0-9_]\|np\.object[^_]\|np\.str[^_]" . --include="*.py"


# === Stage 4 (109→110) ===

# menu_compatibility (now raises TypeError — must remove entirely)
grep -rn "menu_compatibility=" . --include="*.py"

# omni.usd layers deprecated API
grep -rn "get_context()\.get_layers()\|context\.get_layers()" . --include="*.py"

# omni.renderer_capture (deprecated → omni.kit.capture)
grep -rn "omni\.renderer_capture" . --include="*.py"

# USD displayName/displayGroup/hidden deprecated metadata
grep -rn "GetMetadata.*displayName\|SetMetadata.*displayName\|GetMetadata.*hidden\|SetMetadata.*hidden\|GetMetadata.*displayGroup\|SetMetadata.*displayGroup" . --include="*.py"
```

### C++ / Native Code

```bash
# === Stage 1 (106→107) ===

# C++ ABI — check for _GLIBCXX_USE_CXX11_ABI overrides (must be =1)
grep -rn "_GLIBCXX_USE_CXX11_ABI" . --include="*.cpp" --include="*.h" --include="*.cmake"


# === Stage 2 (107→108) ===

# ITokens::setValue (renamed to setValueS)
grep -rn "->setValue(" . --include="*.cpp" --include="*.h"

# carb::detail::defineTupleCommon
grep -rn "carb::detail::defineTupleCommon" . --include="*.cpp" --include="*.h"

# PyObjectVTable::get()->typeName
grep -rn "PyObjectVTable" . --include="*.cpp" --include="*.h"

# acquireInterface (prefer getCachedInterface)
grep -rn "acquireInterface" . --include="*.cpp" --include="*.h"

# carb::extras::Path implicit conversion
grep -rn "carb::extras::Path\|carb::fs::Path" . --include="*.cpp" --include="*.h"

# Assert macros (may need explicit carb/Assert.h now)
grep -rn "CARB_ASSERT\|CARB_FATAL_UNLESS" . --include="*.cpp" --include="*.h"

# Library.h removed functions
grep -rn "getDefaultLibraryPrefix\|getDefaultLibraryExtension" . --include="*.cpp" --include="*.h"

# GfMatrix usage (imprecise overloads removed)
grep -rn "GfMatrix" . --include="*.cpp" --include="*.h"

# ILayers.h inclusion (ABI 1.0 → 1.1 recompile required)
grep -rn "ILayers\.h\|omni/kit/usd/layers" . --include="*.cpp" --include="*.h"

# carb.events const char* usage (deprecated — prefer string_view)
grep -rn "carb::events::\|IEventQueue\|IEvents" . --include="*.cpp" --include="*.h"

# Scalar xform ops — code that iterates over xform ops assuming vector types
grep -rn "GetOrderedXformOps\|xformOp:translate\|xformOp:scale\|xformOp:rotate" . --include="*.cpp" --include="*.h" --include="*.py"


# === Stage 3 (108→109) ===

# Fabric TokenC/PathC (removed; also kUninitializedToken/Path)
grep -rn "TokenC\|PathC\|TokenId\|PathId\|kUninitializedToken\|kUninitializedPath" . --include="*.cpp" --include="*.h"

# carb::cpp17 / carb::cpp20 (merged to carb::cpp)
grep -rn "carb::cpp17\|carb::cpp20" . --include="*.cpp" --include="*.h"

# carb::thread::shared_lock (removed)
grep -rn "carb::thread::shared_lock" . --include="*.cpp" --include="*.h"

# IDictionary::MakeAtPathS (renamed to MakeAtPath)
grep -rn "MakeAtPathS" . --include="*.cpp" --include="*.h"

# compareStringsNoCase (renamed)
grep -rn "compareStringsNoCase" . --include="*.cpp" --include="*.h"

# Logger (superseded by Logger2)
grep -rn "carb::logging::Logger[^2]" . --include="*.cpp" --include="*.h"

# MDL/Neuray usage (ABI 56 → 57 recompile required)
grep -rn "omni\.mdl\|Neuray\|MDL.*SDK" . --include="*.cpp" --include="*.h" --include="*.toml"

# CloudXR / XRCloudXRBindings
grep -rn "CloudXR\|XRCloudXRBindings\|IOpenXRRuntime" . --include="*.cpp" --include="*.h"


# === Stage 4 (109→110) ===

# CARB_CHECK (replaced by CARB_RELEASE_ASSERT)
grep -rn "CARB_CHECK" . --include="*.cpp" --include="*.h"

# carb/Defines.h (split into sub-headers)
grep -rn '#include.*carb/Defines\.h' . --include="*.cpp" --include="*.h"

# IFileSystem raw char* methods
grep -rn "IFileSystem" . --include="*.cpp" --include="*.h"

# ITokens (unsafe methods removed; ITokens 2.0 available)
grep -rn "ITokens\|->resolveString\|->setValue" . --include="*.cpp" --include="*.h"

# optional<bool> / expected<bool> — semantics changed (if(b) now tests presence)
grep -rn "optional<bool>\|expected<bool" . --include="*.cpp" --include="*.h"

# kUnicodeToUtf8Failure / kUnicodeToWideFailure (removed)
grep -rn "kUnicodeToUtf8Failure\|kUnicodeToWideFailure" . --include="*.cpp" --include="*.h"

# g_carbClientName (type changed to zstring_view)
grep -rn "g_carbClientName" . --include="*.cpp" --include="*.h"

# Removed deprecated headers
grep -rn "time/TscClock\.h\|ReplaceCarbAssert\.h\|LogChannelFilterUtils\.h\|WildcardLogChannelFilter\.h" . --include="*.cpp" --include="*.h"

# Deprecated carb/events/IEvents.h include (deprecated in Stage 2, still worth catching in Stage 4)
# Presence causes compile warnings; file may be vestigial if the code already uses carb::eventdispatcher
grep -rn "#include.*carb/events/IEvents" . --include="*.cpp" --include="*.h"

# Hydra 2 settings
grep -rn "hydra2\|hydra\.2\|renderer\.hydra2" . --include="*.kit" --include="*.toml" --include="*.py" --include="*.cpp"

# Ndr/Sdr unified library (includes may need updating)
grep -rn "pxr/usd/ndr\|pxr/usd/sdr\|#include.*Ndr\|Ndr::Node\|Sdr::ShaderNode" . --include="*.cpp" --include="*.h"
```

### Extension Dependency Files

> **Important:** Also scan `templates/`, `launcher-configs/`, and any ETM lock files (e.g. `omni.all.template.extensions.kit`). These contain real dependency declarations and will cause test or runtime failures if they reference removed extensions.

```bash
# === All stages — removed/deprecated extensions ===

# Kit 108 removals
grep -rn "omni\.kit\.extpath\.git" . --include="*.toml" --include="*.kit"

# Kit 108 — monolithic livestream (split into modules)
grep -rn '"omni\.kit\.livestream"' . --include="*.toml" --include="*.kit"
grep -rn "omni\.services\.livestream\.nvcf" . --include="*.toml" --include="*.kit"

# Kit 110 removals (cause cryptic exit-55 dependency solver failures)
for ext in omni.kvdb omni.localcache omni.genproc.core; do
  echo "=== $ext ==="; grep -rn "$ext" . --include="*.kit" --include="*.toml"
done

# Kit 110 silently removed (no deprecation notice)
for ext in "omni.hydra.iray.shadercache.d3d12" "omni.hydra.iray.shadercache.vulkan" "omni.kit.viewport.iray"; do
  echo "=== $ext ==="; grep -rn "$ext" . --include="*.kit" --include="*.toml"
done

# Deprecated (not yet removed — still operational but plan migration)
for ext in "omni.command.usd" "omni.debugdraw" "omni.hydra.iray" "omni.iray.settings.core" \
           "omni.kit.autocapture" "omni.kit.manipulator.viewport" "omni.hydra.scene_api" \
           "omni.renderer_capture" "omni.surface_instancer" "omni.kit.viewport.legacy_gizmos" \
           "omni.kit.widget.nucleus_connector"; do
  echo "=== $ext ==="; grep -rn "$ext" . --include="*.kit" --include="*.toml"
done

# Extensions that need explicit declaration (no longer loaded transitively)
grep -rn "omni\.kit\.manipulator\.prim\.fabric\|omni\.resourcemonitor\|omni\.kit\.ui" . \
  --include="*.py" --include="*.toml"
```

### Config Files

```bash
# Extension registry URLs (must update for Kit 110)
grep -rn "kit-extensions\.ov\.nvidia\.com\|omniverse://" . --include="*.kit"

# Build system (VS version) — also check CI-scoped token overrides
# (e.g. "token:in_ci==true".vs_version may override the default even when the top-level is correct)
grep -rn "vs_version\|vs2019\|vs2017\|v142" repo.toml

# Livestream settings (old path style)
grep -rn "app/livestream" . --include="*.kit" --include="*.toml"

# Kit SDK version pin (use the $DEPS_DIR detected in Step 1)
cat "$DEPS_DIR/kit-sdk.packman.xml"

# mergeMaterials (behavioral default change in 109)
grep -rn "mergeMaterials" . --include="*.kit" --include="*.toml"

# FSD / Fabric Scene Delegate settings
grep -rn "FabricSceneDelegate\|fsd\b" . --include="*.kit" --include="*.toml"
```

### OmniGraph

```bash
# === Stage 2 (107→108) — OmniGraph 3.0 ABI ===
grep -rn "omni\.graph\.core\|omni\.graph\.nodes" . --include="*.toml"

# === Stage 4 (109→110) — deprecated/removed OmniGraph nodes ===

# DeformedPointsToHydra — removed (was part of OmniHydra)
grep -rn "DeformedPointsToHydra" . --include="*.py" --include="*.usd" --include="*.usda"

# OnCustomEvent bundle attributes deprecated
grep -rn "OnCustomEvent" . --include="*.py" --include="*.usd" --include="*.usda"

# Bundle/attribute manipulation nodes deprecated
grep -rn "ArrayGetSize\|AttributeType\|BundleConstructor\|CopyAttribute\|ExtractPrim\|GetAttributeNames\|HasAttribute\|InsertAttribute\|RemoveAttribute\|RenameAttribute" \
  . --include="*.py" --include="*.usd" --include="*.usda"

# Event/render pipeline nodes deprecated
grep -rn "UpdateTickEvent\|GpuInteropCudaEntry\|RenderPreprocessEntry\|RpResourceExample" \
  . --include="*.py" --include="*.usd" --include="*.usda"
```

### Isaac Sim Projects

If the project uses Isaac Sim extensions, scan for the `omni.isaac.*` namespace migration (applies Kit 107+):

```bash
# omni.isaac.* imports (deprecated → isaacsim.*)
grep -rn "omni\.isaac\." . --include="*.py" --include="*.toml" --include="*.kit"

# omni.replicator.isaac (→ isaacsim.replicator.*)
grep -rn "omni\.replicator\.isaac" . --include="*.py" --include="*.toml"

# Dynamic Control Toolbox (removed as compile-time dep)
grep -rn "dynamic_control\|DynamicControl" . --include="*.py" --include="*.cpp" --include="*.h"

# SemanticsAPI (→ UsdSemantics.LabelsAPI)
grep -rn "add_update_semantics\|SemanticsAPI" . --include="*.py"
```

**Isaac Sim namespace mapping (omni.isaac.* → isaacsim.*):**

| Old | New |
|---|---|
| `omni.isaac.core` | `isaacsim.core.api` |
| `omni.isaac.sensor` | `isaacsim.sensors.rtx` / `.physx` / `.physics` |
| `omni.isaac.conveyor` | `isaacsim.asset.gen.conveyor` |
| `omni.isaac.manipulators` | `isaacsim.robot.manipulators` |
| `omni.isaac.ros2_bridge` | `isaacsim.ros2.bridge` |
| `omni.isaac.jupyter_notebook` | `isaacsim.code_editor.jupyter` |
| `omni.isaac.vscode` | `isaacsim.code_editor.vscode` |
| `omni.isaac.lula` | `isaacsim.robot_motion.lula` |
| `omni.replicator.isaac` | `isaacsim.replicator.*` |

---

When the scans are complete, proceed to **Step 4** (`report.md`) to generate the upgrade report.
