# Step 4: Generate Upgrade Report

> Part of the **kit-upgrade** skill (see `../SKILL.md` for the workflow). Run after the Step 3 scans (`scan.md`).

Present findings organized by severity. Use exact `file:line` references from scan output.

```
## Upgrade Report: Kit [FROM] → [TO]
Project: [path]
Migration stages applied: [e.g., Stage 2 + 3 + 4]

### ❌ Breaking Changes (must fix — build or load will fail)
1. [file:line] — [description] → [exact fix]

### ⚠️ Behavioral Changes (no error, but may affect output or performance)
1. [file:line] — [description] → [fix or test required]

### 🔔 Deprecated Usage (should fix — will break in next version)
1. [file:line] — [description] → [fix]

### ✅ Not Affected
- [List the `id` or `title` from `breaking_changes.json` for each pattern that was scanned and returned no matches. This serves as a record that the check was performed, not just skipped.]

### 📋 Required Steps Regardless of Code Changes
1. Clear extscache: `rm -rf _build/*/release/extscache/`
2. Update `kit-sdk.packman.xml`: change version pin to `[TO].x.y+feature.${platform_target_abi}.${config}`
3. Update extension registry URLs in `.kit` files (see `../references/config_changes.json`)
4. Rebuild all C++ extensions (ABI break at every stage — required even with no source changes)
5. Regenerate version lock blocks in `.kit` files: `$BUILD precache_exts -c release` (substitute the build entrypoint detected in Step 1 — `./repo.sh` may not exist on a custom/integrated build)
6. If project has an ETM lock file (e.g. `omni.all.template.extensions.kit`), regenerate it or manually remove entries for removed extensions
7. [stage-specific items, e.g., VS2022 for Stage 4]

### 🧪 Behavioral Tests Required
1. [scenes with DomeLights — orientation regression (Stage 3, but inherited in all later stages)]
2. [load performance with mergeMaterials setting (Stage 3)]
3. [render output with FSD enabled (Stage 3)]
4. [MaterialX materials (Stage 4)]
5. [transform-heavy workflows after scalar xform ops change (Stage 2)]
```

**Prioritize for the user:** Extension removal errors and ABI rebuild requirements are the most common causes of project failures after a version bump. Start there.
