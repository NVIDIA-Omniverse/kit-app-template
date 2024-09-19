# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from functools import partial
from typing import Any, Dict, List, Tuple, Union

import carb.dictionary
import carb.settings
import omni.ui as ui

MODAL_TOOL_ACTIVE_PATH = "/app/tools/modal_tool_active"


class UIStateManager:
    """Manages the state of UI elements based on settings and modal tool state."""
    def __init__(self):
        self._settings = carb.settings.acquire_settings_interface()

        self._modal_changed_sub = \
            self._settings.subscribe_to_node_change_events(
                MODAL_TOOL_ACTIVE_PATH,
                self._on_modal_setting_changed
            )

        self._hide_on_modal: List[Tuple[str, bool]] = []
        self._modal_restore_window_states: Dict[str, bool] = {}
        self._settings_dependencies: Dict[Tuple[str, str], Dict[Any, Any]] = {}
        self._settings_changed_subs = {}
        self._window_settings = {}

        self._window_vis_changed_id = \
            ui.Workspace.set_window_visibility_changed_callback(
                self._on_window_vis_changed
            )

    def destroy(self):
        """Unsubscribe from all events and clean up."""
        if self._settings:
            if self._modal_changed_sub:
                self._settings.unsubscribe_to_change_events(
                    self._modal_changed_sub
                )
            self._settings = None
        self._hide_on_modal = []
        self._modal_restore_window_states = {}
        self._settings_dependencies = {}
        self._window_settings = {}
        if self._window_vis_changed_id:
            ui.Workspace.remove_window_visibility_changed_callback(
                self._window_vis_changed_id
            )
        self._window_vis_changed_id = None

    def __del__(self):
        """Ensure that the object is cleaned up."""
        self.destroy()

    def add_hide_on_modal(
            self, window_names: Union[str, List[str]], restore: bool
    ):
        """Add a window to the list of windows to hide when the modal
        tool is active."""
        if isinstance(window_names, str):
            window_names = [window_names]
        for window_name in window_names:
            if window_name not in self._hide_on_modal:
                self._hide_on_modal.append((window_name, restore))

    def remove_hide_on_modal(self, window_names: Union[str, List[str]]):
        """Remove a window from the list of windows to hide when the modal"""
        if isinstance(window_names, str):
            window_names = [window_names]
        self._hide_on_modal = [item for item in self._hide_on_modal if item[0] not in window_names]

    def add_window_visibility_setting(
            self, window_name: str, setting_path: str
    ):
        """Add a setting that controls the visibility of a window."""
        window = ui.Workspace.get_window(window_name)
        if window is not None:
            self._settings.set(setting_path, window.visible)
        else:
            # handle the case when the window is created later
            self._settings.set(setting_path, False)
        if window_name not in self._window_settings.keys():
            self._window_settings[window_name] = []
        self._window_settings[window_name].append(setting_path)

    def remove_window_visibility_setting(
            self, window_name: str, setting_path: str
    ):
        """Remove a setting that controls the visibility of a window."""
        if window_name in self._window_settings.keys():
            setting_list = self._window_settings[window_name]
            if setting_path in setting_list:
                setting_list.remove(setting_path)
                if len(setting_list) == 0:
                    del self._window_settings[window_name]

    def remove_all_window_visibility_settings(self, window_name: str):
        """Remove all settings that control the visibility of a window."""
        if window_name in self._window_settings.keys():
            del self._window_settings[window_name]

    def add_settings_dependency(
            self, source_path: str, target_path: str, value_map: Dict[Any, Any]
    ):
        """Add a dependency between two settings. When the source setting"""
        key = (source_path, target_path)
        if key in self._settings_dependencies.keys():
            carb.log_error(f'Settings dependency {source_path} -> {target_path} already exists. Ignoring.')
            return

        self._settings_dependencies[key] = value_map
        self._settings_changed_subs[key] = \
            self._settings.subscribe_to_node_change_events(
                source_path,
                partial(self._on_settings_dependency_changed, source_path)
            )

    def add_settings_copy_dependency(self, source_path: str, target_path: str):
        """Add a dependency between two settings. When the source setting"""
        self.add_settings_dependency(source_path, target_path, None)

    def remove_settings_dependency(self, source_path: str, target_path: str):
        """Remove a dependency between two settings."""
        key = (source_path, target_path)
        if key in self._settings_dependencies.keys():
            del self._settings_dependencies[key]
        if key in self._settings_changed_subs.keys():
            sub = self._settings_changed_subs.pop(key)
            self._settings.unsubscribe_to_change_events(sub)

    def _on_settings_dependency_changed(self, path: str, _item, _event_type):
        """Callback for when a setting changes."""
        value = self._settings.get(path)
        # setting does not exist
        if value is None:
            return
        target_settings = [source_target[1] for source_target in
                           self._settings_dependencies.keys() if
                           source_target[0] == path]
        for target_setting in target_settings:
            value_map = self._settings_dependencies[(path, target_setting)]
            # None means copy everything
            if value_map is None:
                self._settings.set(target_setting, value)
            elif value in value_map.keys():
                self._settings.set(target_setting, value_map[value])

    def _on_modal_setting_changed(self, _item, _event_type):
        """Callback to handle changes to window visibility based on the
         app mode setting."""
        modal = self._settings.get_as_bool(MODAL_TOOL_ACTIVE_PATH)
        if modal:
            self._hide_windows()
        else:
            self._restore_windows()

    def _hide_windows(self):
        """Hide all windows that are set to be hidden when the modal tool
        is active."""
        for window_info in self._hide_on_modal:
            window_name, restore_later = window_info[0], window_info[1]
            window = ui.Workspace.get_window(window_name)
            if window is not None:
                if restore_later:
                    self._modal_restore_window_states[window_name] = \
                        window.visible
                window.visible = False

    def _restore_windows(self):
        """Restore all windows that were hidden when the modal tool
        was active."""
        for window_info in self._hide_on_modal:
            window_name, restore_later = window_info[0], window_info[1]
            if restore_later:
                if window_name in self._modal_restore_window_states.keys():
                    old_visibility = \
                        self._modal_restore_window_states[window_name]
                    if old_visibility is not None:
                        window = ui.Workspace.get_window(window_name)
                        if window is not None:
                            window.visible = old_visibility
                            self._modal_restore_window_states[window_name] = \
                                None

    def _on_window_vis_changed(self, title: str, state: bool):
        """Callback to handle changes to window visibility."""
        if title in self._window_settings.keys():
            for setting in self._window_settings[title]:
                self._settings.set_bool(setting, state)
