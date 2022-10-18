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
4. Run `_build\windows-x86_64\release\my_name.my_app.bat` (or other apps) to open an example kit application.

You should have now launched your simple kit based application!

![Simple App Window](docs/images/simple_app_window.png)

### Package

To package run `package.bat`. Package will be created in `_build/packages` folder.

To use package - unzip and run `link_app.bat` inside the package once before running.

Packaging just zips everything in `_build/[platform]/release` folder, using it as a root. Linked app (`baseapp`) and kit (`kit`) folders are skipped.

### Changing a Base App

When building 2 folder links are created:
    * `_build/[platform]/release/baseapp` link to Omniverse App (e.g. Code)
    * `_build/[platform]/release/kit` link to kit inside of the app above (same as `_build/[platform]/release/baseapp/kit`)

In `repo.toml` app name and version are specified and can be changed:

```toml
[repo_kit_link_app]
app_name = "code"   # App name.
app_version = ""    # App version. Empty means latest. Specify to lock version, e.g. "2022.2.0-rc.3"
```

After changing run `build.bat` again to create new app links.

# Keep Learning: Launching Apps

If you look inside `bat`/`sh` app script runner file it just launches kit and passes kit file (`my_name.my_app.kit`).
Application kit file defines app configuration. *Omniverse Kit* is core application runtime for Omniverse Applications. Think of it as `python.exe`. It is a small runtime, that enables all the basics, like settings, python, logging and searches for extensions. **Everything else is an extension.** You can run only this new extension without running any big *App* like *Code*:

There are 2 other apps examples: viewport and editor: `my_name.my_app.viewport.kit` and `my_name.my_app.editor.kit`. Try running them.

For example here is what you see if you launch the Editor version
![Documentation App](docs/images/editor_app.png)

# Repository Content

## Repository Shared Extensions

The repository contains few extensions that are shared amongst the sample applications that we showcase.

### Setup Extension: `my_name.my_app.setup`

It is standard practice when building applications to have a setup extensions that enable you to set up the layout of the relevant windows and configure the menu and various things that happen on startup.

Look at the documentation for **my_name.my_app.setup** to see more details. Its code is also deeply documented so you can review what each parts are doing

### Window Extension: `my_name.my_app.window`

Is an example extension that create a window for your application.
The Window content itself is just for demonstration purpose and doesn't do anything but it is used in the various applications to show how it can be added to a collection of other Extensions coming from Kit or Code

Similar to the setup one, check the documentation directly into the window extension and review the code for more details

## Apps

### Simple App Window: `my_name.my_app.kit`

![Simple App Window](./docs/images/simple_app_window.png)

The simple application showcase how to create a very basic Kit based application showing a simple window.

It is leveraging the kit compatibility mode for the UI that enable it to run on virtually any computer with a GPU.

It use the window extension example that shows how you can create an extensions that show the window into your application.

### Editor App: `my_name.my_app.editor.kit`

![Editor App](./docs/images/editor_app.png)

The simple Editor application showcase how you can start leveraging more of the Omnvierse Shared Extension around USD editing to create an application that have the basic feature from something like Create.

It will require a RTX compatible GPU, Turing or above.

You can see how it use the kit.QuickLayout to setup the example Window at the bottom next to the Content Browser, off couse you can choose your own layout and add more functionality and Windows


### Simple Viewport App: `my_name.my_app.viewport.kit`

![Simple Viewport App](./docs/images/simple_viewport_app.png)

The simple viewport application showcase how to create an application that leverage the RTX Renderer and the Kit Viewport to visulise USD files.

It will require a RTX compatible GPU, Turing and above.

The Functionality is very limited to mostly viewing the data, and is just base as a starting point for somethign you might want to build from.

you can see how it use the kit.QuickLayout to setup the example Window on the right of the Viewport but you can setup any layout that you need.

# Choosing Names

In this repository we use the `my_name` and `my_app` token for our app and extensions naming, the purpose is to outline where you should use `your company/name id` and `name for your app`

## Brand (Company/Person) Name: `my_name`

For example most Omniverse based extenions or application `my_name` is `omni`.
like `omni.kit.window.extensions` for an extensions or `omni.create` for an application.

We recommend that you use a clear and unique name for that and use it for all your apps and extensions.

### Few rules to use when selecting it

1. Don't use generic name like `bob` or `cloud`
2. Don't use `omni` as this is reserved for NVIDIA Application or Extensions
3. Be consistent, select one and stick to it

## App Name: `my_app`

When building applications you might want to *namespace* the extension into the app name they belong too.
like `omni.code` for an application where we have then `omni.code.setup` etc.

For that name you have more freedom as it is already in your `my_name` namespace so should not clash with other people "editor" or "viewer"

It would then be acceptable to have `my_name.editor` or `my_name.player` but you still want to think about giving your application some good identity.

## Shared Extensions

Aside for the extension you build especially for your App there might be some that you want to make more generic and re-used across applications.

That is very possible and even recommended, that is how Omniverse Shared Extensions are build, we have them in namespace like `omni.kit.widget.` or `omni.kit.window.`

Similarly you can have `<my_name>.widget.` and use that namespace to have your great Combox Box or advance List selection widget. those name will be greatly useful when other developers or users want to start using your extensions, it will make it clear those come from you `<my_name>` and your can outline in the `extension.toml` repository field where they are coming from.


## Contributing
The source code for this repository is provided as-is and we are not accepting outside contributions.
