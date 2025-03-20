# Usage and Troubleshooting

This section provides high-level information and guidance related to using the Kit App Template repository, along with troubleshooting tips for common issues.

## Usage Information

### A Project per Repository
The `build` and `package` tooling provided in this repository is designed to capture all code and assets contained within the `/source` directory. Each time the `template new` command is executed, a new application or extension is created within `/source`.

For purposes of experimentation and initial development, housing all working assets within the `/source` directory is reasonable. However, as the project matures or requires deployment, it is recommended to segregate projects (typically a single `.kit` file and any required custom extensions) to minimize build times and reduce the size of the resultant package.

### Applications and Extensions
From the perspective of the Omniverse Kit SDK, everything is considered an extension. The `.kit` files that define applications are simply a convenient method to assemble and configure a set of extensions for specific functionalities, while extensions (and combinations thereof) can act as modular components fulfilling particular tasks.

For additional information on the Kit SDK and how to create applications and extensions, refer to the [Kit SDK Companion Tutorial](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template/latest/docs/intro.html).

### Extendable Templates and Tools
The templates and tools provided in this repository are designed to be extendable.

#### Templates
Templates consist of a directory structure and boilerplate code containing variables configurable at the time the templates are applied. The `templates.toml` file, located in `templates/templates.toml`, specifies which templates the tooling recognizes.

#### Tooling
Most tooling is not stored directly within the repository; it is instead downloaded from a remote registry upon the initial use of the tooling. This design allows the tooling to be updated independently of the repository. The framework used for the tooling also supports the definition of custom tools.

To see this extensibility in action, explore the local tooling defined within `tools/repoman`, specifically the `launch` tool. Configuration for this tool within the repo is delineated in the `repo_tools.toml` file at the root of the repository.


## Troubleshooting
This section outlines potential issues that may arise when using the Kit App Template repository.

### Setup & Configuration Issues

#### Windows Long Path
Due to path length limitations on Windows it is recommended to place repository artifacts in a location closer to the root of the drive. This will help avoid issues with the path lengths when building and packaging applications.

#### exFAT Drive Compatibility Limitations
The Kit App Template repository and associated tooling are designed to work with drive formats that support junctions/symlinks. If you are using an exFAT-formatted drive, you may encounter errors during the build process. To resolve this issue, consider using a different drive format such as NTFS.

#### Extension Naming Guidelines
When creating custom extensions, avoid using a top-level namespace that is the same as any built-in Python module (e.g., “random”, “sys”, “xml”). Doing so can cause import conflicts if Omniverse Kit attempts to load extensions from these Python modules. For example, instead of “random.extension.name”, use a unique namespace such as “my_company.my_app.my_extension”.

### Rendering & Performance

#### Initial Rendering Startup Times
When launching an application that requires the RTX renderer, the first launch may take considerably longer than subsequent launches due to shader compilation. **The initial launch can take between 5 to 8 minutes.** Subsequent launches of RTX-enabled applications will be faster as the renderer caches the compiled shaders.

### Build & Packaging

#### Build Issues
The `template new` tooling ensures that any created application is properly configured to build. However, extensive manual changes can occasionally cause the configuration and `/source` directory contents to become unsynchronized. The specifics of any given build are determined by three main factors:

1) The state of the top-level `repo.toml` file, especially the `.kit` files listed in the `apps` array within the `[[repo_precache_exts]]` section.

2) The state of the `premake5.lua` file, particularly which `.kit` files are set to build via `define_app()` (e.g., `define_app("my_company.my_service.kit")`).

3) The state of the `source` directory, specifically which `.kit` files are present within `source/apps`.

**To ensure a build proceeds as intended, verify that the same `.kit` files are listed or defined in all three locations.**

For a clean build, use the command `./repo.sh build -c` or `.\repo.bat build -c` to clean the build directory before building.

#### Caching and Persistent Data
The Omniverse Kit SDK caches data and required dependencies to improve build and runtime performance. If you encounter issues with stale, incorrect, or missing dependencies/data, consider clearing application specific and/or global cache locations:

- **Application Specific Caches**: Clearing application specific caches and settings can be done by adding arguments at launch time.

  Linux:
    ```bash
    ./repo.sh launch -- --clear-cache --clear-data --reset-user
    ```
  Windows:
    ```powershell
    .\repo.bat launch -- --clear-cache --clear-data --reset-user
    ```
  Upon selecting a `.kit` file to launch, the application will clear the cache and data directories before starting.

- **Global Cache Locations (:warning:Use with Caution:warning:)**:

  **IMPORTANT NOTE -** Clearing any of the following cache locations will require a full rebuild of any existing applications.

  Deleting the directories responsible for caching ensures a fresh build of the relevant caches during the next build.

  - **Extension AND Application Data Cache Locations**: `$HOME/.local/share/ov` on Linux, `%LOCALAPPDATA%\ov` on Windows.

  - **Tooling AND Dependency Cache Location**:

    - **Packman :** `$PM_PACKAGES_ROOT` on Linux, `%PM_PACKAGES_ROOT%` on Windows.

      - If `PM_PACKAGES_ROOT` is not set on your system, the default location will revert to `$HOME/.cache/packman` on Linux, `{drive where packman is launched from}\packman-repo` on Windows.

    - **uv :** `$HOME/.cache/uv` on Linux, `%LOCALAPPDATA%\uv\cache` on Windows.



#### Space Constraints Due to Docker Artifacts
When performing extensive local testing of container images created via `repo package --container`, Docker artifacts can accumulate over time, consuming significant disk space.

`docker system df` can be used to determine disk space utilized by Docker objects. To reclaim space, consider the following options:

1. **Regular Safe Cleanup**:
    - **Command**: `docker container prune`
    - **Description**: This command removes all stopped containers, which is typically safe and helps manage disk space without affecting images, networks, or volumes.
    - **Use**: Recommended for regular maintenance.

2. **Extensive Cleanup (:warning:Use with Caution:warning:)**:
    - **Command**: `docker system prune`
    - **Description**: This command removes all unused containers, networks, images, and optionally volumes. It is akin to running a `rm -rf` for Docker resources.
    - **Warning**: Use this command carefully, as it will remove many resources indiscriminately. Ensure you review and understand what will be deleted.

For image-specific cleanup, use `docker images` to list all images and `docker rmi <image>` to manually remove those that are no longer needed.