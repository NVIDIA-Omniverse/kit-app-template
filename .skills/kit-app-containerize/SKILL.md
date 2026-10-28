---
name: kit-app-containerize
description: Prepare and containerize an existing or new NVIDIA Omniverse Kit application, including Kit App Streaming or NVCF layers, explicit image naming, optional runtime validation, and an image handoff. Use for Kit application container builds and packaging, rather than cluster deployment or frontend development.
---

# Containerize a Kit application

Produce the developer's requested container image from the selected Kit app, and report what was built and verified. Prefer the existing application. For a new application, recommend the public [Kit App Template](https://github.com/NVIDIA-Omniverse/kit-app-template) on `main`; offer another Kit version/ref when requested. NGC SDK download is a secondary route.

## Resolve the developer's intent

Inspect the request, orchestration context, and project before asking questions. Ask only for missing decisions that affect the work.

| Decision | Action |
|---|---|
| Existing application or new application? | Locate the existing project and intended app, even if it needs preparation. For a new app, resolve the template and required app name, display name, and app version. |
| Streaming from the container? | Determine Kit App Streaming versus NVCF. In the inspected Kit App Template layer picker, Kit App Streaming is `[omni_default_streaming]: Omniverse Kit App Streaming (Default)` and renders `{app_name}_streaming.kit`; NVCF is `[nvcf_streaming]: NVCF Streaming` and renders `{app_name}_nvcf.kit`. Check whether the appropriate layer already exists. For non-streaming use, establish the intended headless service, batch, or rendering behavior. |
| Which Kit version? | For a new app without a specified version, ask whether to use public GitHub `main` or another Kit version/ref. Recommend `main` and show its resolved Kit version. For an existing app, report and preserve its version unless a change is requested. |
| What image name and tag? | Resolve the full image repository/name and explicit version tag, including any registry/namespace. Preserve supplied values. Kit version, app version, and container tag are separate choices. |
| What runtime validation? | Recommend running RTX apps on a compatible RTX GPU before packaging and checking the built container afterward. Allow containerization only, even when a GPU is present. Offer applicable CPU checks for non-rendering services. |
| Required license acceptance? | Identify the selected workflow's applicable terms early. When acceptance is required and not already supplied, collect it with the initial preflight questions before generation or long-running builds. Follow [license preflight](references/app-preparation.md#license-acceptance-during-preflight). |

An existing app without streaming layers stays on the existing-app path. Ordinary streaming configuration does not establish NVCF readiness. If multiple apps or layers fit the request, resolve the selection before modifying files.

## Prepare the selected app

Read [app preparation](references/app-preparation.md) for the applicable existing-app, new-project, or NGC route.

1. Resolve the project, source ref/artifact, Kit and tool versions, exact app/layer, and target platform. Inspect the developer project's pins, rather than assuming the toolchain of a different repository or the latest documentation.
2. Reuse the app and correct streaming layer, or generate only the missing app/layer/configuration. Inspect dependencies and settings as well as template metadata. Preserve custom work; substantial application repair or a Kit migration needs its own scope.
3. Establish a compatible Linux x86_64 build environment and Docker access for the initial workflow. Native Windows packaging is unsupported by the inspected tool. A suitable WSL or remote Linux environment must execute the native Kit packaging steps, not just host a Docker daemon.

The standard inspected pipeline can build/package without RTX rendering. Custom hooks or Dockerfiles can add GPU requirements. Runtime rendering/streaming needs compatible GPU resources. Extension dependency precaching is not shader warmup. Do not claim an unexecuted GPU-free build succeeded.

## Build and package

Read [container workflow](references/container-workflow.md) before packaging. It covers the actual CLI, app/config matching, image references, and common failures.

1. Build with the selected project's supported release workflow. Confirm dependencies and the selected app artifacts are present.
2. Perform source-app runtime validation when selected and available. Record it separately from container validation.
3. Resolve a real, unique staged app and a writable `repository:explicit-tag`. Reuse matching container configuration. Inspect an existing target tag before replacing it.
4. Package with the selected tool's supported arguments. The inspected command is `./repo.sh package_container --app <app.kit> --image-tag <repository>:<tag> --config release`.
5. Inspect the resulting image ID, requested tag, architecture, app label/configuration, entrypoint, and required runtime inputs. An old image with the same tag is not evidence of a successful build.

The default entrypoint uses `--no-window` and invokes Kit directly. It does not automatically retain a custom shell launcher's setup or provide a desktop display. Inspect those requirements before promising equivalent behavior.

Diagnose failures, make a bounded correction supported by the evidence, and repeat affected steps. Report unresolved blockers rather than repeatedly rebuilding unchanged inputs, broadly cleaning the environment, or silently changing Kit versions.

## Validate and hand off

Read [validation and handoff](references/validation-and-handoff.md). Always inspect the build result and image. Run only the runtime checks selected by the developer, against the exact built image ID or published digest.

| Outcome | Report |
|---|---|
| Build and image inspection succeed; containerization only requested | Complete. Runtime validation not run by request. |
| Runtime validation requested and passes | Complete for the checks actually performed. |
| Build succeeds but requested runtime checks cannot run | Image built; requested validation remains unverified, with the reason. |
| A build or runtime check fails | Failed stage and evidence. Do not relabel a failure as skipped. |

Return source/SDK provenance, resolved versions, chosen app and streaming target, image reference and ID, platform/runtime requirements, evidence, and remaining checks. Use a consistent human-readable result; use a machine format only when the caller supplies a real contract.

Publish the image only when requested for a resolved destination. A registry-qualified tag alone is not a request to push. A local-only image is a valid containerization result, but downstream NVCF workers still need a distributed image and registry pull access.

NVCF deployment, frontend creation, and full browser/media validation are separate stages. Container readiness does not prove end-to-end streaming. Carry the image identity and required runtime configuration to the next stage without claiming its checks passed.
