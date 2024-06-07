# Kit Service App Template

![Kit Service Image](../../../readme-assets/kit_service.png)

**Based On:** `Omniverse Kit SDK 106.0`

## Overview

The Kit Service App Template offers a starting point for creating headless services within the NVIDIA Omniverse ecosystem. Designed to leverage the capabilities of the Omniverse Kit SDK, this template enables developers to build solutions that operate without a graphical user interface, ideal for background processes or server-side applications.

### Use Cases
The Kit Service Template is particularly well-suited for:

- Automation services that perform tasks in the background.
- Headless batch processing of 3D content for optimization, conversion, or analysis.
- Integrations with other software ecosystems that require 3D data processing without direct user interaction.


### Key Features

- **Headless Operation**: Runs without a graphical user interface for efficient background processing.
- **Fully Extensible**: Leverage and extend the existing functionalities of Omniverse Kit SDK.

## Usage

This section provides comprehensive instructions to leverage the Kit Service App Template effectively.

### Getting Started

To get started with the Kit Service Template, ensure your development environment meets the prerequisites outlined in the top-level README.

#### Cloning the Repository

```bash
git clone https://github.com/NVIDIA-Omniverse/kit-app-template.git
cd kit-app-template
```

#### Create New Application

**Note for Kit Service Template** : Some applications require a setup extension to function as intended. During Application configuration, you will be prompted for information about this extension. This extension will be created alongside the application and automatically added to your .kit file.  Subsequent extensions can be added to the .kit file manually.

**Linux:**
```bash
./repo.sh template new
```

**Windows:**
```powershell
.\repo.bat template new
```

Follow the prompt instructions:
- **? Select with arrow keys what you want to create:** Application
- **? Select with arrow keys your desired template:** Kit Service
- **? Enter name of application .kit file [name-spaced, lowercase, alphanumeric]:** [set application name]
- **? Enter application_display_name:** [set application display name]
- **? Enter version:** [set app version]

*The application template you have selected requires a setup extension.
Setup Extension -> kit_service_setup*
- **? Enter name of extension [name-spaced, lowercase, alphanumeric]:** [set extension name]
- **? Enter extension_display_name:** [set extension display name]
- **? Enter version:** [set extension version]

### Build and Launch

#### Build your application using the provided build scripts:
Note that the build step will build all applications contained in the `source` directory. Outside of initial experimentation, it is recommended that you build only the application you are actively developing.

**Linux:**
```bash
./repo.sh build
```
**Windows:**
```powershell
.\repo.bat build
```

 If you experience issues related to build, please see the [Usage and Troubleshooting](readme-assets/additional-docs/usage_and_troubleshooting.md) section for additional information.

#### Launch your application:

**Linux:**
```bash
./repo.sh launch
```
**Windows:**
```powershell
.\repo.bat launch
```

**? Select with arrow keys which App would you like to launch:** [Select the desired service application]

#### View your running Service:
- Visit `http://localhost:8011/docs` in your web browser to view the interactive documentation for the running service.
- By default the service will have a POST endpoint which will prompt you for input to generate a simple USD scene.

### Testing
Applications and their associated extensions can be tested using the `repo test` tooling provided. Each application template includes an initial test suite that can be run to verify the application's functionality.

**Note:** Testing will only be run on applications and extensions within the build directory. **A successful build is required before testing.**

**Linux:**
```bash
./repo.sh test
```

**Windows:**
```powershell
.\repo.bat test
```


### Customization
You can customize your Service Setup extension by adding new endpoints to, modifying existing ones, or adding new functionality to `service.py` or `extension.py`. If you would like to create a reusable component that might be used in other Omniverse services or applications, it is recommended that you create a new extension.

#### Create Custom Extension

**Linux:**
```bash
./repo.sh template new
```

**Windows:**
```powershell
.\repo.bat template new
```

Follow the prompt instructions:
- **? Select with arrow keys what you want to create:** Extension
- **? Select with arrow keys your desired template:**: [choose extension template]
- **? Enter name of extension [name-spaced, lowercase, alphanumeric]:**: [set extension name]
- **? Enter extension_display_name:**: [set extension display name]
- **? Enter version:**: [set extension version]


#### Adding Extension to .kit File
**Importantly** For an extension (beyond the initial setup extension) to become a persistent part of an application, the extension will need to be added to the application `.kit` file.

```toml
[dependencies]
"my_company.my_extension" = {}
```

#### Build with New Extensions
After a new extension has been added to the `.kit` file, the application should be rebuilt to ensure extensions are populated to the build directory.

### Packaging and Deployment

For deploying your application, create a deployable package using the `package` command:

**Linux:**
```bash
./repo.sh package --name [package_name]
```
**Windows:**
```powershell
.\repo.bat package --name [package_name]
```

This will bundle your application into a distributable format, ready for deployment on compatible platforms.

:warning: **Important Note for Packaging:** Because the packaging operation will package everything within the `source/` directory the package version will need to be set independently of a given `kit` file.  **The version is set within the `tools/VERSION.md` file.**

## Additional Learning

- [Kit App Template Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)
