# Omniverse Kit App Template

<p align="center">
  <img src="readme-assets/kit_app_template_banner.png" width=100% />
</p>

## :memo: Feature Branch Information
**This repository is based on a Feature Branch of the Omniverse Kit SDK.** Feature Branches are regularly updated and best suited for testing and prototyping.
For stable, production-oriented development, please use the [Production Branch of the Kit SDK on NVIDIA GPU Cloud (NGC)](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/omniverse/collections/omniverse_enterprise_25h1).

[Omniverse Release Information](https://docs.omniverse.nvidia.com/dev-overview/latest/omniverse-releases.html#)


## Overview

Welcome to `kit-app-template`, a toolkit designed for developers interested in GPU-accelerated application development within the NVIDIA Omniverse ecosystem. This repository offers streamlined tools and templates to simplify creating high-performance, OpenUSD-based desktop or cloud streaming applications using the Omniverse Kit SDK.

### About Omniverse Kit SDK

The Omniverse Kit SDK enables developers to build immersive 3D applications. Key features include:
- **Language Support:** Develop with either Python or C++, offering flexibility for various developer preferences.
- **OpenUSD Foundation:** Utilize the robust Open Universal Scene Description (OpenUSD) for creating, manipulating, and rendering rich 3D content.
- **GPU Acceleration:** Leverage GPU-accelerated capabilities for high-fidelity visualization and simulation.
- **Extensibility:** Create specialized extensions that provide dynamic user interfaces, integrate with various systems, and offer direct control over OpenUSD data, making the Omniverse Kit SDK versatile for numerous applications.

### Applications and Use Cases

The `kit-app-template` repository enables developers to create cross-platform applications (Windows and Linux) optimized for desktop use and cloud streaming. Potential use cases include designing and simulating expansive virtual environments, producing high-quality synthetic data for AI training, and building advanced tools for technical analysis and insights. Whether you're crafting engaging virtual worlds, developing comprehensive analysis tools, or creating simulations, this repository, along with the Kit SDK, provides the foundational components required to begin development.

### A Deeper Understanding

The `kit-app-template` repository is designed to abstract complexity, jumpstarting your development with pre-configured templates, tools, and essential boilerplate. For those seeking a deeper understanding of the application and extension creation process, we have provided the following resources:

#### Companion Tutorial

**[Explore the Kit SDK Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)**: This tutorial offers detailed insights into the underlying structure and mechanisms, providing a thorough grasp of both the Kit SDK and the development process.

### New Developers

For a beginner-friendly introduction to application development using the Omniverse Kit SDK, see the NVIDIA DLI course:

#### Beginner Tutorial

**[Developing an Omniverse Kit-Based Application](https://learn.nvidia.com/courses/course-detail?course_id=course-v1:DLI+S-OV-11+V1)**: This course offers an accessible introduction to application development (account and login required).

These resources empower developers at all experience levels to fully utilize the `kit-app-template` repository and the Omniverse Kit SDK.

## Table of Contents
- [Overview](#overview)
- [Prerequisites and Environment Setup](#prerequisites-and-environment-setup)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Templates](#templates)
    - [Applications](#applications)
    - [Extensions](#extensions)
- [Application Streaming](#application-streaming)
- [Custom Messaging](#custom-messaging)
    - [Overview](#custom-messaging-overview)
    - [Kit Side Implementation](#kit-side-implementation)
    - [Web Client Implementation](#web-client-implementation)
    - [Timeline Control Example](#timeline-control-example)
- [Tools](#tools)
- [License](#license)
- [Additional Resources](#additional-resources)
- [Contributing](#contributing)

## Prerequisites and Environment Setup

Ensure your system is set up with the following to work with Omniverse Applications and Extensions:

- **Operating System**: Windows 10/11 or Linux (Ubuntu 22.04 or newer)

- **GPU**: NVIDIA RTX capable GPU (RTX 3070 or Better recommended)

- **Driver**: Minimum and recommended - This update requires driver version >=550.54.15 (Linux) or >=551.78 (Windows). Please verify your driver versions before upgrading. Newer versions may work but are not equally validated.

- **Internet Access**: Required for downloading the Omniverse Kit SDK, extensions, and tools.

### Required Software Dependencies

- [**Git**](https://git-scm.com/downloads): For version control and repository management

- [**Git LFS**](https://git-lfs.com/): For managing large files within the repository

- **(Windows - C++ Only) Microsoft Visual Studio (2019 or 2022)**: You can install the latest version from [Visual Studio Downloads](https://visualstudio.microsoft.com/downloads/). Ensure that the **Desktop development with C++** workload is selected.  [Additional information on Windows development configuration](readme-assets/additional-docs/windows_developer_configuration.md)

- **(Windows - C++ Only) Windows SDK**: Install this alongside MSVC. You can find it as part of the Visual Studio Installer. [Additional information on Windows development configuration](readme-assets/additional-docs/windows_developer_configuration.md)

- **(Linux) build-essentials**: A package that includes `make` and other essential tools for building applications.  For Ubuntu, install with `sudo apt-get install build-essential`

### Recommended Software

- [**(Linux) Docker**](https://docs.docker.com/engine/install/ubuntu/): For containerized development and deployment. **Ensure non-root users have Docker permissions.**

- [**(Linux) NVIDIA Container Toolkit**](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html): For GPU-accelerated containerized development and deployment. **Installation and Configuring Docker steps are required.**

- [**VSCode**](https://code.visualstudio.com/download) (or your preferred IDE): For code editing and development


## Repository Structure

| Directory Item   | Purpose                                                    |
|------------------|------------------------------------------------------------|
| .vscode          | VS Code configuration details and helper tasks             |
| readme-assets/   | Images and additional repository documentation             |
| templates/       | Template Applications and Extensions.                      |
| tools/           | Tooling settings and repository specific (local) tools     |
| .editorconfig    | [EditorConfig](https://editorconfig.org/) file.            |
| .gitattributes   | Git configuration.                                         |
| .gitignore       | Git configuration.                                         |
| LICENSE          | License for the repo.                                      |
| README.md        | Project information.                                       |
| premake5.lua     | Build configuration - such as what apps to build.          |
| repo.bat         | Windows repo tool entry point.                             |
| repo.sh          | Linux repo tool entry point.                               |
| repo.toml        | Top level configuration of repo tools.                     |
| repo_tools.toml  | Setup of local, repository specific tools                  |

## Quick Start

This section guides you through creating your first Kit SDK-based Application using the `kit-app-template` repository. For a more comprehensive explanation of functionality previewed here, reference the following [Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html) for an in-depth exploration.

### 1. Clone the Repository

Begin by cloning the `kit-app-template` to your local workspace:

#### 1a. Clone

```bash
git clone https://github.com/NVIDIA-Omniverse/kit-app-template.git
```

#### 1b. Navigate to Cloned Directory

```bash
cd kit-app-template
```

### 2. Create and Configure New Application From Template

Run the following command to initiate the configuration wizard:

**Linux:**
```bash
./repo.sh template new
```

**Windows:**
```powershell
.\repo.bat template new
```

> **NOTE:** If this is your first time running the `template new` tool, you'll be prompted to accept the Omniverse Licensing Terms.

Follow the prompt instructions:
- **? Select what you want to create with arrow keys ↑↓:** Application
- **? Select desired template with arrow keys ↑↓:** Kit Base Editor
- **? Enter name of application .kit file [name-spaced, lowercase, alphanumeric]:** [set application name]
- **? Enter application_display_name:** [set application display name]
- **? Enter version:** [set application version]

  Application [application name] created successfully in [path to project]/source/apps/[application name]

- **? Do you want to add application layers?** No

#### Explanation of Example Selections

• **`.kit` file name:** This file defines the application according to Kit SDK guidelines. The file name should be lowercase and alphanumeric to remain compatible with Kit’s conventions.

• **display name:** This is the application name users will see. It can be any descriptive text.

• **version:** The version number of the application. While you can use any format, semantic versioning (e.g., 0.1.0) is recommended for clarity and consistency.

• **application layers:** These optional layers add functionality for features such as streaming to web browsers. For this quick-start, we skip adding layers, but choosing “yes” would let you enable and configure streaming capabilities.

### 3. Build

Build your new application with the following command:


**Linux:**
```bash
./repo.sh build
```
**Windows:**
```powershell
.\repo.bat build
 ```

A successful build will result in the following message:

```text
BUILD (RELEASE) SUCCEEDED (Took XX.XX seconds)
```

 If you experience issues related to build, please see the [Usage and Troubleshooting](readme-assets/additional-docs/usage_and_troubleshooting.md) section for additional information.


### 4. Launch

Initiate your newly created application using:

**Linux:**
```bash
./repo.sh launch
```
**Windows:**
```powershell
.\repo.bat launch
```

**? Select with arrow keys which App would you like to launch:** [Select the created editor application]

![Kit Base Editor Image](readme-assets/kit_base_editor.png)


> **NOTE:** The initial startup may take 5 to 8 minutes as shaders compile for the first time. After initial shader compilation, startup time will reduce dramatically

## Templates

`kit-app-template` features an array of configurable templates for `Extensions` and `Applications`, catering to a range of desired development starting points from minimal to feature rich.

### Applications

Begin constructing Omniverse Applications using these templates

- **[Kit Service](./templates/apps/kit_service)**: The minimal definition of an Omniverse Kit SDK based service. This template is useful for creating headless services leveraging Omniverse Kit functionality.

- **[Kit Base Editor](./templates/apps/kit_base_editor/)**: A minimal template application for loading, manipulating and rendering OpenUSD content from a graphical interface.

- **[USD Composer](./templates/apps/usd_composer)**: A template application for authoring complex OpenUSD scenes, such as configurators.

- **[USD Explorer](./templates/apps/usd_explorer)**: A template application for exploring and collaborating on large Open USD scenes.

- **[USD Viewer](./templates/apps/usd_viewer)**: A viewport-only template application that can be easily streamed and interacted with remotely, well-suited for streaming content to web pages.

### Extensions

Enhance Omniverse capabilities with extension templates:

- **[Basic Python](./templates/extensions/basic_python)**: The minimal definition of an Omniverse Python Extension.

- **[Python UI](./templates/extensions/python_ui)**: An extension that provides an easily extendable Python-based user interface.

- **[Basic C++](./templates/extensions/basic_cpp)**: The minimal definition of an Omniverse C++ Extension.

- **[Basic C++ w/ Python Bindings](./templates/extensions/basic_python_binding)**: The minimal definition of an Omniverse C++ Extension that also exposes a Python interface via Pybind11.

   **Note for Windows C++ Developers** : This template requires `"platform:windows-x86_64".enabled` and `link_host_toolchain` within the `repo.toml` file be set to `true`. For additional C++ configuration information [see here](readme-assets/additional-docs/windows_developer_configuration.md).


## Application Streaming

The Omniverse Platform supports streaming Kit-based applications directly to a web browser. You can either manage your own deployment or use an NVIDIA-managed service:

### Self-Managed
- **Omniverse Kit App Streaming :** A reference implementation on GPU-enabled Kubernetes clusters for complete control over infrastructure and scalability.

### NVIDIA-Managed
- **NVIDIA Cloud Functions (NVCF):** Offloads hardware, streaming, and network complexities for secure, large scale deployments.

- **Graphics Delivery Network (GDN):** Streams high-fidelity 3D content worldwide with just a shared URL.

[Configuring and packaging streaming-ready Kit applications](readme-assets/additional-docs/kit_app_streaming_config.md)


## Custom Messaging

Custom messaging enables bidirectional communication between your Kit application and web clients. This is essential for building interactive streaming applications where the web UI needs to trigger actions in Omniverse or receive data from the Kit application.

### Custom Messaging Overview

The messaging system consists of two parts:
- **Kit Side (Python)**: Handles incoming messages from web clients and sends responses
- **Web Client Side (TypeScript/JavaScript)**: Sends requests and handles responses from Kit

The `usd_viewer.messaging` extension template includes a `custom_messaging.py` file that demonstrates this pattern.

### Kit Side Implementation

#### Step 1: Create the Custom Message Manager

Create a `custom_messaging.py` file in your extension's Python module:

```python
import carb
import carb.events
from carb.eventdispatcher import get_eventdispatcher
import omni.kit.app
import omni.kit.livestream.messaging as messaging
from omni.timeline import get_timeline_interface


class CustomMessageManager:
    """Manages custom messages between web client and Kit application"""

    def __init__(self):
        self._subscriptions = []
        self._timeline = get_timeline_interface()
        carb.log_info("[CustomMessageManager] Initializing...")

        # ===== REGISTER OUTGOING MESSAGES (Kit -> Web Client) =====
        outgoing_messages = [
            "customActionResult",       # Response to custom action requests
            "dataUpdateNotification",   # Notify client of data changes
            "timelineStatusResponse",   # Timeline/simulation status response
        ]

        for message_type in outgoing_messages:
            messaging.register_event_type_to_send(message_type)
            omni.kit.app.register_event_alias(
                carb.events.type_from_string(message_type),
                message_type,
            )

        # ===== REGISTER INCOMING MESSAGE HANDLERS (Web Client -> Kit) =====
        incoming_handlers = {
            'customActionRequest': self._on_custom_action_request,
            'getTimelineStatus': self._on_get_timeline_status,
            'timelineControl': self._on_timeline_control,
        }

        ed = get_eventdispatcher()
        for event_type, handler in incoming_handlers.items():
            omni.kit.app.register_event_alias(
                carb.events.type_from_string(event_type),
                event_type,
            )
            self._subscriptions.append(
                ed.observe_event(
                    observer_name=f"CustomMessageManager:{event_type}",
                    event_name=event_type,
                    on_event=handler
                )
            )

        carb.log_info("[CustomMessageManager] Initialized successfully")

    def _on_custom_action_request(self, event: carb.events.IEvent):
        """Handle custom action requests from web client"""
        payload = event.payload
        action_type = payload.get('action_type', '')
        parameters = payload.get('parameters', {})

        # Process the action and prepare result
        result = {"action": action_type, "status": "success"}

        # Send response back to web client
        get_eventdispatcher().dispatch_event(
            "customActionResult",
            payload={'action_type': action_type, 'result': result}
        )

    def on_shutdown(self):
        """Clean up subscriptions"""
        for sub in self._subscriptions:
            sub.unsubscribe()
        self._subscriptions.clear()
```

#### Step 2: Integrate with Your Extension

Update your `extension.py` to initialize the CustomMessageManager:

```python
from .custom_messaging import CustomMessageManager
import omni.ext


class Extension(omni.ext.IExt):
    def on_startup(self):
        self._custom_manager = CustomMessageManager()

    def on_shutdown(self):
        if self._custom_manager:
            self._custom_manager.on_shutdown()
            self._custom_manager = None
```

### Web Client Implementation

#### Sending Messages to Kit

Use the `AppStreamer.sendMessage()` method to send messages:

```typescript
import { AppStreamer } from '@nvidia/omniverse-webrtc-streaming-library';

// Send a custom action request
function sendCustomAction(actionType: string, parameters: Record<string, any>) {
    const message = {
        event_type: "customActionRequest",
        payload: {
            action_type: actionType,
            parameters: parameters
        }
    };
    AppStreamer.sendMessage(JSON.stringify(message));
}

// Query timeline status
function queryTimelineStatus() {
    const message = {
        event_type: "getTimelineStatus",
        payload: {}
    };
    AppStreamer.sendMessage(JSON.stringify(message));
}

// Control timeline (play/pause/stop)
function sendTimelineControl(action: 'play' | 'pause' | 'stop') {
    const message = {
        event_type: "timelineControl",
        payload: { action: action }
    };
    AppStreamer.sendMessage(JSON.stringify(message));
}
```

#### Handling Responses from Kit

Handle responses in your `onCustomEvent` callback:

```typescript
function handleCustomEvent(event: any) {
    if (!event) return;

    switch (event.event_type) {
        case "customActionResult":
            console.log('Action result:', event.payload);
            break;

        case "timelineStatusResponse":
            const status = event.payload;
            console.log('Timeline mode:', status.mode);
            console.log('Is playing:', status.is_playing);
            console.log('Scripted mode active:', status.scripted_mode_active);
            break;

        case "dataUpdateNotification":
            console.log('Data update:', event.payload);
            break;
    }
}
```

### Timeline Control Example

A common use case is controlling the simulation timeline from the web client. This is useful when you have Action Graphs that only execute during simulation playback.

#### Kit Side Handler

```python
def _on_get_timeline_status(self, event: carb.events.IEvent):
    """Handle timeline status requests"""
    is_playing = self._timeline.is_playing()
    is_stopped = self._timeline.is_stopped()

    mode = "playing" if is_playing else ("stopped" if is_stopped else "paused")

    get_eventdispatcher().dispatch_event(
        "timelineStatusResponse",
        payload={
            'mode': mode,
            'is_playing': is_playing,
            'is_stopped': is_stopped,
            'scripted_mode_active': is_playing,
        }
    )

def _on_timeline_control(self, event: carb.events.IEvent):
    """Handle timeline control requests (play/pause/stop)"""
    action = event.payload.get('action', '')

    if action == "play":
        self._timeline.play()
    elif action == "pause":
        self._timeline.pause()
    elif action == "stop":
        self._timeline.stop()

    # Send updated status
    get_eventdispatcher().dispatch_event(
        "timelineStatusResponse",
        payload={
            'mode': "playing" if self._timeline.is_playing() else "stopped",
            'is_playing': self._timeline.is_playing(),
            'scripted_mode_active': self._timeline.is_playing(),
        }
    )
```

#### Web Client Usage

```typescript
// Check if simulation is running before triggering navigation
async function navigateToLocation(coordinates: {x: number, y: number, z: number}) {
    // First, ensure timeline is playing (scripted mode)
    queryTimelineStatus();

    // If not playing, start the simulation
    if (!timelineStatus.isPlaying) {
        sendTimelineControl('play');
    }

    // Now trigger navigation action
    sendCustomAction('navigate', coordinates);
}
```

### Message Types Reference

| Message Type | Direction | Description |
|-------------|-----------|-------------|
| `customActionRequest` | Web -> Kit | Request a custom action with parameters |
| `customActionResult` | Kit -> Web | Response with action result |
| `getTimelineStatus` | Web -> Kit | Request current timeline/simulation state |
| `timelineControl` | Web -> Kit | Control timeline (play/pause/stop) |
| `timelineStatusResponse` | Kit -> Web | Current timeline state information |
| `dataUpdateNotification` | Kit -> Web | Push data updates to client |

For a complete implementation example, see the [usd_viewer.messaging](./templates/extensions/usd_viewer.messaging) extension template.


## Tools

The Kit SDK includes a suite of tools to aid in the development, testing, and deployment of your projects. For a more detailed overview of available tooling, see the [Kit SDK Tooling Guide](readme-assets/additional-docs/kit_app_template_tooling_guide.md).

Here's a brief overview of some key tools:

- **Help (`./repo.sh -h` or `.\repo.bat -h`):** Provides a list of available tools and their descriptions.

- **Template Creation (`./repo.sh template` or `.\repo.bat template`):** Assists in starting a new project by generating a scaffold from a template application or extension.

- **Build (`./repo.sh build` or `.\repo.bat build`):** Compiles your applications and extensions, preparing them for launch.

- **Launch (`./repo.sh launch`or`.\repo.bat launch`):** Starts your compiled application or extension.

- **Testing (`./repo.sh test` or `.\repo.bat test`):** Facilitates the execution of test suites for your extensions, ensuring code quality and functionality.

- **Packaging (`./repo.sh package` or `.\repo.bat package`):** Aids in packaging your application for distribution, making it easier to share or deploy in cloud environments.

## Governing Terms
The software and materials are governed by the [NVIDIA Software License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/) and the [Product-Specific Terms for NVIDIA Omniverse](https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-omniverse/).

## Data Collection
The Omniverse Kit SDK collects anonymous usage data to help improve software performance and aid in diagnostic purposes. Rest assured, no personal information such as user email, name or any other field is collected.

To learn more about what data is collected, how we use it and how you can change the data collection setting [see details page](readme-assets/additional-docs/data_collection_and_use.md).


## Additional Resources

- [Kit SDK Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)

- [Usage and Troubleshooting](readme-assets/additional-docs/usage_and_troubleshooting.md)

- [Developer Bundle Extensions](readme-assets/additional-docs/developer_bundle_extensions.md)

- [Omniverse Kit SDK Manual](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/index.html)


## Contributing

We provide this source code as-is and are currently not accepting outside contributions.