# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from .stage_loading import LoadingManager
from .stage_management import StageManager
import omni.ext


# Any class derived from `omni.ext.IExt` in top level module (defined in
# `python.modules` of `extension.toml`) will be instantiated when extension
# gets enabled and `on_startup(ext_id)` will be called. Later when extension
# gets disabled on_shutdown() is called.
class Extension(omni.ext.IExt):
    """This extension manages creating the loading and stage
    messaging managers"""
    def on_startup(self):
        """This is called every time the extension is activated."""
        # Internal messaging state
        self._loading_manager: LoadingManager = LoadingManager()
        self._stage_manager: StageManager = StageManager()

    def on_shutdown(self):
        """This is called every time the extension is deactivated. It is used to
        clean up the extension state."""
        # Resetting the state.
        if self._loading_manager:
            self._loading_manager.on_shutdown()
            self._loading_manager = None
        if self._stage_manager:
            self._stage_manager.on_shutdown()
            self._stage_manager = None
