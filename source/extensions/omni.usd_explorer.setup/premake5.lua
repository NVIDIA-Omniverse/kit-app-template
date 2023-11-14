-- Use folder name to build extension name and tag.
local ext = get_current_extension_info()

project_ext (ext)

-- Link only those files and folders into the extension target directory
repo_build.prebuild_link { "docs", ext.target_dir.."/docs" }
repo_build.prebuild_link { "data", ext.target_dir.."/data" }
repo_build.prebuild_link { "omni", ext.target_dir.."/omni" }
repo_build.prebuild_link { "layouts", ext.target_dir.."/layouts" }
