-- Shared build scripts from repo_build package.
repo_build = require("omni/repo/build")

-- Repo root
root = repo_build.get_abs_path(".")

-- Pull in new Premake options from repo_build-1.0.0
repo_build.setup_options()
-- Set variables so repo_kit_tools does not set default values for MSVC and WINSDK
MSVC_VERSION = _OPTIONS["visual-cxx-version"]
WINSDK_VERSION = _OPTIONS["winsdk-version"]

-- Run repo_kit_tools premake5-kit that includes a bunch of Kit-friendly tooling configuration.
kit = require("_repo/deps/repo_kit_tools/kit-template/premake5-kit")
kit.setup_all()


-- Registries config for testing
repo_build.prebuild_copy {
    { "%{root}/tools/deps/user.toml", "%{root}/_build/deps/user.toml" },
}

define_app("innoactive.usdcomposer.kit")
define_app("innoactive.usdcomposer_streaming.kit")
define_app("innoactive.usdcomposer.ar.kit")
define_app("innoactive.usdcomposer.ar_streaming.kit")
define_app("innoactive.usdcomposer.vr.kit")
define_app("innoactive.usdcomposer.vr_streaming.kit")

