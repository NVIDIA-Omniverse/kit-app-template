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
The template tool has two main commands: `list` and `new`.

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
- `-c` or `--clean`: Cleans the build directory before building.
- `x` or `--rebuild`: Rebuilds the project from scratch.

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
- `d` or `--dev-bundle`: Launches with a suite of developer tools enabled in UI-based applications.
- `-p` or `--package`: Launches a packaged application from a specified path.

**Linux:**
```bash
./repo.sh launch -p /path/to/package.zip
```
**Windows:**
```powershell
.\repo.bat launch -p C:\path\to\package.zip
```

## Test Tool

**Command:** `./repo.sh test` or `.\repo.bat test`

### Purpose
The test tool facilitates the execution of automated tests on your applications and extensions to help ensure their functionality and stability.

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

By default, the `package` tool creates a `.zip` file named `kit-app-template` in the `_build/packages` directory. The package name can be specified using the `-n` or `--name` flag:

**Linux:**
```bash
./repo.sh package -n my_package
```
**Windows:**
```powershell
.\repo.bat package -n my_package
```

:warning: **Important Note for Packaging:** Because the packaging operation will package everything within the `source/` directory the package version will need to be set independently of a given `kit` file.  **The version is set within the `tools/VERSION.md` file.**

#### Fat and Thin Packages
Packages can be either 'fat' (including all dependencies) or 'thin' (including only custom extensions and configurations for required registry extensions). Thin packages are created using the `--thin` flag. A fat package is created by default to facilitate ease of use and testing, whereas **thin package distribution is required for broader dissemination.**

## Additional Resources
- [Kit App Template Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/intro.html)