# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


## [106.2.0] - 2024-10-08

### Changed
- Updated to Kit 106.2.0
- Refactored Viewer Template default tests to avoid unnecessary dependencies

### Removed
- Unused `simulation` menu item from USD Composer Template


## [106.1.0] - 2024-09-17

### Added
- Support for containerization of streaming applications and services via `repo package --container`
- Support extension only builds via `repo build`
- Support the ability to launch created containers via `repo launch --container`
- repo_usd tooling dependency
- Support for USD Viewer Template to send scene loading state to client via messaging

### Changed
- Aligned default testing for applications and extensions
- Update and align code formatting/style across templates

### Fixed
- Extra setup extensions appear in standard extension template menu
- "Could not find cgroup memory limit" error during build
- Fixed default manipulator pivot back to "bounding box base" in USD Explorer Template


## [106.0.2] - 2024-07-29

### Added
- Support for local streaming configurations for UI based Applications
- Support for multiple setup extensions per application
- Ability to pass arguments to Kit via the 'repo launch` tool.
- USD Composer Application Template and Documentation
- USD Viewer Application Template and Documentation
- USD Composer Setup Extension and Documentation
- USD Viewer Setup Extension and Documentation
- Repository Issue Templates Bug/Question/Feature Request
- Omniverse Product-Specific Terms (PRODUCT_TERMS_OMNIVERSE)
- Support for type ordering in templates.toml
- Metrics Assembler to Kit Base Editor Template to support unit correct assets
- Support for automatic launch if only single `.kit` file is present in `source/apps`

### Changed
- Updated all relevant application templates READMEs to reflect the addition of local streaming configurations
- Updated .gitattributes to ensure LFS is used for all relevant file types
- Updated .gitignore to exclude streaming app event traces
- Updated .vscode/launch.json to better support debugging behavior
- Updated LICENSE to separate NVIDIA License from Omniverse Product-Specific Terms
- Updated top level README.md to reflect additional templates and improve documentation clarity
- Updated Developer Bundle extension availability and corresponding documentation
- Updated public extension registry to reflect current Kit 106 registry location
- Updated templates.toml to support multiple setup extensions and new templates


## [106.0.0] - 2024-06-07

### Added
- Kit Base Editor Application Template and Documentation
- USD Explorer Application Template and Documentation
- USD Explorer Setup Extension and Documentation
- Kit Service Template and Documentation
- Simple Python Extension Template and Documentation
- Simple C++ Extension Template and Documentation
- Python UI Extension Template and Documentation
- Template configuration file (templates.toml)
- Added local `repo launch` tool for launching applications and fat packages directly
- Added local `repo package` functionality to improve package naming
- Omniverse EULA acceptance to Kit App Template via tooling
- tasks.json for better VSCode support
- SECURITY.md for security policy
- Notice for data collection and use
- Early access Developer Bundle extensions
- Kit App Template related Developer Bundle documentation (developer_bundle_extensions.md)
- Kit App Template related repo tools documentation (kit_app_template_tooling_guide.md)
- Usage and troubleshooting documentation for Kit App Template (usage_and_troubleshooting.md)
- repo_tools.toml to configure local repo tools

### Changed
- Updated repo_kit_template tooling to support Applications and Extensions
- Updated repo_kit_template tooling to allow for application setup extensions
- Updated top level README.md to reflect updated tooling and templates
- Updated LICENSE.md to reflect updated tooling and templates
- Updated .gitattributes to reflect use of templates rather directly from source
- Added configuration to repo.toml to support new tools and templates

### Removed
- Top level build .bat/.sh scripts in favor of using `repo build` directly
- Predefined `define_app` declarations from `premake5.lua` in favor of developer defined applications
- Predefined source/apps in favor of templates for developers to build from