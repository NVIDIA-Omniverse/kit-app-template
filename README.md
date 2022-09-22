# Omniverse Kit App Template

This project contains everything necessary to develop and package an Omniverse App.


## What Is an App?

Ultimately, an Omniverse Kit app is a `.kit` file. It is a single file extension. You can think of it as a tip of dependencies pyramid, a final extension that pulls everything.

Extensive documentation detailing what extensions are and how they work can be found [here](https://docs.omniverse.nvidia.com/py/kit/docs/guide/extensions.html).

## Getting Started

### Install Omniverse and some Apps

1. Install *Omniverse Launcher*: [download](https://www.nvidia.com/en-us/omniverse/download)
2. Install and launch one of *Omniverse* apps in the Launcher. This repo required *Code* installed.

### Build

1. Clone this repo to your local machine.
2. Open a command prompt and navigate to the root of your cloned repo.
3. Run `build.bat` to bootstrap your dev environment and build an example app.
4. Run `_build\windows-x86_64\release\omni.app.example.extension_browser.bat` to open an example kit application.

### Changing an App

When building 2 folder links are created:
    * `_build/[platform]/release/baseapp` link to Omniverse App (e.g. Code)
    * `_build/[platform]/release/kit` link to kit inside of the app above (same as ``_build/[platform]/release/baseapp/kit`)

In `repo.toml` app name and version are specified and can be changed:

```toml
[repo_kit_link_app]
app_name = "code"   # App name.
app_version = ""    # App version. Empty means latest. Specify to lock version, e.g. "2022.2.0-rc.3"
```

After changing run `build.bat` again to create new app links.

## Contributing
The source code for this repository is provided as-is and we are not accepting outside contributions.
