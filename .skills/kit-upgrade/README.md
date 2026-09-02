# Kit SDK Upgrade Skill

## What This Is

This repository contains an AI agent skill for upgrading Omniverse Kit SDK projects between versions. The skill encodes the complete breaking-change catalog for the Kit 106→107→108→109→110 migration path — including removed extensions, deprecated APIs, C++ ABI breaks, Python runtime changes, and configuration updates — into a structured set of instructions and reference data that an AI agent can execute against a live project. The agent scans the project, produces a categorized report with exact `file:line` references, and suggests targeted fixes, including auto-fixable regex replacements where safe.

## Who It's For

Kit extension and application developers who need to upgrade a project from one Kit SDK version to another. This includes developers working on kit-app-template-based applications, standalone extensions, and Isaac Sim integrations. The skill is particularly useful when upgrading across multiple versions at once (e.g., 107→110), where the number of breaking changes makes manual triage error-prone.

## What It Contains

| File | Description |
|------|-------------|
| `SKILL.md` | Lean workflow router — loaded by the AI agent. Holds version/layout/build detection (Step 1) and the migration-path decision (Step 2), and points to the procedure files for everything else. |
| `procedures/toolchain.md` | Step 2.5 — update the `repo_*` build toolchain (the highest-impact part of most upgrades). |
| `procedures/scan.md` | Step 3 — the full per-stage `grep` scan catalog for breaking changes, removed extensions, and config. |
| `procedures/report.md` | Step 4 — the upgrade-report template. |
| `procedures/apply-fixes.md` | Step 5 — ordered fix list, auto-fixable regex patterns, and manual-only changes. |
| `procedures/validate.md` | Step 6 — clean-rebuild and validation commands. |
| `procedures/failure-modes.md` | Symptom→fix diagnosis for projects that already upgraded and are erroring. |
| `procedures/stage-notes.md` | Per-stage (106→107→…→110) breaking-change reference. |
| `references/breaking_changes.json` | 80+ breaking changes with search patterns, affected versions, and recommended fixes. |
| `references/removed_extensions.json` | Extensions removed or deprecated by Kit version, with replacement guidance and search targets. |
| `references/api_replacements.json` | 1:1 API replacements that are safe to apply with regex find/replace. |
| `references/config_changes.json` | Settings keys, registry URLs, and build config changes between versions. |
| `references/toolchain.json` | The build-toolchain file/package set (`repo_*` tools, packman, repo scripts) and how to find the correct target versions for a given Kit line. |
| `install.sh` / `install.bat` | Copies the skill (SKILL.md + `procedures/` + `references/`) into an existing Kit project so it travels with the repo. |

The skill uses **progressive disclosure**: `SKILL.md` stays small (a router the agent always loads) and each step's detail lives in a `procedures/*.md` file the agent reads only when the workflow sends it there. This keeps the entry file well under length limits and keeps irrelevant detail out of context.

## How to Use

**Install into an existing project** (so the skill travels with the repo):

```bash
./install.sh /path/to/your-kit-project                  # copies into <project>/.skills/kit-upgrade/
./install.sh /path/to/your-kit-project .claude/skills   # or the Claude Code skills layout
```

On Windows: `install.bat C:\path\to\your-kit-project`.

Then load the skill into any AI coding assistant that can read files and run shell commands, and point it at the project you want to upgrade.

**Claude Code:**
```
Read the skill at /path/to/kit-upgrade-skill/SKILL.md and the reference files in references/.
Then scan /path/to/my-kit-project and generate an upgrade report for Kit 109 → 110.
```

**Cursor / VS Code Copilot / other MCP clients:**
Add `kit-upgrade-skill/` as a context directory or attach `SKILL.md` as a system prompt, then ask the agent to scan your project.

The agent will:
1. Detect the current Kit SDK version, the deps-directory location (`tools/deps/` vs root `deps/`), and the build entrypoint (`./repo.sh` / `repo.bat` or a custom/integrated build) — never assuming the SDK template layout
2. Determine the migration path — including within-major (minor/patch) and feature↔production transitions, not just major-version stages
3. Update the build toolchain (`repo_*` tools, packman, repo scripts) to match the target Kit line — often the substantive part of an upgrade
4. Run targeted `grep` scans across the full project root (including `templates/`, launcher configs, and ETM lock files) for any major boundaries crossed
5. Generate a categorized report: breaking changes, behavioral changes, deprecated usage, and a "not affected" checklist
6. Suggest fixes — both auto-applicable regex replacements and manual changes requiring human judgment
7. Provide clean-rebuild and validation commands (via the detected build entrypoint) to confirm the upgrade

## Version Coverage

| Stage | Migration | Key Changes |
|-------|-----------|-------------|
| 1 | 106 → 107 | Python 3.10→3.11, Linux ABI (`_GLIBCXX_USE_CXX11_ABI=1`), Carbonite Events 2.0, nv_usd rename |
| 2 | 107 → 108 | Python 3.11→3.12, OpenUSD 25.02, OmniGraph 3.0 ABI, livestream split, ILayers ABI 1.1 |
| 3 | 108 → 109 | NumPy 2.x, CUDA 12.4.1 driver requirement, Fabric ABI, mimalloc, FSD default on, DomeLight orientation |
| 4 | 109 → 110 | OpenUSD 25.11, Carbonite 210, Hydra 2 removed, OmniGraph bundle node deprecations, VS2022 required |

> **Note:** Kit 108 was never publicly released. Its changes are folded into the 107→109 path — Stage 2 must still be addressed when upgrading 107→109.

Multi-version upgrades (e.g., 107→110) apply all intervening stages in sequence.

## How to Contribute

**Add a new breaking change:**
Add an entry to `references/breaking_changes.json`. Each entry needs an `id`, `title`, `stage`, `search_pattern` (grep-compatible regex), `affected_files` (glob patterns), and `fix` description. If the fix is a safe 1:1 substitution, also add it to `references/api_replacements.json`.

**Add a removed or deprecated extension:**
Add an entry to `references/removed_extensions.json` with `extension`, `status` (`removed` or `deprecated`), `version`, `replacement` (or `null`), `search_in` (list of file extensions to scan), and `notes`. Include any known failure mode (e.g., exit-55) and whether the extension appears in non-obvious locations like `templates/` or ETM lock files.

**Add a new Kit version (release):** edit the files that own each piece — the skill is split by concern:
- `SKILL.md` — add the new row/stage to the **Step 2 migration-path table and Stage summary** (these stay in the router).
- `procedures/scan.md` — add the new `# === Stage N ===` scan blocks.
- `procedures/stage-notes.md` — add the new per-stage breaking-change section.
- `procedures/apply-fixes.md` — add any new auto-fix regex patterns or fix-list items.
- `references/*.json` — add the corresponding structured entries.

Follow the existing section structure in each file for consistency. Keep `SKILL.md` lean — detailed scan commands and stage notes belong in `procedures/`, not the router.

**Test your additions:**
Apply the skill to a real project that exercises the new patterns. If the scan misses something or the fix guidance is wrong, document it and open a PR with both the issue description and the corresponding fix in the relevant `procedures/` or `references/` file.

---

This skill was developed and validated against [kit-extension-explorer](https://github.com/NVIDIA-Omniverse/kit-extension-explorer), a Kit 110 application based on kit-app-template. See `test-report.md` for the full upgrade report from that validation run.
