# Step 6: Validate

> Part of the **kit-upgrade** skill (see `../SKILL.md` for the workflow). Assumes Step 1 detection has run (`$BUILD` is set).

```bash
# After a kit-kernel pin bump, do a CLEAN rebuild so the kernel symlinks refresh,
# then regenerate the version lock against the new kernel.
# $BUILD is the entrypoint detected in Step 1 (./repo.sh, repo.bat, or the project's own build wrapper).
$BUILD build --rebuild -r   # clean + release build in one command
$BUILD build -u             # regenerate the version lock (removes the generated block and re-resolves)

# (equivalently: $BUILD build --clean   then   $BUILD build -r -u)

# Run tests if available
$BUILD test
```

> **After changing the kit-kernel pin, do a clean rebuild — clearing extscache is not enough.** Changing the
> pin does not always relink `_build/<platform>/<config>/kit`; if the stale old-version kernel link remains,
> the lock regenerates against the wrong kernel and the rebuild then fails (e.g. `No versions of
> omni.anim.curve.core … =<old-version>`). Use **`$BUILD build --clean`** (removes the build-time `_*`
> folders so the next `build -r` refreshes the symlinks) or **`$BUILD build --rebuild -r`** (clean +
> release build in one command), then regenerate the lock with `build -u`. The generated `[settings.app.exts]
> enabled = [...]` block in each `.kit` is what must be regenerated — it carries exact old-version pins that
> `extscache` clearing does not touch.

Watch for:
- **Exit code 55** from dependency solver = removed extension still declared as a dependency
- **Load failures** for removed extensions (no compile error — only visible at runtime)
- **Render differences** for DomeLight, mergeMaterials, FSD behavioral changes (Stage 3)
- **Silent correctness bugs** from NumPy int32→int64 default on Windows (Stage 3)
- **Slow scene loading** from mergeMaterials default change (Stage 3)

If a build error recurs, see `failure-modes.md` — in particular the anti-loop rule for repeated failures.
