# Kit App Template and Omniverse Cloud (OVC)

![USD Explorer Hero Image](../readme-assets/usd_explorer.jpg)


## Overview

Omniverse Cloud leverages Kit App Template to create Omniverse applications, include required streaming extensions and package into containers. This document outlines step-by-step instructions on how to build a Kit application specifically for Omniverse Cloud.

### Use Cases

Kit applications are deployed into Omniverse cloud for consumption at scale.

### Key Features

- **Streaming via Webrtc**: Seamlessly combine and manage multiple USD files in a unified scene.
- **Container Packaging**: Intuitive interface designed for ease of use by non-specialized personnel.

## Steps to Create Kit App for OVC

### Getting Started

To get started with Kit App Template, ensure your development environment meets the prerequisites outlined in the top-level [**README**](../../../README.md#prerequisites-and-environment-setup).

> **NOTE:** These steps should only be executed on a Linux system because they require containerization. Use **terminal** in Linux for all instructions.

#### Cloning the Repository

```bash
git clone https://github.com/NVIDIA-Omniverse/kit-app-template.git
cd kit-app-template
```

#### Create New Application

```bash
./repo.sh template new
```

During this step, select a default app template. The three recommended are:
- USD Composer
- USD Explorer
- USD Viewer

Refer to each of the unique application docs, linked above, for details on the function of each application.

### Build and Launch
Note that the build step will build all applications contained in the `source` directory. Outside of initial experimentation, it is recommended that you build only the application you are actively developing.

#### Build your application using the provided build scripts:

```bash
./repo.sh build
```

 If you experience issues related to build, please see the [Usage and Troubleshooting](readme-assets/additional-docs/usage_and_troubleshooting.md) section for additional information.

#### Launch your application:

This is a step to test the application. This will launch the Kit App locally in a desktop environment. This step must be run from a terminal session inside of a desktop environment (ie. VDI)

```bash
./repo.sh launch
```

### Testing
Applications and their associated extensions can be tested using the `repo test` tooling provided. Each application template includes an initial test suite that can be run to verify the application's functionality.

> **NOTE:** Testing will only be run on applications and extensions within the build directory. **A successful build is required before testing.**

**Linux:**
```bash
./repo.sh test
```

### Customization

#### Enable Extension
- On launch of the Application enable the developer bundle by adding the `--dev-bundle` or `-d` flag to the launch command.

    **Linux:**
    ```bash
    ./repo.sh launch --dev-bundle
    ```
    **Windows:**
    ```powershell
    .\repo.bat launch --dev-bundle
    ```
- From the running application select `Developer` > `Extensions`

- Browse and enable extensions of interest from the Extension Manager.
    - Enabling the extensions within the Extension Manager UI will allow you to try out the features of the extension in the currently running application.

    - To permanently add the extension to the application, you will need to add the extension to the `.kit` file. For example, adding the Layer View extension would require adding `omni.kit.widget.layers` to the dependencies section of the `.kit` file.

- For additional information on the Developer Bundle Extensions, refer to the [Developer Bundle Extensions](../../../readme-assets/additional-docs/developer_bundle_extensions.md) documentation.

### Containerization

**Requires:** `Docker` and `NVIDIA Container Toolkit`

The packaging tooling provided by the Kit App Template also supports containerization of applications. This is a required step to deploy the Omniverse Kit Application into Omniverse Cloud. This can only be performed in a **Linux environment**.

To package your application as a container image, use the `--container` flag:

**Linux:**
```bash
./repo.sh package --container
```

You will be prompted to select a `.kit` file to serve as the application to launch via the container entrypoint script. This will dictate the behavior of your containerized application.

For Omniverse Cloud Managed Paas (OVC), you must select the `{your-app-name}_ovc.kit` file to ensure the proper settings are used for that platform.

Similar to desktop packaging, the container option allows for specifying a package name using the `--name` flag to name the container image:

```bash
./repo.sh package --container --name [container_image_name]
```

#### Launching a Container

The container can be launched to test it's functionality locally. This is a good validation step before uploading the container into the OVC subscription.
Applications packaged as container images can be launched using the `launch` command:

```bash
./repo.sh launch --container
```

If only a single container image exists, it will launch automatically. If multiple container images exist, you will be prompted to select the desired container image to launch.

### Local Streaming

The UI-based template applications in this repository produce more than a single `.kit` file. For validating the OV Kit template application, you will test using `{your-app-name}_ovc.kit` which we will use for local streaming. This file inherits from the base application and adds necessary streaming components like `omni.kit.livestream.webrtc`. To try local streaming, you need a web client to connect to the streaming server.

#### 1. Clone Web Viewer Sample

The web viewer sample can be found [here](https://github.com/NVIDIA-Omniverse/web-viewer-sample)

```base
git clone https://github.com/NVIDIA-Omniverse/web-viewer-sample.git
```

Follow the instructions in the README to install the necessary dependencies.

#### 2. Modify the Web Viewer Sample

The Web Viewer Sample is configured by default to connect to the USD Viewer application template and includes web UI elements for sending API calls to a running Kit application. This is necessary for the Viewer template, which has limited functionality for driving application behavior directly. However, for the USD Explorer template, this messaging UI functionality isn't needed as the USD Explorer Template includes menus and other UI elements that can be interacted with directly.

When connecting the Web Viewer Sample to the USD Explorer application template, it is recommended to modify the source code. Make the following change to the web viewer sample:

**In `web-viewer-sample/src/App.tsx`**

- Change:
```typescript
import Window from './Window';
```

- To:
```typescript
import Window from './ViewportOnly';
```

#### 3. Start the streaming Kit Application

:warning: **Important**: Launching the streaming application with `--no-window` passes an argument directly to Kit allowing it to run without the main application window to prevent conflicts with the streaming client.

> **NOTE:** The `--no-window` flag is not required for containerized applications as it is the default launch behavior.


**Launch and stream a containerized application:**

When streaming a containerized application, ensure that the containerized application was configured during packaging to launch a streaming application (e.g., `{your_app_name}_streaming.kit`).

```bash
./repo.sh launch --container
```
If only a single container image exists, it will launch automatically. If multiple container images exist, you will be prompted to select the desired container image to launch.

Alternatively, if the `./repo.sh container` command was already executed and the Kit App was already containerized, the container can be run using docker:

```bash
docker run <name_of_container>
```

#### 4. Start the Streaming Client
```bash
npm run dev
```
In a Chromium-based browser, navigate to [http://localhost:5173/](http://localhost:5173/) and you should see the streaming client connect to the running Kit application.

![Streaming Explorer Image](../../../readme-assets/streaming_explorer.png)

## Additional Learning

- [Kit App Template Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)
