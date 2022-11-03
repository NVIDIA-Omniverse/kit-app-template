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
