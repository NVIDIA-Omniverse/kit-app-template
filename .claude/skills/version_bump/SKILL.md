# Version Bump Skill

Automates kit-sdk version bumps by updating version files, creating a branch, committing, and optionally pushing a merge request.

## Steps

### 1. Read Current State

Read these files to determine the current version:
- `tools/VERSION.md` — contains the current version string (e.g. `110.0.0-stage.17`)
- `tools/deps/kit-sdk.packman.xml` — contains the current kit-kernel packman version in the `version="..."` attribute

Display the current version and kit-kernel version to the user.

### 2. Ask Build Type

Use `AskUserQuestion` to ask: **"Is this a stage or rc build?"** with two options: `stage` and `rc`. Show the current version from `tools/VERSION.md` for context.

### 3. Compute New Version

Parse the current version from `tools/VERSION.md` which follows the format `X.Y.Z-<type>.<N>` (e.g. `110.0.0-stage.17`).

Apply these transition rules:

| Current Version | User picks | New Version |
|---|---|---|
| `X.Y.Z-stage.N` | stage | `X.Y.Z-stage.(N+1)` |
| `X.Y.Z-stage.N` | rc | `X.Y.Z-rc.1` |
| `X.Y.Z-rc.N` | rc | `X.Y.Z-rc.(N+1)` |
| `X.Y.Z-rc.N` | stage | `X.Y.(Z+1)-stage.1` |

Display the computed new version to the user.

### 4. Auto-Detect Latest kit-kernel Version

Query the omnipackages API to find available kit-kernel versions:

```bash
curl -s "https://omnipackages.nvidia.com/api/v3/packages/kit-kernel/?version=<MAJOR.MINOR.PATCH>%2B&remote=cloudfront"
```

Where `<MAJOR.MINOR.PATCH>` is extracted from the current version (e.g. `110.0.0`).

Parse the JSON response:
- Extract the `name` field from each item in the `items` array
- Strip the platform/config suffix using this regex to get the base version: `^([\d.]+\+\w+\.\d+\.[a-f0-9]+\.gl)\.`
- Deduplicate the base versions (multiple platform variants share the same base)
- They are already sorted by `modificationTime` (newest first)

Read the current kit-kernel version from `tools/deps/kit-sdk.packman.xml` to identify which ones are newer.

If the newest available version matches the current kit-kernel version (i.e. there are no newer versions), notify the user that the kit-kernel is already up to date and exit without making any file changes.

Otherwise, present the top available versions newer than the current one (up to 4) to the user via `AskUserQuestion`, with the newest version marked as "(Recommended)". The "Other" option is automatically available for the user to paste a custom version. Show the current kit-kernel version for reference in the question text.

### 5. Edit 3 Files

Using the new version string from step 3 and the kit-kernel version from step 4:

1. **`tools/VERSION.md`**: Replace the entire file content with the new version string (e.g. `110.0.0-stage.18`). Do NOT include a trailing newline.

2. **`tools/deps/kit-sdk.packman.xml`**: Replace the `version="..."` attribute value on the `<package name="kit-kernel" .../>` line. The new value should be the selected kit-kernel base version + `.${platform_target_abi}.${config}`. For example:
   ```
   version="110.0.0+feature.275000.abcd1234.gl.${platform_target_abi}.${config}"
   ```

3. **`templates/omni.all.template.extensions.kit`**: Replace the `# Kit SDK Version:` comment line. The new value should use just the base version (without platform suffix). For example:
   ```
   # Kit SDK Version: 110.0.0+feature.275000.abcd1234.gl
   ```

### 6. Confirm and Push

Use `AskUserQuestion` with yes/no options to confirm. The question should summarize the changes:
- Previous version → new version (e.g. `110.0.0-stage.17` → `110.0.0-stage.18`)
- Previous kit-kernel → new kit-kernel version
- Ask: **"Create branch, commit, and push merge request?"**

If the user declines, revert the 3 files back to their original content (restore the values read in step 1) and stop.

If the user accepts, perform these substeps:

**6a. Create Branch**

Before creating the new branch, capture the current branch name to use as the MR target:
```bash
git rev-parse --abbrev-ref HEAD
```

Derive the git username by running `git config user.email` and extracting the part before `@`.

Create and switch to a new branch:
```bash
git checkout -b <username>/<new-version>
```

For example: `gamato/110.0.0-stage.18`

**6b. Commit**

Stage and commit exactly the 3 modified files:
```bash
git add tools/VERSION.md tools/deps/kit-sdk.packman.xml templates/omni.all.template.extensions.kit
git commit -m "<new-version>"
```

The commit message is just the version string (e.g. `110.0.0-stage.18`), matching the existing convention.

**6c. Push and Create MR**

Push using GitLab push options to create an MR in one step, targeting the base branch captured in step 6a:
```bash
git push -u origin <username>/<new-version> \
  -o merge_request.create \
  -o merge_request.target=<base-branch> \
  -o "merge_request.title=[No Jira] chore: <new-version>"
```

For example, if the base branch was `feature/110.0`:
```bash
git push -u origin gamato/110.0.0-stage.18 \
  -o merge_request.create \
  -o merge_request.target=feature/110.0 \
  -o "merge_request.title=[No Jira] chore: 110.0.0-stage.18"
```

Display the MR URL from the push output to the user.
