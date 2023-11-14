-- Shared build scripts from repo_build package.
repo_build = require("omni/repo/build")

-- Repo root
root = repo_build.get_abs_path(".")

-- Execute the kit template premake configuration, which creates the solution, finds extensions, etc.
dofile("_repo/deps/repo_kit_tools/kit-template/premake5.lua")

-- Registries config for testing
repo_build.prebuild_copy {
    { "%{root}/tools/deps/user.toml", "%{root}/_build/deps/user.toml" },
}

-- Apps: for each app generate batch files and a project based on kit files (e.g. my_name.my_app.kit)
define_app("omni.usd_explorer")
define_app("my_name.my_app")

-- App warmup script for the Launcher
create_app_warmup_script("omni.usd_explorer", {
     args = "--exec \"open_stage.py ${SCRIPT_DIR}exts/omni.usd_explorer.setup/data/BuiltInMaterials.usda\" --/app/warmupMode=1 --no-window --/app/extensions/excluded/0='omni.kit.splash' --/app/extensions/excluded/1='omni.kit.splash.carousel' --/app/extensions/excluded/2='omni.kit.window.splash' --/app/settings/persistent=0 --/app/settings/loadUserConfig=0 --/structuredLog/enable=0 --/app/hangDetector/enabled=0 --/crashreporter/skipOldDumpUpload=1 --/app/content/emptyStageOnStart=1 --/app/window/showStartup=false --/rtx/materialDb/syncLoads=1 --/omni.kit.plugin/syncUsdLoads=1 --/rtx/hydra/materialSyncLoads=1 --/app/asyncRendering=0 --/app/file/ignoreUnsavedOnExit=1 --/renderer/multiGpu/enabled=0 --/app/quitAfter=10"
})
