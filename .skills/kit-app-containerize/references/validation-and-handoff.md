# Validate and hand off the image

Always verify build completion and inspect the output image. Runtime checks follow the developer's selected scope and the app's actual requirements.

## Choose applicable checks

| Application and request | Runtime behavior |
|---|---|
| Containerization only | Do not launch the app/container for runtime validation. Report runtime checks not run by request. |
| RTX rendering or streaming, validation selected | Use compatible GPU hardware, drivers, and container runtime support. Check the source app and exact built container separately. |
| Non-rendering service or batch app, validation selected | Use supported CPU execution and the app's actual service-readiness or completion criteria. Non-streaming alone does not imply CPU-only. |
| Requested runtime checks, suitable host unavailable | Preserve successful build/image inspection results and identify the requested checks that remain unverified. |

GPU-free packaging support is based on inspected default tooling. An actual successful GPU-free build provides execution evidence for that specific app, version, and environment. Do not generalize it to every custom app or historical version.

For selected GPU runtime checks, verify access inside a disposable container before starting Kit. Host `nvidia-smi` alone does not establish Docker GPU access. Use the host's configured mechanism: `--gpus all` with NVIDIA runtime support, or `--device nvidia.com/gpu=all` when Docker native CDI support is enabled and an NVIDIA CDI specification is available. Use the verified option in the runtime example below. See [Docker CDI configuration](https://docs.docker.com/reference/cli/dockerd/#configure-cdi-devices) and [NVIDIA CDI support](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html) for the installed versions. Reuse working host configuration; runtime preparation does not require replacing it with a different mechanism.

## Test the exact image

Capture the image ID after packaging, then use that ID for container execution. On another host, distribute the image through the requested mechanism and establish the resulting identity. Use a registry digest after publication when available; a Docker local image ID and registry manifest digest are different identifiers.

Choose a unique test-container name and bounded check duration. Configure only the needed environment inputs, mounts, and ports from the selected app. Preserve logs and container state before cleanup; remove only resources created for this check.

The inspected `./repo.sh launch --container --name <repository>:<tag>` is a convenience launcher. It can fall back to another image when lookup fails, always requires NVIDIA hardware, and can discard the child process's failure status. Do not accept its completion as the success signal or use it for CPU-only validation. Prefer controlled Docker execution when proving the result.

For an NVCF app with an HTTP readiness service on container port 8011, a minimal local GPU readiness check can use the following shape. First select a free host port, a unique name, the actual image ID, and any app-required runtime inputs. Adjust ports/settings for the selected version. These are examples, not default values to overwrite the developer's configuration with.

```bash
KIT_IMAGE_ID=$(docker image inspect --format '{{.Id}}' acme/viewer:0.1.0)
KIT_CHECK_NAME=kit-container-check-unique
docker run --detach --name "$KIT_CHECK_NAME" --gpus all -p 127.0.0.1:18011:8011 "$KIT_IMAGE_ID"
docker inspect --format '{{.Image}} {{json .State}}' "$KIT_CHECK_NAME"
docker logs "$KIT_CHECK_NAME"
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:18011/v1/streaming/ready
```

Ensure image lookup and container creation succeed before proceeding. Add the selected app's required GPU driver capabilities, mounts, and environment inputs as needed. For CPU services, omit GPU options and use that service's configured check. A batch app needs its actual exit status and expected output rather than an HTTP probe.

A single probe immediately after launch is not a startup deadline. Poll within a chosen total limit, checking for early container exit and collecting logs. A successful `docker run --detach` only confirms container creation. Verify the container's `.Image`, actual state/exit status, and applicable readiness or completion result. For a long-running app, require it to remain running while checking readiness; a stopped container with exit code 0 is not a healthy running service.

Cold RTX startup can take several minutes for shader and driver pipeline preparation. An initial HTTP 503 or an "app ready" log line alone does not decide the readiness result. Allow for that preparation in the bounded check, observe progress, and record a timeout if the chosen deadline expires.

After collecting evidence, stop and remove the specific test container if it is no longer needed. Record intentional test shutdown separately from an application crash. A rebuild creates a new candidate and requires new image-specific runtime evidence.

## NVCF readiness and downstream boundary

When runtime validation is selected and the app exposes `omni.services.livestream.session`, check its configured readiness endpoint. The documented default is HTTP `/v1/streaming/ready` on port 8011, with a successful response indicating the service's readiness criteria. `/v1/streaming/startup` is not equivalent evidence of application/RTX readiness. See the [session service documentation](https://docs.omniverse.nvidia.com/kit/docs/omni.services.livestream.session/latest/Overview.html).

Keep these outcomes separate:

1. Source app runs in its development environment.
2. The packaged image runs and satisfies its app/container checks.
3. An NVCF deployment becomes ready with workers using the intended image.
4. The frontend connects and receives advancing decoded application frames.

This skill handles the first two when requested. The latter two need the downstream deployment/client validation workflow. Readiness-only local port mapping does not provide a complete external media/signaling path.

For the NVCF handoff, inspect actual settings and carry the required runtime input names and signaling/health configuration. Documented defaults include function type `STREAMING`, signaling route `/sign_in` on 49100, and readiness on 8011. Derive values from the selected app/version. Do not attach NVCF requirements to Kit App Streaming or non-streaming results. See [Deploying Kit Apps](https://docs.omniverse.nvidia.com/ov/ovs/latest/kit-guide/deploying.html).

## Optional publication

Publish only when the request includes image distribution to a resolved registry destination. A registry-qualified image name alone does not request a push. Confirm missing registry/namespace details and use the available authenticated mechanism without exposing secret values or baking credentials into the image.

If publication needs an additional tag, preserve the developer's original local tag, identify the destination tag, and ensure it refers to the built image before pushing. Do not silently choose a different repository or version. Verify the successful push and capture the published URI and manifest digest when available. Report publication failures independently of local build success.

A local image is not pullable by remote NVCF workers. The deployment stage needs the published/distributed image identity and pull access for its cluster. This skill can supply the image when publication is requested; otherwise report that distribution remains to be arranged.

## Result format

Return the following fields in a concise human-readable report. A caller may request a machine-readable contract; follow that actual contract rather than inventing a new required schema.

| Field | Include |
|---|---|
| Requested outcome | Existing/new app, streaming target or headless behavior, containerization-only or selected runtime checks, requested publication. |
| Source | Git URL/ref/commit and relevant local changes, or NGC resource/version/artifact identity; available provenance for a local project. |
| Versions | Kit, app, template and relevant build/package tools; resolved streaming extension versions or generated version-lock evidence; skill source/version separately. |
| Application | Base app, selected layer/entrypoint, important configuration changes, required runtime input names and mounts. |
| Image | Exact requested reference, local ID, OS/architecture, and published URI/digest if publication occurred. |
| Evidence | Build outcome/log location, image inspection, separate source-app and container runtime outcomes, exact identity tested, applicable readiness/exit evidence. |
| Remaining work | Checks not run and reasons, unresolved failures, and distribution/deployment/client validation still needed for downstream use. |

Use `passed`, `failed`, `not run by request`, `not run because unavailable`, or `not applicable` for each stage as appropriate. Include stages only where they clarify the requested outcome. Preserve attempted failures rather than describing them as untested.

Build plus image inspection is sufficient for a containerization-only request. If runtime validation was requested but unavailable, state that the image is built while that requested validation remains incomplete. Do not claim NVCF deployment or end-to-end streaming success from local container readiness.
