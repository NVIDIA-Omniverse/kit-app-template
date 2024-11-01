# Basic Python Extension Template

<p align="center">
  <img src="../../../readme-assets/python-logo-only.png" width="30%" />
</p>

## Overview

The Basic Python Extension Template is a starting point for developers looking to build Python-based extensions within the NVIDIA Omniverse ecosystem. This template offers a best practices foundation and structure to easily integrate with the broader capabilities of the Omniverse Kit SDK.

### Use Cases

This template is ideal for developers looking to build:

- A reusable Python extension that can be easily integrated with Omniverse Kit SDK applications.


### Key Features

- Structure well suited for the build, test and packaging tooling within this repository.
- All required setup code for use with the Omniverse Kit SDK.


## Usage

This section provides instructions for the setup and use of the Basic Python Extension Template.

### Getting Started

To get started with the Basic Python Extension, ensure your development environment meets the prerequisites outlined in the [top-level README](../../../README.md#prerequisites-and-environment-setup).

#### Cloning the Repository

```bash
git clone https://github.com/NVIDIA-Omniverse/kit-app-template.git
cd kit-app-template
```

#### Create New Extension
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
- **? Select with arrow keys your desired template:**: Basic Python Extension
- **? Enter name of extension [name-spaced, lowercase, alphanumeric]:**: [set extension name]
- **? Enter extension_display_name:**: [set extension display name]
- **? Enter version:**: [set extension version]

#### Build and Launch

While Python extensions typically do not require a build step in isolation, this template is structured to properly interact with the Omniverse Kit SDK application build and packaging tooling.

Launching the extension typically requires that they be a part of an Omniverse [Service](../../apps/kit_service/README.md) or [Editor](../../apps/kit_base_editor/README.md) application.

**Adding an Extension to an Application**

To add your extension to an application, declare it in the dependencies section of the application's `.kit` file:

```toml
[dependencies]
"my_company.my_extension" = {}
```

#### Build with New Extensions
After a new extension has been added to the `.kit` file, the application should be rebuilt to ensure extensions are populated to the build directory.

### Customization

Customization of a Python Extension might involve writing new Python modules, or integrating existing libraries.

As is the case with Applications, extensions can also depend on and be depended on by other extensions. These can be custom developed extensions or those provided by the NVIDIA managed extension registry. A view of available registry extensions can be found within the Extension Manager accessible via the developer bundle available when running `./repo.sh launch --dev-bundle`(Linux) or `.\repo.bat launch --dev-bundle`(Windows) to launch the Base Editor or USD Explorer Application Templates (select `Developer` > `Utilities` > `Extensions`)

## Additional Learning
- [Kit Manual Extension Docs](https://docs.omniverse.nvidia.com/kit/docs/kit-manual/latest/guide/extensions_basic.html)
- [Kit App Template Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html)