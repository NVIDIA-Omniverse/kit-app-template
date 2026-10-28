# kit-app-containerize

An agent skill for preparing and containerizing NVIDIA Omniverse Kit applications. It supports existing applications, new Kit App Template projects, Kit App Streaming and NVCF layers, explicit image tags, and optional runtime validation. The default new-project source is public Kit App Template `main`; the agent asks about the desired Kit version when it has not been supplied.

## Load the skill

Use an agent that can read local files and run commands in the chosen build environment. Point it at this folder's `SKILL.md` and the application project. For example:

```text
Read /path/to/kit-app-containerize/SKILL.md and follow its relevant references.
Containerize the existing app in /path/to/my-kit-project for NVCF as
acme/viewer:0.1.0. Build and inspect the image only; skip runtime validation.
```

For a new application:

```text
Read /path/to/kit-app-containerize/SKILL.md.
Help me create and containerize a new Kit application for streaming.
Ask about the Kit version, streaming target, and image name/tag where needed.
```

Keep the complete `kit-app-containerize/` directory together. Resolve each relative link from the file containing that link, preserving the folder layout even when the application is in another checkout. An older project or an NGC SDK package can use this skill from a separate checkout without changing the application's Kit version.

Publishing a skill under `.skills` does not guarantee automatic discovery in every agent host. Direct file loading is the baseline. If your agent supports a native skills directory, copy or link the complete folder into that host's documented location. A plain copy of `SKILL.md` omits required references. No agent-specific installer or additional plugin is required for direct loading.

## Contents

| File | Purpose |
|---|---|
| [SKILL.md](SKILL.md) | Developer preflight, workflow, and completion rules. |
| [App preparation](references/app-preparation.md) | Existing apps, version selection, streaming layers, and the secondary NGC route. |
| [Container workflow](references/container-workflow.md) | Build prerequisites, packaging commands, image naming, and troubleshooting. |
| [Validation and handoff](references/validation-and-handoff.md) | Exact-image runtime checks, optional publication, and downstream results. |

The initial execution workflow targets Linux x86_64 with Docker and compatible Kit artifacts. RTX runtime checks require compatible hardware; containerization-only is supported without claiming runtime validation. The skill inspects the selected project's actual tooling rather than promising identical behavior across all Kit versions.

See the [Kit containerization guide](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/building_containerizing.html) and [OVS getting-started guide](https://docs.omniverse.nvidia.com/ov/ovs/latest/getting-started.html) for the surrounding developer journey.
