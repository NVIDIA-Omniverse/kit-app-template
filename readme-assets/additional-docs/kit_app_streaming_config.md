# Kit Application Streaming

## Overview

Kit SDK templates and tooling enable the creation streaming-ready Omniverse Kit applications and aid in the packaging/containerization in preparation for deployment. This document outlines how to set up, configure, and package Kit applications for a streaming deployment.

:warning: **Important :** For **Omniverse Kit App Streaming** or **Omniverse Cloud (OVC)**, you must containerize your application in a Linux environment to enable streaming.

## Create and Configure an Application

Choose a template from the options below, then follow the instructions in the template README.md to create your application using the `template new` command:

- **[Kit Base Editor](../../templates/apps/kit_base_editor/)**: A minimal application for loading, manipulating, and rendering OpenUSD content through a graphical interface.
- **[USD Composer](../../templates/apps/usd_composer)**: A template for authoring complex OpenUSD scenes (e.g., configurators).
- **[USD Explorer](../../templates/apps/usd_explorer)**: A template for exploring and collaborating on large OpenUSD scenes.
- **[USD Viewer](../../templates/apps/usd_viewer)**: A streamlined, viewport-only application well-suited for remote streaming to web pages.

:warning: **Important :** During the templating process, you will be prompted:

```bash
Do you want to add application layers?
```

Answer `yes` to enable streaming for your application. You can then pick from the following streaming layers:

```bash
? Do you want to add application layers? Yes
? Browse layers with arrow keys ↑↓: [SPACE to toggle selection, ENTER to confirm selection(s)]
❯ [ ] [omni_default_streaming]: Omniverse Kit App Streaming (Default)
  [ ] [ovc_streaming]: Omniverse Cloud Streaming
  [ ] [omni_gdn_streaming]: GDN Streaming
  [ ] [ovc_streaming_legacy]: Omniverse Cloud Streaming (Legacy)
```

- **Omniverse Kit App Streaming (Default):** Ideal for self-managed streaming deployments or local streaming during development.
- **Omniverse Cloud Streaming:** Suited for applications streamed through Omniverse Cloud, enabling Omniverse Connect and Omniverse Create (new or migrating customers should use this layer).
- **GDN Streaming:** Streams applications through NVIDIA GDN; especially useful for configurator workflows.
- **Omniverse Cloud Streaming (Legacy):** For existing customers on the legacy Omniverse Cloud platform.

After creating your application, you’ll find two `.kit` files in the `/source/apps/` directory:
- `{app_name}.kit`: The main application configuration file.
- `{app_name}_{streaming_config}.kit`: The streaming configuration file.

## Build Your Application
After you have created and customized your application, build it using the following command:

```bash
./repo.sh build
```

## Packaging Your Application

- **Omniverse Kit App Streaming** & **Omniverse Cloud**
  From a **Linux** development environment, run the following command to containerize your application for streaming:

  ```bash
  ./repo.sh package --container --name {container name}
  ```

  :warning: **Note**
  When prompted to select a `.kit` file, choose the `{app_name}_{streaming_config}.kit` file.

- **GDN Streaming**
  Refer to the [End-to-End Configurator Example Guide](https://docs.omniverse.nvidia.com/auto-config/latest/overview.html) for instructions on packaging and deploying to NVIDIA GDN.

## Testing Locally

If you added the **Omniverse Kit App Streaming** layer, you can test your application locally. Follow the “Local Streaming” instructions in the template’s README:

- [Kit Base Editor Local Streaming](../../templates/apps/kit_base_editor/README.md#local-streaming)
- [USD Composer Local Streaming](../../templates/apps/usd_composer/README.md#local-streaming)
- [USD Explorer Local Streaming](../../templates/apps/usd_explorer/README.md#local-streaming)
- [USD Viewer Local Streaming](../../templates/apps/usd_viewer/README.md#local-streaming)

## Additional Resources

- [Kit SDK Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)