# Step 2.5: Update the Build Toolchain (highest-impact — often the real work)

> Part of the **kit-upgrade** skill (see `../SKILL.md` for the workflow). Assumes Step 1 detection has run (`$DEPS_DIR`, `$BUILD` are set). Run this **before** touching source code — for a within-major / feature→production bump it is usually the *only* substantive work.

> **Key principle:** the most valuable part of an upgrade is usually **not** the code changes — it is making sure the project's **tooling** is correctly updated (repo scripts, `repo_man`/repoman, dependency versions). This step is therefore **first-class for every upgrade**, and the *primary* step for within-major / branch-transition bumps. Run it **before** touching source code.

**Why it matters:** the Kit kernel pin and the repo toolchain are coupled. Bumping `kit-sdk.packman.xml` alone frequently fails because packman tokens (e.g. `${platform_target_abi}`) only resolve under the matching `repo_man`, and newer kernels expect newer `repo_build` / `repo_kit_tools`. A pin bump *without* a toolchain bump produces cryptic pull/resolve failures — e.g. `Package not found ...gl.linux-x86_64` or `No versions of <ext> … =<old-version>`.

**The toolchain = these files** (see `../references/toolchain.json`):
- `$DEPS_DIR/repo-deps.packman.xml` — the `repo_*` tools: `repo_man`, `repo_build`, `repo_kit_tools`, `repo_kit_tools_internal`, `repo_kit_template`, `repo_usd`, `repo_format`, `repo_test`, `repo_package`, `repo_ci`, etc.
- `$DEPS_DIR/kit-sdk.packman.xml` — the kit-kernel pin (updated in Step 5, item 2 — see `apply-fixes.md`).
- `tools/packman/` — the packman bootstrap (`packman`, `packman.cmd`, `bootstrap/`).
- `repo.sh` / `repo.bat` — the repo wrappers (may need regenerating under a newer `repo_man`).
- `repo.toml` — build config (VS/MSVC/WinSDK for Stage 4; see `../references/config_changes.json`).

**How to find the correct target versions — do NOT guess:**
1. Get a **reference project already on the target Kit version** — the matching `kit-app-template` or `kit-sdk-public` branch for that Kit line, or the target Kit SDK release. Read its `repo-deps.packman.xml`. **Prefer the `production/<line>` branch** — it carries the vetted, most-current toolchain for that release. ⚠️ **Toolchain versions track the branch's maintenance cadence, not the kernel number** — a newer kernel line can ship an *older* toolchain (in kit-sdk-public, `feature/main` pins kernel 110.4 with `repo_man` 2.6.4, while the maintained `production/110.1` pins kernel 110.1.3 with a *newer* `repo_man` 2.9.3). Always read the target branch's **actual** pins; never assume "newer Kit = newer tools". *(Those version numbers are an illustrative snapshot read in 2026 — they **will** go stale; verify against the live branch, do not copy them.)*
2. **Diff** the project's `$DEPS_DIR/repo-deps.packman.xml` against the reference and align each `repo_*` tool `version=` to the reference. Do the same for `tools/packman/` if it differs.
3. Apply the versions, then do a **clean rebuild** (Step 6 — see `validate.md`) — the toolchain bump must land before the kernel pin resolves cleanly.

> This step is safe to run and validate (Step 6) **on its own, first**. Many "the upgrade won't build" error loops are nothing more than a stale toolchain — fixing it up front avoids chasing phantom code errors.
