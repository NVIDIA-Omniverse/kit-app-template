# Select and prepare the application

Use the section matching the developer's starting point. Source selection and app preparation happen in the application project, which can differ from the checkout containing this skill.

## License acceptance during preflight

Identify required license acceptance while resolving the selected source and tool version. Inspect that version's license notices or prompt implementation before starting generation or long-running builds. Brief source/tool inspection may be needed to identify the terms; do not defer a known acceptance requirement until an unattended operation stops at a prompt.

When acceptance is required and not already supplied, collect it together with the initial app/version/image/validation decisions. Make the question explicit in the conversation, even when also using a structured question UI:

- Explain which planned operation requires acceptance.
- Name and link every agreement identified by the selected workflow, and state the project or runs the acceptance will cover. Quote the tool's prompt when it has been observed; do not invent a live prompt or claim work has stopped when this is preflight.
- Ask for an explicit yes or no, with an example reply. Explain that a yes authorizes answering the matching tool prompt on the developer's behalf.

For example, when the selected workflow names the NVIDIA agreements below:

> Before I generate this application and start the build, do you accept the [NVIDIA Software License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/) and [Omniverse Product-Specific Terms](https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-omniverse/), and authorize me to answer Yes to the license prompt for this application? Reply "Yes, I accept" or "No."

Use the selected version's agreements and URLs if they differ, and state the actual scope. One explicit acceptance can cover multiple planned runs using the same terms when those runs are named. Honor acceptance already supplied for that scope and use it when the matching tool prompt appears. Do not infer acceptance from silence or a general request to build, or bypass the tool's required response. If a later prompt presents different terms or scope, surface that difference before accepting. While awaiting an answer, continue only work that does not require acceptance.

## Existing project

Locate the intended project and inspect its instructions, working changes, build entrypoint, app definitions, and dependency configuration. Common Kit App Template locations include:

- `source/apps/` for base apps and layers, `source/extensions/` for project extensions.
- `repo.toml` for build/packaging configuration, `repo_tools.toml` and `tools/deps/` for tool and SDK pins.
- `templates/templates.toml` and resolved template metadata for available template/layer operations.

Custom projects can use other layouts. Follow their build registration and dependency precaching rather than introducing template metadata solely to fit this workflow.

Resolve the requested `.kit` file and its dependencies. Record the actual base app and selected layer. Inspect inherited settings and launcher behavior as well as the selected file. A name ending in `_nvcf.kit` or `_streaming.kit` is a clue, not proof of the configured functionality.

Check whether the app has the dependencies, settings, build registration, and assets it needs. Prepare missing packaging or streaming configuration within the requested scope. If the app requires substantial implementation or migration before it can build, report that boundary and the specific blocker.

## New project from GitHub

Recommend [NVIDIA-Omniverse/kit-app-template](https://github.com/NVIDIA-Omniverse/kit-app-template), `main`. If the request does not choose a Kit version/ref, ask whether the developer wants that default or a specific version/ref. Inspect the public refs and selected source pins, then display the resolved Kit version.

Use a new directory. For the accepted default:

```bash
git clone --branch main --single-branch https://github.com/NVIDIA-Omniverse/kit-app-template.git my-kit-project
cd my-kit-project
git rev-parse HEAD
```

Choose the directory from the developer's workspace context. For another branch or tag, resolve that exact ref; for a commit, fetch and check out the resolved commit explicitly. Do not apply `--branch` to a commit hash. If a requested version is unavailable publicly, explain the available choices. Never substitute an internal checkout or edit only the Kit kernel pin to simulate a complete version change.

Inspect the selected checkout's dependency pins and CLI. The ordinary template flow is:

```bash
./repo.sh template new
```

Select the available app template based on the requested behavior, then resolve its app namespace/name, display name, app version, and any required extension inputs. Do not silently reuse documentation example identities. Keep app version independent of the Kit version and container tag.

Answer any required template license prompt using the acceptance established during preflight. If it presents different terms or scope, follow [license preflight](#license-acceptance-during-preflight) before proceeding.

Use supported interactive input or the chosen tool's documented playback mechanism. In the inspected tooling, `template new --generate-playback <file>` records choices without creating the app; `template replay <file>` subsequently renders it. Inspect help before using these options on another version. A generated playback file alone is not an application. Legacy `--input` or `REPO_TEMPLATE_SCRIPT` mechanisms do not reliably handle checkbox layer selection; use the supported playback flow or interact with the actual prompts.

## Streaming layers

| Target | Preparation |
|---|---|
| Kit App Streaming | Reuse or add the selected version's ordinary streaming layer for local or self-managed streaming. In the inspected Kit App Template this is the picker entry `[omni_default_streaming]: Omniverse Kit App Streaming (Default)`, which renders `{app_name}_streaming.kit`. |
| NVCF | Reuse or add that version's NVCF layer, including its streaming/session-service dependencies and settings. Ordinary streaming alone is insufficient. In the inspected Kit App Template this is the picker entry `[nvcf_streaming]: NVCF Streaming`, which renders `{app_name}_nvcf.kit`. |
| Non-streaming | Keep the intended headless app entrypoint; do not add streaming dependencies. Determine whether the app still requires GPU rendering. |

For template-generated apps, select the layer during creation or use the available modify flow:

```bash
./repo.sh template modify
```

Inspect the app's template metadata before modifying it, commonly `source/rendered_template_metadata.json`, and the template's linked-layer definitions. The inspected modify flow is interactive and can overwrite an already rendered layer when selected again. Reuse a correct existing layer; inspect custom edits before regenerating. Do not invent noninteractive `--app` or `--layer` flags. For a manually authored app without the required metadata, use the selected version's layer definitions as a reference and make only the necessary dependency/settings changes.

Rebuild after adding or changing layers. Select the actual generated layer as the packaging entrypoint, such as `acme.viewer_streaming.kit` for Kit App Streaming or `acme.viewer_nvcf.kit` for NVCF. Do not package the base desktop app merely because it has the same display name.

## Secondary route: NGC SDK

Use this route when the developer chooses it. If the developer is unsure, explain the two source routes and recommend public Kit App Template by default.

1. Resolve the desired resource and version using the [Kit SDK catalog links in the manual](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/building_containerizing.html#omniverse-kit-sdk). Select the resource matching the requested release and platform; the collection linked by a latest guide may cover a different feature or production line. Follow that resource's download and extraction instructions using available authentication. Do not assume an NGC SDK resource is a runnable container image.
2. Record the resource organization/team/name, requested version, downloaded artifact identity/checksum, and detected SDK version. Do not invent a Git commit for a downloaded SDK.
3. On Linux, when provided by that package, run `./new_project.sh` from the extracted SDK and resolve its project-location and license prompts. Inspect the package's instructions if this entrypoint differs.
4. Enter the generated project, inspect its actual tool/SDK pins, and use the same app/layer workflow above. Keep the skill loaded from its complete folder if it is absent from that SDK release.

## Record the selection

Capture the source URL/ref/commit and relevant local changes for Git projects, or the NGC artifact provenance for downloaded SDKs. For a local non-Git project, record the available provenance. Record the skill's source/version separately, along with the resolved app, Kit, template, and build/package tool versions.

Generated projects can resolve streaming extensions from a registry to versions newer than copies bundled in the SDK. Record the versions resolved by the application or preserve its generated version locks with the build evidence. Keep the selected SDK and Kit pins unless the developer requests a change.

Examples follow the [Kit app creation and containerization guide](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/building_containerizing.html). When the selected checkout differs from the latest guide, its actual configuration and supported CLI determine the commands.
