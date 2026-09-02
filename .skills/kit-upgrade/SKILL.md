---
name: kit-upgrade
description: "Scan and upgrade Omniverse Kit SDK projects between versions. Analyzes project files, identifies breaking changes, deprecated APIs, and removed extensions specific to the customer's code. Provides a personalized upgrade plan with file:line references and auto-fix suggestions. Covers Kit 106→107→108→109→110."
---

# Kit SDK Upgrade Skill

Guide a developer through upgrading their Omniverse Kit project from one version to another.

This skill is a lean workflow router. **Steps 1 and 2 (detect the project, decide the migration path) are inline below** — they are always needed. The detail for the remaining steps (2.5–6) lives in `procedures/`, and the structured change data in `references/`. **Read each procedure file when the workflow sends you to it** — do not try to hold them all in context at once.

## When to Use
- User asks to upgrade their Kit project/app/extension
- User asks about Kit breaking changes or migration
- User is hitting errors after changing their Kit SDK version
- User has a broken build or runtime failure after a version bump

---

## Quick Orientation

Pick the entry point that matches the request:
1. **First-time upgrade scan** → start at Step 1 below and follow the workflow in order.
2. **Already upgraded, now has a build/runtime error** → go straight to `procedures/failure-modes.md`, diagnose, then apply the relevant Stage's fixes from `procedures/stage-notes.md`.
3. **Just wants a list of breaking changes** → do Step 1, then run the scans in `procedures/scan.md` for their migration path and present the report from `procedures/report.md`.

**Structured data — `references/` (JSON):**
- `breaking_changes.json` — All breaking changes with search patterns and fixes (80+ entries)
- `removed_extensions.json` — Extensions removed/deprecated by version
- `api_replacements.json` — 1:1 API replacements (auto-fixable with regex)
- `config_changes.json` — Settings and config changes between versions
- `toolchain.json` — The `repo_*` build-tool set and how to find target versions

**Detailed procedures — `procedures/` (Markdown, read on demand):**
| Step | File | Purpose |
|---|---|---|
| 2.5 | `procedures/toolchain.md` | Update the build toolchain (highest-impact) |
| 3 | `procedures/scan.md` | Scan the project for breaking changes |
| 4 | `procedures/report.md` | Generate the upgrade report |
| 5 | `procedures/apply-fixes.md` | Apply fixes |
| 6 | `procedures/validate.md` | Clean-rebuild and validate |
| — | `procedures/failure-modes.md` | Diagnose a specific post-upgrade error |
| — | `procedures/stage-notes.md` | Per-stage breaking-change reference |

---

## Step 1: Detect Current Version, Project Layout & Build System

Check these files in the project root (in order of reliability):

```bash
# Kit SDK version pin (most reliable)
cat tools/deps/kit-sdk.packman.xml | grep 'version='
cat deps/kit-sdk.packman.xml 2>/dev/null | grep 'version='

# Generated version block in .kit app files
grep -rn "Kit SDK Version" source/apps/*.kit

# Extension registry URL reveals the version series
grep -rn 'registries' source/apps/*.kit | grep -o 'kit/prod/[0-9]*'

# Kit version targeting in extensions
grep -rn 'kit_sdk_version' source/extensions/*/config/extension.toml
```

> **Note:** The version in `kit-sdk.packman.xml` is the authoritative pin. The `# Kit SDK Version:` comment in `.kit` files reflects the last lock-file regeneration and may differ from the pin during an in-progress upgrade.

Version string format: `110.1.0+feature.${platform_target_abi}.${config}`
- First number (110) = major Kit version

**If no version pin is found:** Check git history (`git log --oneline -20 -- tools/deps/ deps/`) or ask the user what Kit version they are currently running. (Layout detection below has not run yet, so scope the log to both candidate deps locations.)

### Detect project layout and build system

Kit projects do **not** all use the SDK template layout, and the layout can differ between releases and project types — for example, `deps/` may sit at the project **root** in one release and under **`tools/`** in another (even between two point releases of the same major line). Projects also frequently **wrap or integrate the Kit build system into their own tooling**. Detect the layout and build entrypoint **once**, then reuse them everywhere below — **never assume `tools/deps/` or `./repo.sh`**.

```bash
# 1. deps directory (holds kit-sdk.packman.xml + repo-deps.packman.xml)
if   [ -f tools/deps/kit-sdk.packman.xml ]; then DEPS_DIR=tools/deps
elif [ -f deps/kit-sdk.packman.xml ];       then DEPS_DIR=deps
else f=$(find . -name kit-sdk.packman.xml -not -path './_*' | head -1); DEPS_DIR=${f:+$(dirname "$f")}; fi
echo "DEPS_DIR=${DEPS_DIR:-<not found — ask the user where kit-sdk.packman.xml lives>}"

# 2. build entrypoint — the standard repo wrapper, if present
if   [ -f ./repo.sh ];  then BUILD='./repo.sh'
elif [ -f ./repo.bat ]; then BUILD='repo.bat'
else BUILD=''; fi   # empty => custom / integrated build (see below)
echo "BUILD=${BUILD:-<custom/integrated>}"
```

**If `BUILD` is empty, the project uses a custom or integrated build system** (common — many customers embed the Kit build inside their own). Do **not** fabricate `./repo.sh` calls. Find the real build command (check `repo.toml`, `Makefile`/`CMakeLists.txt`, `package.json` scripts, CI config, or the project README) or ask the user how they build. The upgrade work below (kernel pin bump, **toolchain update**, lock regeneration) still applies — you just invoke it through the project's own entrypoint. Record it as `$BUILD`.

