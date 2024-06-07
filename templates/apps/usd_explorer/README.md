# USD Explorer App Template

![USD Explorer Hero Image](../../../readme-assets/usd_explorer.jpg)

**Based On:** `Omniverse Kit SDK 106.0`

## Overview

The USD Explorer App Template is designed to provide a robust starting point for developers looking to visualize and interact with large-scale environments such as factories, warehouses, and other expansive scenes using Open Universal Scene Description (OpenUSD). This template showcases high-performance rendering, scene optimization,  live collaboration, and more. It is a great fit for interacting with large or complex 3D scenes.

By integrating advanced features such as instancing, optimization techniques, and new extension examples for planning, commenting, and reviewing, the USD Explorer Template simplifies the process of aggregating and examining large scenes. It offers a dual-mode UI, catering both to novices seeking ease of use and to advanced users requiring detailed scene manipulation capabilities.

### Use Cases

The USD Explorer Template is perfectly suited for:

- Visualizing complex industrial environments for planning and review.
- Collaborating on large-scale design projects in real-time.
- Building digital twins for industries to simulate and analyze real-world performance.

This template stands out by providing specialized tools for handling large scenes, making it an ideal choice for applications requiring detailed spatial analysis and collaborative review functionalities.

### Key Features

- **OpenUSD File Aggregation**: Seamlessly combine and manage multiple USD files in a unified scene.
- **Simple User Interface**: Intuitive interface designed for ease of use by non-specialized personnel.
- **Dual Mode Interface**: Toggle between simplified and advanced user interfaces based on user proficiency.
- **Easy Navigation**: Tools for smoothly navigating through large-scale scenes.
- **Annotation Tools**: Integrated tools for annotating and commenting within the scene for collaborative reviewing.
- **CAD Converter Import**: Directly import and convert CAD files into the OpenUSD format.
- **Live Collaboration**: Real-time collaboration tools allowing multiple users to view and edit scenes concurrently.
- **Content Library - Materials & Assets**: Extensive library of materials and assets for scene enhancement and realism.

## Usage

### Getting Started

To get started with the Kit Base Editor, ensure your development environment meets the prerequisites outlined in the top-level README.

#### Cloning the Repository

```bash
git clone https://github.com/NVIDIA-Omniverse/kit-app-template.git
cd kit-app-template
```

#### Create New Application

**Note for USD Explorer** : Some applications require setup extensions to function as intended. In the case of USD Explorer, the setup extension controls the configuration of the extensions within the application, their layout, and other settings. During Application configuration, you will be prompted for information about this extension.

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
- **? Select with arrow keys your desired template:** USD Explorer
- **? Enter name of application .kit file [name-spaced, lowercase, alphanumeric]:** [set application name]
- **? Enter application_display_name:** [set application display name]
- **? Enter version:** [set app version]

*The application template you have selected requires a setup extension.
Setup Extension -> omni_usd_explorer_setup*
- **? Enter name of extension [name-spaced, lowercase, alphanumeric]:** [set extension name]
- **? Enter extension_display_name:** [set extension display name]
- **? Enter version:** [set extension version]

### Build and Launch
Note that the build step will build all applications contained in the `source` directory. Outside of initial experimentation, it is recommended that you build only the application you are actively developing.

#### Build your application using the provided build scripts:

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

**? Select with arrow keys which App would you like to launch:** [Select the desired explorer application]

***NOTE:* The initial startup may take 5 to 8 minutes as shaders compile for the first time. After initial shader compilation, startup time will reduce dramatically**

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
- From the running application select `Developer` > `Utilities` > `Extensions`

- Browse and enable extensions of interest from the Extension Manager.
    - Enabling the extensions within the Extension Manager UI will allow you to try out the features of the extension in the currently running application.

    - To permanently add the extension to the application, you will need to add the extension to the `.kit` file. For example, adding the Layer View extension would require adding `omni.kit.widget.layers` to the dependencies section of the `.kit` file.

- For additional information on the Developer Bundle Extensions, refer to the [BETA - Developer Bundle Extensions](readme-assets/additional-docs/developer_bundle_extensions.md) documentation.


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
**Importantly** For an extension to become a persistent part of an application, the extension will need to be added to the `.kit` file.

```toml
[dependencies]
"extension.name" = {}
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
