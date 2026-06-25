-- Setup the extension.
local ext = get_current_extension_info()
project_ext(ext)

-- Link folders that should be packaged with the extension.
repo_build.prebuild_link {
    { "data", ext.target_dir.."/data" },
    { "docs", ext.target_dir.."/docs" },
}

-- Build the C++ plugin that will be loaded by the extension.
project_ext_plugin(ext, "{{ extension_name }}.plugin")
    add_files("include", "include/{{ python_module_path }}")
    add_files("source", "plugins/{{ extension_name }}")
    includedirs { "include", "plugins/{{ extension_name }}" }

-- Build Python bindings that will be loaded by the extension.
project_ext_bindings {
    ext = ext,
    project_name = "{{ extension_name }}.python",
    module = "{{ library_name }}",
    src = "bindings/python/{{ extension_name }}",
    target_subdir = "{{ python_module_path }}"
}
    includedirs { "include" }
    repo_build.prebuild_link {
        { "python/impl", ext.target_dir.."/{{ python_module_path }}/impl" },
        { "python/tests", ext.target_dir.."/{{ python_module_path }}/tests" },
    }

-- Build the C++ plugin that will be loaded by the tests.
project_ext_tests(ext, "{{ extension_name }}.tests")
    add_files("source", "plugins/{{ extension_name }}.tests")
    includedirs { "include", "plugins/{{ extension_name }}.tests", "%{target_deps}/doctest/include" }
