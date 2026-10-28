# Build and package the selected app

Run from the resolved application project. These command examples match the inspected `repo_kit_tools` 1.21.4 workflow; inspect the selected checkout's pins and help before using them with other tooling.

## Establish the build environment

The initial workflow uses Linux x86_64 artifacts, compatible Linux x86_64 execution, and Docker. Check the actual build host and Docker daemon:

```bash
uname -s
uname -m
docker version
docker info
./repo.sh build --help
./repo.sh package_container --help
```

Check the project's documented compiler/dependency prerequisites, Docker daemon accessibility, artifact/package download access, and space for the build, staged copy, and image layers. The selected base image and Dockerfile determine additional requirements. The inspected default Dockerfile needs a BuildKit frontend supporting `COPY --exclude` and its `# syntax=docker/dockerfile:1` directive.

Native Windows packaging is rejected by this tool. A suitable WSL installation or a remote Linux builder can supply the required environment, but native Kit also runs during host-side extension trimming. A Windows shell connected only to a remote Docker daemon does not move that step to Linux. ARM, multiarch, and cross-build setups require a compatible Kit distribution, base image, and separately verified workflow.

GPU availability is a runtime decision, not a prerequisite for this inspected default packaging path. Dependency precaching resolves extensions; it is not shader warmup. Inspect custom build hooks, trimming changes, and Dockerfiles before applying this conclusion to a customized project. Check compatible GPUs/drivers and NVIDIA Container Toolkit only when GPU runtime checks are selected.

## Resolve app and image inputs

Resolve a real source app/layer and its staged basename. Confirm that the intended `.kit` file and Kit executable exist after building. Check a separate launcher only when the selected project's workflow requires one. Stop to resolve missing paths, multiple matching apps, or duplicate basenames in nested app directories.

Inspect `repo.toml` and existing `[repo_kit_package_container]` configuration. The tool can reduce an existing app path to its basename, and configuration lookup can distinguish `acme.viewer_nvcf` from `acme.viewer_nvcf.kit` before normalizing. Reuse the matching configured entry with consistent naming rather than generating duplicate entries or passing a nonexistent path.

Require a valid, writable image repository plus explicit tag. Examples:

| Reference | Meaning |
|---|---|
| `acme/viewer:0.1.0` | Repository and explicit tag. |
| `registry.example.com:5000/acme/viewer:0.1.0` | Registry port and a separate explicit tag. |
| `registry.example.com:5000/acme/viewer` | Missing tag; the registry-port colon is not a version tag. |
| `acme/viewer@sha256:...` | Existing-image digest identity, not a writable Docker build tag. |

The inspected tool treats any colon in `--image-tag` as a complete-reference signal. Passing an untagged name can therefore change its interpretation or cause Docker to default to `latest`. Resolve the name/tag first. Preserve the requested value instead of silently adding `latest`, changing the namespace, or replacing it with a generated app name.

