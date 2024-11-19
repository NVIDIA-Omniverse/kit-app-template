# Windows C++ Developer Configuration

## Introduction

This document guides you through setting up this repository for C++ development on Windows using Microsoft Visual Studio and the Windows SDK.

**For New Users:** If you are new to Windows C++ development, this guide provides a step-by-step installation of Visual Studio 2022 Community and the Windows SDK, ensuring you have all the components required for standard development tasks.

**For Advanced Configurations:** If you already have Visual Studio and the Windows SDK installed but wish to specify exact versions, this guide will help you configure your environment using the `[repo_build.msbuild]` configuration within `repo.toml` at the project root.

## Configuration

To enable the Windows C++ build process:

- Set the `"platform:windows-x86_64".enabled` flag to `true` in your `repo.toml` file:

  ```toml
  [repo_build.build]
  "platform:windows-x86_64".enabled = true
  ```

- Set the `link_host_toolchain` flag to `true` in your `repo.toml` file:

  ```toml
  [repo_build.msbuild]
  link_host_toolchain = true
  ```

**Note:** If you already have Visual Studio and the Windows SDK installed, this might be the only change needed. The tooling will auto-detect installed components.

## Microsoft Visual Studio and Windows SDK Setup

### Basic Installation

#### Installing Visual Studio 2022 Community

1. **Download Visual Studio Installer**

   ![VS Download](../vs_download.png)
   - Visit the [Visual Studio Downloads](https://visualstudio.microsoft.com/downloads/).
   - Click "Free download" under "Community".

2. **Run the Installer**
   - Open the downloaded installer.
   - Select "Community" edition and click "Install".

3. **Select Workloads**

   ![VS Workloads](../vs_workloads.png)
   - Check "Desktop development with C++".
   - This includes tools like the MSVC compiler and C++ libraries.

4. **Additional Components**
   ![VS Additional](../vs_additional.png)
   - If you need specific components, go to "Individual components".
   - Select additional tools as needed.

5. **Complete the Installation**
   - Proceed with the installation to download and set up all files.

#### Installing Windows SDK (as needed)

Usually, the Windows SDK is included with the "Desktop development with C++" workload. To verify or install it separately:

1. **Launch Visual Studio Installer**
   - Open the installer if it's not already running.

2. **Modify Installation**

   ![VS Modify](../vs_modify.png)
   - Click "Modify" on your Visual Studio installation.

3. **Verify Windows SDK**

   ![VS WinSDK Verify](../vs_winsdk_verify.png)
   - Ensure "Windows SDK" is selected under "Optional" sections or "Individual components".

4. **Apply Changes**
   - Click "Modify" to install or update the SDK.

### Configuring an Existing Installation

#### Default Installation Paths

If Visual Studio and the Windows SDK are installed in default locations, the build tooling will auto-detect them without additional configuration.

- Default Windows SDK: `C:\Program Files (x86)\Windows Kits`
- Default Visual Studio 2019: `C:\Program Files (x86)\Microsoft Visual Studio`
- Default Visual Studio 2022: `C:\Program Files\Microsoft Visual Studio`

#### Non-Default Installation Paths

For installations at non-standard paths, specify them in `repo.toml`:

```toml
[repo_build.msbuild]
vs_path = "D:\\CustomPath\\Visual Studio\\2022\\Community"
winsdk_path = "D:\\CustomPath\\Windows Kits\\10\\bin\\10.0.19041.0"
```

Adjust and save the paths as needed.

**Note:** If the path entered is incorrect or invalid, the build system will fall back to auto-detection.

#### Multiple Installations

For multiple Visual Studio or Windows SDK installations, the latest version is used by default. If unspecified, default edition preference is "Enterprise", "Professional", "Community". To specify preferred versions, editions, or paths:

##### Visual Studio

```toml
[repo_build.msbuild]
vs_version = "vs2022"
vs_edition = "Community"
vs_path = "D:\\AnotherPath\\Visual Studio\\2022\\Enterprise\\"
```

##### Windows SDK

```toml
[repo_build.msbuild]
winsdk_version = "10.0.19041.0"
winsdk_path = "D:\\CustomSDKPath\\Windows Kits\\10\\bin\\10.0.19041.0"
```

With these configurations, you control which versions the build system uses, ensuring consistency in environments with multiple installations.

## Additional Resources
- [Repo Build Documentation](https://docs.omniverse.nvidia.com/kit/docs/repo_build/1.0.0/)