> **From here on (and in every procedure file), use `$DEPS_DIR` and `$BUILD` in every command.** Where a document still shows a literal `tools/deps/` or `./repo.sh`, substitute the detected values.
>
> **These are not guaranteed to persist across shells.** If you run each fenced block in a fresh subshell, `$DEPS_DIR`/`$BUILD` will be unset. So do **one** of: (a) textually replace `$DEPS_DIR` and `$BUILD` with the literal detected paths (e.g. `tools/deps`, `./repo.sh`) in every command you run, or (b) re-run the two detection blocks above at the top of each new shell session. Do **not** run a later block assuming the variables are still set.

---

## Step 2: Determine Migration Path

Kit versions must be upgraded **in sequence**. **Kit 108 was never publicly released** — its changes are folded into the 107→109 path. When upgrading 107→109 you must still address Stage 2 (107→108) changes.

| From → To | Stages to apply |
|---|---|
| 106 → 107 | Stage 1 only |
| 106 → 109 | Stage 1 + 2 + 3 |
| 106 → 110 | Stage 1 + 2 + 3 + 4 |
| 107 → 109 | Stage 2 + 3 |
| 107 → 110 | Stage 2 + 3 + 4 |
| 109 → 110 | Stage 4 only |

**Stage summary** (full per-stage detail is in `procedures/stage-notes.md`):
- **Stage 1 (106→107):** Python 3.10→3.11, Linux ABI (_GLIBCXX_USE_CXX11_ABI=1), nv_usd rename, Carbonite Events 2.0
- **Stage 2 (107→108):** Python 3.11→3.12, OpenUSD 25.02, Carbonite 208.3, OmniGraph 3.0, livestream split, GPU Turing min, ILayers ABI 1.0→1.1
- **Stage 3 (108→109):** NumPy 2.x, CUDA 12.4.1, Fabric API revision, mimalloc, FSD default on, DomeLight orientation, MDL ABI 57
- **Stage 4 (109→110):** OpenUSD 25.11, Carbonite 210, Hydra 2 removed, OmniGraph node deprecations, VS2022 required

### Within-major upgrades (minor / patch) and feature ↔ production transitions

The stages above are **major-version** migrations. A **within-major** bump (e.g. `110.0 → 110.1`, `110.1.0 → 110.1.2`) or a **feature → production** branch transition is a *different, lighter* job — and it is the most common upgrade performed in practice. These rarely need the Stage code/API changes. The real work is almost entirely **tooling and layout**:

1. **Update the build toolchain** (repo tools, packman, repo scripts) — see Step 2.5 (`procedures/toolchain.md`). This is usually the substantive part.
2. **Re-detect the deps directory** — its location can differ between releases, even within the same major line (Step 1 already sets `$DEPS_DIR`).
3. **Bump the kit-kernel pin** in `$DEPS_DIR/kit-sdk.packman.xml` (Step 5, item 2 — `procedures/apply-fixes.md`).
4. **For a feature ↔ production transition only:** check the extension **registry URL** in the `.kit` files — the feature and production lines use different registries, so a feature→production move may need a registry swap (Step 5, item 3). A plain within-major bump on the same line usually does **not**.
5. **Regenerate the extension version-lock** and do a **clean rebuild** (Step 5 items 1 & 8, then Step 6).

> **⚠️ Do NOT run the whole of Step 5 for a within-major bump.** Step 5 (`procedures/apply-fixes.md`) is written for **major-boundary** crossings. For a within-major / feature→production move, run **only**:
> - Step 5, **item 1** (clear extscache)
> - Step 5, **item 2** (update the kernel pin)
> - Step 5, **item 3** *only if* this is a feature↔production transition needing a registry swap
> - Step 5, **item 8** (rebuild) + Step 6 (lock regeneration + validate)
>
> **Skip items 4, 5, 6, and 7.** Those (deprecated-API regex replacement, removed-extension deletion including the 109→110 six-extension purge, adding transitive deps, and the VS/MSVC/WinSDK bump) apply **only when a major boundary is crossed**. Running them on a 110.1.0→110.1.2 bump would wrongly strip extensions or rewrite APIs that are perfectly valid on 110.1.

**Only run the Step 3 code scans if the upgrade crosses a major boundary.** For a pure within-major or feature→production move, skip Step 3's per-stage API scans and go straight to Step 2.5 → Step 5 (items 1–3 & 8 only, as above) → Step 6. If you cross one or more major boundaries on the way, run Step 3 for each major boundary passed and the full Step 5.

---

## Steps 2.5–6: Execute the Upgrade

Once the path is known, work through these in order. **Read the linked procedure file and follow it**; each assumes Step 1 detection has run.

- **Step 2.5 — Update the build toolchain** → `procedures/toolchain.md`. Highest-impact step; run it **first**, before touching source. For a within-major bump this is usually the only substantive work.
- **Step 3 — Scan the project** → `procedures/scan.md`. Run only the stage scans for the major boundaries you cross. Skip entirely for a pure within-major bump.
- **Step 4 — Generate the upgrade report** → `procedures/report.md`. Present findings by severity with exact `file:line` references.
- **Step 5 — Apply fixes** → `procedures/apply-fixes.md`. Get user approval before modifying files. (Within-major: items 1, 2, 8 only — see Step 2 above.)
- **Step 6 — Validate** → `procedures/validate.md`. Clean rebuild, regenerate the version lock, run tests.

**Already upgraded and hitting a specific error?** Go to `procedures/failure-modes.md` — it maps common symptoms (exit-55, ABI undefined symbols, render diffs, build loops, custom-build/layout issues) to fixes.
