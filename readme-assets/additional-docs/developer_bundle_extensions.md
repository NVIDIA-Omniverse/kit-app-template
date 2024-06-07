# BETA - Developer Bundle Extensions

## Overview

The BETA Developer Bundle Extensions provide a suite of tools designed to enhance the development and debugging process within Omniverse Kit applications. These extensions fall into a few categories, each aimed at streamlining specific aspects of application and extension development. Given their BETA status, these tools are in active development, which means they will undergo continual enhancements, updates, and possibly some significant changes.

---

## Enabling Developer Bundle Extensions

**Linux**
```bash
./repo.sh launch --dev-bundle
```

**Windows**
```powershell
.\repo.bat launch --dev-bundle
```

The `launch` tool will prompt for a selection of a `.kit` file to launch. Select the desired UI based application. The developer bundle is not currently suitable for headless services.

---

## Developer Bundle

### Developer Utilities

Developer Utilities are designed to assist developers in various aspects of application development, from debugging to extension management. These utilities offer insight into the internal workings of an application and its extensions.

- **[Developer > Utilities > Debug Settings] omni.kit.debug.settings**: This utility provides a detailed view of the configurable settings for extensions within an application, making it easier to tweak and optimize extension behavior.

- **[Developer > Utilities > Commands] omni.kit.window.commands**: Captures the command history within a running application. It is particularly useful for developers who interact with the UI, allowing them to capture the commands used to execute specific functionalities.

- **[Developer > Utilities > Extensions] omni.kit.window.extensions**: The most popular utility, this tool manages available extensions. It provides quick access to the extension registry and local extensions, simplifying the process of adding dependencies for developer extensions and applications.

- **[Developer > Utilities > Window Inspector] omni.kit.window.inspector**: Enables developers to inspect UI elements, understanding their configuration and structure, which is helpful for efficient UI development.

- **[Developer > Utilities > Script Editor] omni.kit.window.script_editor**: A simplified script editor for running short code snippets directly within the application. It's a helpful tool for testing small pieces of code before integrating them into a project. Additionally, it offers useful sample scripts that can be executed live.

### Live Documentation

Live Documentation extensions offer in-app documentation, making it easier for developers to understand and leverage various components of the Omniverse Kit SDK.

- **[Developer > Documentation > Omni UI Style Docs] omni.kit.documentation.ui.style**: Provides in-app documentation for UI styling, helping developers achieve the desired look and feel for their applications.

- **[Developer > Documentation > Omni Viewport Docs] omni.kit.viewport.docs**: Offers in-app documentation for viewport usage, enabling developers to leverage viewport features effectively.

- **[Developer > Documentation > Omni UI Scene Docs] omni.ui.scene.docs**: Delivers in-app documentation for in-scene (within the viewport) UI elements, assisting developers in creating immersive and interactive 3D environments.

### Profiling

Profiling tools are essential for identifying bottlenecks and optimizing application performance. This category includes:

- **[Developer > Profiling > Tracy] omni.kit.profiler.tracy**: An application profiler that can be launched and connected to analyze the application's performance in depth.

- **[Developer > Profiling > Profiler Window] omni.kit.profiler.window**: Provides quick access to a profiler UI window, offering summary information about application performance and facilitating easy identification of potential issues.

- **[Developer > Profiling > Performance] omni.kit.runtime_performance_monitor**: A configurable performance testing extension that captures performance data during its enabled state. Upon disabling, it prints the results to the console, allowing for an analysis of the application's runtime performance.

---

**:warning: The developer extensions do require a UI based application to run properly. They will not work as expected for headless services**