Before building, inspect whether the chosen local tag already exists and record its ID. Rebuilding that tag updates its local target; make that effect clear. A remote registry overwrite is a separate publication action. See [Docker image reference syntax](https://docs.docker.com/reference/cli/docker/image/tag/).

## Build and optional source-app check

For the supported template workflow:

```bash
./repo.sh build --config release
```

Use the custom project's supported equivalent when needed. In the inspected build tool, `-c` means clean and exit, not configuration; use the long `--config` option. Verify command success, dependency resolution, and the selected app artifacts. Inspect the configured build root rather than assuming one path for every project.

If requested and supported by the host, run the source app and collect actual exit/readiness/log evidence before packaging. The convenience `./repo.sh launch` command can guide app selection, but its return alone is not proof of runtime success. A non-rendering CPU service can need direct invocation through its own launcher. If runtime checks were declined, continue with packaging and record that choice.

## Container configuration and packaging

Reuse existing valid Dockerfile and entrypoint configuration. For supported projects without configuration, `package_container` can generate a container template/configuration when supplied a valid app. Inspect the files it creates. Explicit generation is also available in the inspected version:

```bash
./repo.sh package_container --app acme.viewer_nvcf.kit --generate
```

This generates configuration in the default project `tools/containers` location; it is not a completed image build. If specifying a destination in this tool version, use an absolute path inside the project because configuration injection computes a path relative to the absolute project root. Inspect the selected version's help before using it, and do not regenerate customized files without examining them.

Generation does not overwrite existing files. In the inspected tool, both `--generate` and the `auto_generate` configuration path skip any destination file that already exists, log a warning, and continue, so an existing `tools/containers/Dockerfile` keeps its current `FROM` line after the tool's bundled default changes. Compare that `FROM` line with the Dockerfile bundled in the pinned `repo_kit_tools` package (`omni/repo/kit_tools/package/data/Dockerfile`). The inspected 1.21.4 default is `nvcr.io/nvidia/omniverse/ov-base-ubuntu22-x86_64:1.0.0`; the default before 1.21.4 was `nvcr.io/nvidia/omniverse/ov-base-ubuntu-22:2026.2.3`. When they differ, update deliberately: delete `tools/containers/Dockerfile` (and `entrypoint.sh` if it should also be refreshed) and rerun `--generate`, or edit the `FROM` line in place and keep the customized content. Regeneration leaves an existing `repo.toml` container entry for that app unchanged. Record the base image actually used in the result.

Substitute the resolved app name and full image reference in the build command:

```bash
./repo.sh package_container --app acme.viewer_nvcf.kit --image-tag acme/viewer:0.1.0 --config release
```

The tool stages build artifacts, optionally precaches dependencies, trims unused extensions, and invokes Docker. Do not substitute historical `package --container`, `--target-app`, or container `--name` arguments without evidence that the selected version requires them. There is no shader-cache bypass or dry-run flag in this inspected container tool. Use `--from-package` only when deliberately using a compatible packaged artifact. It is a boolean switch, not an archive-path argument; inspect both its configured archive pattern and post-unpack commands for compatibility with the selected public or private source.

Inspect custom runtime-loaded dependencies and assets. The inspected tool supports repeatable `--extra-ext` and `extra_extensions` configuration to keep needed extensions/apps through precache and trimming. Use it only for identified dependencies. If local assets, credentials, caches, or cloud inputs are expected at runtime, identify their mounts or input names instead of silently treating the developer machine's state as part of the image.

The default entrypoint runs Kit directly with `--no-window`, rather than invoking a custom app shell launcher. Account for required environment/setup/arguments. Desktop display integration or substantial custom launcher behavior requires its own adaptation and validation.

## Verify the produced image

After a successful packaging command, inspect the exact requested reference:

```bash
docker image inspect acme/viewer:0.1.0
docker image inspect --format '{{.Id}}' acme/viewer:0.1.0
```

Record its full local ID, repository tags, OS/architecture, configured entrypoint/command, and relevant app metadata. The default Dockerfile labels images with `kit_app_template`; match that label and the rendered entrypoint/configuration to the selected app. A label alone is insufficient if a custom Dockerfile changes behavior.

Bind the result to the current successful build and its logs. An unchanged image ID can be legitimate when Docker reuses identical content. Neither an existing tag after a failed build nor a different ID without successful build evidence proves completion. Keep full metadata/logs private when they contain environment values, and include only necessary non-secret evidence in the result.

Continue with [validation and handoff](validation-and-handoff.md).

## Diagnose common failures

| Observation | Next check |
|---|---|
| Command or option is unavailable | Inspect the selected tool pin, help, and project configuration. Do not upgrade the project just to match these examples. |
| App missing or multiple matches | Resolve the real source/staged app and consistent config name before retrying. |
| Dependencies cannot resolve | Check selected-version extension pins, registry access, and build/precaching configuration. Avoid a global cache purge. |
| An app works outside the container but lacks an extension inside it | Inspect trimming and runtime-loaded dependencies; preserve identified extras through supported configuration. |
| Dockerfile parse failure around `COPY --exclude` | Inspect BuildKit/frontend compatibility and the syntax directive, especially in custom Dockerfiles. |
| Native executable or architecture failure | Verify Linux x86_64 artifacts, host execution environment, and base image. Remote Docker alone does not solve native host execution. |
| Stale staging is demonstrated | Use the selected tool's scoped staging-clean option only after checking its target. Avoid deleting unrelated builds or Docker caches. |
| Docker image exists after an error | Preserve the failed result and distinguish the old tag/image from the attempted build. |

Use [container tool documentation](https://docs.omniverse.nvidia.com/kit/docs/repo_kit_tools/latest/docs/package_container.html) alongside the selected tool's implementation and configuration.
