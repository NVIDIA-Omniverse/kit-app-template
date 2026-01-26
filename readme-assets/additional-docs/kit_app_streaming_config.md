# Kit Application Streaming

## Overview

Kit SDK templates and tooling enable the creation streaming-ready Omniverse Kit applications and aid in the packaging/containerization in preparation for deployment. This document outlines how to set up, configure, and package Kit applications for a streaming deployment.

:warning: **Important :** Creation of containerized streaming applications must be done from a Linux environment.

## Create and Configure an Application

Choose a template from the options below, then follow the instructions in the template README.md to create your application using the `template new` command:

- **[Kit Base Editor](../../templates/apps/kit_base_editor/)**: A minimal application for loading, manipulating, and rendering OpenUSD content through a graphical interface.
- **[USD Composer](../../templates/apps/usd_composer)**: A template for authoring complex OpenUSD scenes (e.g., configurators).
- **[USD Explorer](../../templates/apps/usd_explorer)**: A template for exploring and collaborating on large OpenUSD scenes.
- **[USD Viewer](../../templates/apps/usd_viewer)**: A streamlined, viewport-only application well-suited for remote streaming to web pages.

### What Are Application Layers?

An **application layer** is a separate `.kit` configuration file that extends your base application for a specific deployment scenario. Instead of modifying your main application, layers let you create variants optimized for different use cases:

- **Base application** (`my_app.kit`): Your core application with all features and UI
- **Streaming layer** (`my_app_streaming.kit`): Inherits from base, adds streaming extensions and settings

This approach keeps your base application clean while enabling different deployment modes (local desktop, cloud streaming, etc.) from the same codebase.

### Adding a Streaming Layer

During the templating process, you will be prompted:

```bash
Do you want to add application layers?
```

Answer `yes` to enable streaming for your application. You can then pick from the following streaming layers:

```bash
? Do you want to add application layers? Yes
? Browse layers with arrow keys ↑↓: [SPACE to toggle selection, ENTER to confirm selection(s)]
❯ [ ] [omni_default_streaming]: Omniverse Kit App Streaming (Default)
  [ ] [nvcf_streaming]: NVCF Streaming
  [ ] [omni_gdn_streaming]: GDN Streaming
```

- **Omniverse Kit App Streaming (Default):** Ideal for self-managed streaming deployments or local streaming during development. Uses [`omni.kit.livestream.webrtc`](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.livestream.app/latest/Overview.html) for WebRTC-based streaming. Choose this for local testing, Kubernetes deployments, or custom infrastructure.

- **NVCF Streaming:** Required for applications deployed on NVIDIA DGX Cloud via NVIDIA Cloud Functions. Adds [`omni.services.livestream.session`](https://docs.omniverse.nvidia.com/kit/docs/omni.services.livestream.session/latest/Overview.html) which implements NVCF-specific health endpoints and session management. See the [DGXC Deployment Guide](dgxc_nvcf_deployment.md) for configuration details.

- **GDN Streaming:** Streams applications through NVIDIA Graphics Delivery Network; especially useful for configurator workflows. Refer to the [End-to-End Configurator Example Guide](https://docs.omniverse.nvidia.com/auto-config/latest/overview.html) for deployment instructions.


After creating your application, you'll find two `.kit` files in the `/source/apps/` directory:
- `{app_name}.kit`: The main application configuration file.
- `{app_name}_{streaming_config}.kit`: The streaming configuration file.

### Adding Layers to an Existing Application

If you didn't add streaming layers during initial setup, or want to add additional layers later, use the `modify` command:

**Linux:**
```bash
./repo.sh template modify
```
**Windows:**
```powershell
.\repo.bat template modify
```

When prompted, select the application `.kit` file to update, then choose the layer(s) to add. After the operation completes, rebuild the project with `./repo.sh build` or `.\repo.bat build`.

For more details on the `modify` command, see the [Tooling Guide](kit_app_template_tooling_guide.md#modify).

> **Note:** The `modify` command works with applications created using Kit App Template 107.3 or newer.

## Build Your Application
After you have created and customized your application, build it using the following command:

```bash
./repo.sh build
```

## Packaging Your Application

- **Omniverse Kit App Streaming** & **Omniverse on NVCF**
  From a **Linux** development environment, run the following command to containerize your application for streaming:

  ```bash
  ./repo.sh package_container --image-tag [container_image_name:container_image_tag]
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