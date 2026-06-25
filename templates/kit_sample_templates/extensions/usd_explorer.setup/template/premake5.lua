-- Use folder name to build extension name and tag. Version is specified explicitly.
local ext = get_current_extension_info()

project_ext (ext)

-- Link only those files and folders into the extension target directory
repo_build.prebuild_link {
    { "data", ext.target_dir.."/data" },
    { "docs", ext.target_dir.."/docs" },
    { "layouts", ext.target_dir.."/layouts" },
    { "{{ python_module_toplevel }}", ext.target_dir.."/{{ python_module_toplevel }}" },
}
