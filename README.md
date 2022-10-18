# Omniverse Kit App Template

This project contains everything necessary to develop and package an Omniverse App.


## What Is an App?

Ultimately, an Omniverse Kit app is a `.kit` file. It is a single file extension. You can think of it as the tip of a dependencies pyramid, a final extension that pulls in everything.

Extensive documentation detailing what extensions are and how they work can be found [here](https://docs.omniverse.nvidia.com/py/kit/docs/guide/extensions.html).

## Getting Started

### Install Omniverse and some Apps

1. Install *Omniverse Launcher*: [download](https://www.nvidia.com/en-us/omniverse/download)
2. Install and launch one of *Omniverse* apps in the Launcher. This repo requires *Code* installed.

### Build

1. Clone this repo to your local machine.
2. Open a command prompt and navigate to the root of your cloned repo.
3. Run `build.bat` to bootstrap your dev environment and build an example app.
4. Run `_build\windows-x86_64\release\my_name.my_app.bat` (or other apps) to open an example kit application.

You should have now launched your simple kit-based application!

![Simple App Window](docs/images/simple_app_window.png)

### Package

To package, run `package.bat`. The package will be created in the `_build/packages` folder.

To use the package, unzip and run `link_app.bat` inside the package once before running.

Packaging just zips everything in the `_build/[platform]/release` folder, using it as a root. Linked app (`baseapp`) and kit (`kit`) folders are skipped.

### Changing a Base App

When building 2 folder links are created:
    * `_build/[platform]/release/baseapp` link to Omniverse App (e.g. Code)
    * `_build/[platform]/release/kit` links to kit inside of the app above (same as `_build/[platform]/release/baseapp/kit`)

In `repo.toml`, the baseapp name and version are specified and can be changed:

```toml
[repo_kit_link_app]
app_name = "code"   # App name.
app_version = ""    # App version. Empty means latest. Specify to lock version, e.g. "2022.2.0-rc.3"
```

After editing `repo.toml`, run `build.bat` again to create new app links.

# Keep Learning: Launching Apps

If you look inside the `bat`/`sh` app script runner file it just launches kit and passes a kit file (`my_name.my_app.kit`).
Application kit files define app configuration. *Omniverse Kit* is the core application runtime for Omniverse Applications. Think of it as `python.exe`. It is a small runtime, that enables all the basics like settings, python, logging and searches for extensions. **Everything else is an extension.** You can run only this new extension without running any big *App* like *Code*:

There are 2 other app examples: `my_name.my_app.viewport.kit` and `my_name.my_app.editor.kit`. Try running them.

For example here is what you see if you launch the Editor version
![Documentation App](docs/images/editor_app.png)

# Repository Content

## Repository Shared Extensions

The repository contains a few extensions that are shared amongst the sample applications that we showcase.

### Setup Extension: `my_name.my_app.setup`

It is standard practice when building applications to have a setup extension that enables you to set up the layout of the relevant windows and configure the menu and various things that happen on startup.

Look at the documentation for **my_name.my_app.setup** to see more details. Its code is also deeply documented so you can review what each part is doing.

### Window Extension: `my_name.my_app.window`

This example extension creates a window for your application.
The Window content itself is just for demonstration purposes and doesn't do anything but it is used in the various applications to show how it can be added to a collection of other Extensions coming from Kit or Code.

Similar to the setup extension, check the window extension's included documentation and review the code for more details

## Apps

### Simple App Window: `my_name.my_app.kit`

![Simple App Window](./docs/images/simple_app_window.png)

The simple application showcases how to create a very basic Kit-based application showing a simple window.

It leverages the kit compatibility mode for the UI that enables it to run on virtually any computer with a GPU.

It uses the window extension example that shows how you can create an extension that shows the window in your application.

### Editor App: `my_name.my_app.editor.kit`

![Editor App](./docs/images/editor_app.png)

The simple Editor application showcases how you can start leveraging more of the Omniverse Shared Extensions around USD editing to create an application that has the basic features of an app like Create.

It will require an RTX compatible GPU, Turing or above.

You can see how it uses the kit.QuickLayout to setup the example Window at the bottom next to the Content Browser, of course you can choose your own layout and add more functionality and Windows.


### Simple Viewport App: `my_name.my_app.viewport.kit`

![Simple Viewport App](./docs/images/simple_viewport_app.png)

This simple viewport application showcases how to create an application that leverages the RTX Renderer and the Kit Viewport to visualize USD files.

It will require an RTX compatible GPU, Turing or above.

The functionality is very limited to mostly viewing the data, and is just a starting point for something you might want to build from.

You can see how it uses the kit.QuickLayout to setup the example Window on the right of the Viewport but you can setup any layout that you need.

# Choosing Names

In this repository we use the `my_name` and `my_app` token for our app and extensions naming, the purpose is to outline where you should use `your company/name id` and `name for your app`

## Brand (Company/Person) Name: `my_name`

For example, for extensions or applications created by the Omniverse team `my_name` is `omni` like `omni.kit.window.extensions` for an extension or `omni.create` for an application.

We recommend that you use a clear and unique name for that and use it for all your apps and extensions.

### A few rules to follow when selecting it

1. Don't use a generic name like `bob` or `cloud`
2. Don't use `omni` as this is reserved for NVIDIA Applications or Extensions
3. Be consistent. Select one and stick to it

## App Name: `my_app`

When building applications you might want to *namespace* the extension within the app name they belong to like `omni.code` for an application where we have then `omni.code.setup` etc.

For that name you have more freedom as it is already in your `my_name` namespace so it should not clash with someone else's "editor" or "viewer".

It would then be acceptable to have `my_name.editor` or `my_name.player` but you still want to think about giving your application some good identity.

## Shared Extensions

Aside from the extension you build specifically for your App there might be some that you want to make more generic and reuse across applications.

That is very possible and even recommended. That is how Omniverse Shared Extensions are built. We have them in namespaces like `omni.kit.widget.` or `omni.kit.window.`

Similarly, you can have `<my_name>.widget.` and use that namespace to have your great ComboBox or advanced List selection widget. Those names will be very useful when other developers or users want to start using your extensions, it will make it clear those come from you (`<my_name>`) and your can outline in the `extension.toml` repository field where they are coming from.


## Contributing
The source code for this repository is provided as-is and we are not accepting outside contributions.
