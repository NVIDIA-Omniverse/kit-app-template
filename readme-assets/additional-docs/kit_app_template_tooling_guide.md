# Kit App Template Tooling Guide

This document provides an overview of the practical aspects of using the tooling provided in the `kit-app-template`. Intended for users with a basic familiarity with command-line operations, this guide offers typical usage patterns and recommendations for effective tool use. For a complete list of options for a given tool, use the help command: `./repo.sh [tool] -h` or `.\repo.bat [tool] -h`.

## Overview of Tools

The `kit-app-template` repository includes several tools designed to streamline the development of applications and extensions within the Omniverse Kit SDK.

### Available Tools
- `template`
- `build`
- `launch`
- `test`
- `package`

Each tool plays a specific role in the development workflow:

## Template Tool

**Command:** `./repo.sh template` or `.\repo.bat template`

### Purpose
The template tool facilitates the initiation of new projects by generating scaffolds for applications or extensions based on predefined templates located in `/templates/templates.toml`.

### Usage
The template tool has three main commands: `list`, `new`, `replay`.

#### `list`
Lists available templates without initiating the configuration wizard.

**Linux:**
```bash
./repo.sh template list
```
**Windows:**
```powershell
.\repo.bat template list
```

#### `new`
Creates new applications or extensions from templates with interactive prompts guiding you through various configuration choices.

**Linux:**
```bash
./repo.sh template new
```
**Windows:**
```powershell
.\repo.bat template new
```

#### `replay`
In cases where automation is required for CI pipelines or other scripted workflows, it is possible to record and replay the `template new` configuration.  

To achieve this first run template new with the `--generate-playback` flag:

**Linux:**
```bash
./repo.sh template new --generate-playback {playback_file_name}.toml
```

**Windows:**
```powershell
.\repo.bat template new --generate-playback {playback_file_name}.toml
```

After the configuration has been generated, the configuration can be replayed using the `replay` command:

**Linux:**
```bash
./repo.sh template replay {playback_file_name}.toml
```

**Windows:**
```powershell
.\repo.bat template replay {playback_file_name}.toml
```

## Build Tool

**Command:** `./repo.sh build` or `.\repo.bat build`

### Purpose
The build tool compiles all necessary files in your project, ensuring they are ready for execution, testing, or packaging. It includes all resources located in the `source/` directory.

### Usage
Run the build command before testing or packaging your application to ensure all components are up to date:

**Linux:**
```bash
./repo.sh build
```
**Windows:**
```powershell
.\repo.bat build
```

Other common build options:
- **`-c` or `--clean`:** Cleans the build directory before building.
- **`x` or `--rebuild`:** Rebuilds the project from scratch.

## Launch Tool

**Command:** `./repo.sh launch` or `.\repo.bat launch`

### Purpose
The launch tool is used to start your application after it has been successfully built, allowing you to test it live.

### Usage
Select and run a built .kit file from the `source/apps` directory:

**Linux:**
```bash
./repo.sh launch
```
**Windows:**
```powershell
.\repo.bat launch
```

Additional launch options:
- **`-d` or `--dev-bundle`:** Launches with a suite of developer tools enabled in UI-based applications.

- **`-p` or `--package`:** Launches a packaged application from a specified path.

    **Linux:**
    ```bash
    ./repo.sh launch -p </path/to/package.zip>
    ```
    **Windows:**
    ```powershell
    .\repo.bat launch -p <C:\path\to\package.zip>
    ```

- **`--container`:** Launches a containerized application (Linux only).

    **Linux:**
    ```bash
    ./repo.sh launch --container
    ```
    **Windows:**
    ```powershell
    .\repo.bat launch --container
    ```

- **Passing args to launched Kit executable:**
You can pass through arguments to your targeted Kit executable by appending `--` to your launch command. Any flags added after `--` will be passed through to Kit directly. The following examples will pass the `--clear-cache` flag to Kit.

    **Linux:**
    ```bash
    ./repo.sh launch -- --clear-cache
    ```
    **Windows:**
    ```powershell
    .\repo.bat launch -- --clear-cache
    ```

## Test Tool

**Command:** `./repo.sh test` or `.\repo.bat test`

### Purpose
The test tooling facilitates the execution of automated tests on your applications and extensions to help ensure their functionality and stability.  Applications configurations (`.kit` files) are tested to ensure they can startup and shutdown without issue.  However, the tests written within the extensions will dictate a majority of application functionality testing.  Extension templates provided by the Kit App Template repository include sample tests which can be expanded upon to increase test coverage as needed.

### Usage
Always run a build before testing:

**Linux:**
```bash
./repo.sh test
```
**Windows:**
```powershell
.\repo.bat test
```

## Package Tool

**Command:** `./repo.sh package` or `.\repo.bat package`

### Purpose
This tool prepares your application for distribution or deployment by packaging it into a distributable format.

### Usage
Always run a build before packaging to ensure the application is up-to-date:

**Linux:**
```bash
./repo.sh package
```
**Windows:**
```powershell
.\repo.bat package
```


Additional launch options:
- **`-n` or `--name`:** Specifies the package (or container image) name.

    **Linux:**
    ```bash
    ./repo.sh package -n <package_name>
    ```
    **Windows:**
    ```powershell
    .\repo.bat package -n <package_name>
    ```

- **`--thin`:** Creates a thin package that includes only custom extensions and configurations for required registry extensions.

    **Linux:**
    ```bash
    ./repo.sh package --thin
    ```
    **Windows:**
    ```powershell
    .\repo.bat package --thin
    ```

- **`--container`:** Packages the application as a container image (Linux only). When using the `--container` flag, the user will be asked to select a `.kit` file to use within the entry point script for the container.  This can also be specified without user interaction by passing it appropriate `.kit` file name via the `--target-app` flag.

    **Linux:**
    ```bash
    ./repo.sh package --container
    ```
    **Windows:**
    ```powershell
    .\repo.bat package --container
    ```

:warning: **Important Note for Packaging:** Because the packaging operation will package everything within the `source/` directory the package version will need to be set independently of a given `kit` file.  **The version is set within the `tools/VERSION.md` file.**

## Additional Resources
- [Kit App Template Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)