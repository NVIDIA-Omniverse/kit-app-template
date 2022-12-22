# Omniverse Kit App Template

[Omniverse Kit App Template](https://github.com/NVIDIA-Omniverse/kit-app-template) - is the place to start learning about developing Omniverse Apps.
This project contains everything necessary to develop and package an Omniverse App.

## Links

* [Repository](https://github.com/NVIDIA-Omniverse/kit-app-template)
* [Full Documentation](https://docs.omniverse.nvidia.com/kit/docs/kit-app-template)

## What Is an App?

Ultimately, an Omniverse Kit app is a `.kit` file. It is a single file extension. You can think of it as the tip of a dependencies pyramid, a final extension that pulls in everything.

Extensive documentation detailing what extensions are and how they work can be found [here](https://docs.omniverse.nvidia.com/py/kit/docs/guide/extensions.html).

## Getting Started

### Install Omniverse and some Apps

1. Install *Omniverse Launcher*: [download](https://www.nvidia.com/en-us/omniverse/download)
2. Install and launch one of *Omniverse* apps in the Launcher. This repo requires the latest *Create* installed.

### Build

1. Clone [this repo](https://github.com/NVIDIA-Omniverse/kit-app-template) to your local machine.
2. Open a command prompt and navigate to the root of your cloned repo.
3. Run `build.bat` to bootstrap your dev environment and build an example app.
4. Run `_build\windows-x86_64\release\my_name.my_app.bat` (or other apps) to open an example kit application.

You should have now launched your simple kit-based application!

### Package

To package, run `package.bat`. The package will be created in the `_build/packages` folder.

To use the package, unzip and run `link_app.bat` inside the package once before running.

Packaging just zips everything in the `_build/[platform]/release` folder, using it as a root. Linked app (`baseapp`) and kit (`kit`) folders are skipped.

### Changing a Base App

When building 2 folder links are created:
    * `_build/[platform]/release/baseapp` link to Omniverse App (e.g. Create)
    * `_build/[platform]/release/kit` links to kit inside of the app above (same as `_build/[platform]/release/baseapp/kit`)

In `repo.toml`, the baseapp name and version are specified and can be changed:

```toml
[repo_kit_link_app]
app_name = "create"   # App name.
app_version = ""    # App version. Empty means latest. Specify to lock version, e.g. "2022.2.0-rc.3"
```

After editing `repo.toml`, run `build.bat` again to create new app links.

## Keep Learning: Launching Apps

If you look inside the `bat`/`sh` app script runner file it just launches kit and passes a kit file (`my_name.my_app.kit`).
Application kit files define app configuration. *Omniverse Kit* is the core application runtime for Omniverse Applications. Think of it as `python.exe`. It is a small runtime, that enables all the basics like settings, python, logging and searches for extensions. **Everything else is an extension.** You can run only this new extension without running any big *App* like *Create*:

There are 2 other app examples: `my_name.my_app.viewport.kit` and `my_name.my_app.editor.kit`. Try running them.

## Contributing
The source code for this repository is provided as-is and we are not accepting outside contributions.
