# Developer Bundle Extensions

## Overview

The Developer Bundle Extensions provide a suite of tools designed to enhance the development and debugging process within Omniverse Kit applications. Each of these extensions aims streamline a specific aspects of Omniverse application and extension development.

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

## Developer Bundle Extensions

Developer Utilities are designed to assist developers in various aspects of application development, from debugging to extension management. These utilities offer insight into the internal workings of an application and its extensions.

- **[Developer > Extensions] omni.kit.window.extensions**: The most popular utility, this tool manages available extensions. It provides quick access to the extension registry and local extensions, simplifying the process of adding dependencies for developer extensions and applications.

- **[Developer > Commands] omni.kit.window.commands**: Captures the command history within a running application. It is particularly useful for developers who interact with the UI, allowing them to capture the commands used to execute specific functionalities.

- **[Developer > Script Editor] omni.kit.window.script_editor**: A simplified script editor for running short code snippets directly within the application. It's a helpful tool for testing small pieces of code before integrating them into a project. Additionally, it offers useful sample scripts that can be executed live.

- **[Developer > VS Code Link] omni.kit.debug.vscode**: VSCode python debugger support window.  This utility allows developers to step through their python code in VSCode while running the application.

- **[Developer > Debug Settings] omni.kit.debug.settings**: This utility provides a detailed view of the configurable settings for extensions within an application, making it easier to tweak and optimize extension behavior.

---

**:warning: The Developer Bundle extensions require a UI based application with a menu bar to run properly. They will not work as expected for headless services or in applications that do not display a menu bar**