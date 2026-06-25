# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import carb
import carb.settings
import carb.tokens
import omni.ui as ui

from omni.kit.viewport.menubar.core import (
    DEFAULT_MENUBAR_NAME, SettingModel, SliderMenuDelegate,
)
from omni.kit.viewport.menubar.core import get_instance as get_menubar_instance
from omni.ui import color as cl

ICON_PATH = carb.tokens.get_tokens_interface().resolve("${% raw %}{{% endraw %}{{ extension_name }}{% raw %}}{% endraw %}/data/icons")

VIEW_MENUBAR_STYLE = {
    "MenuBar.Window": {"background_color": 0xA0000000},
    "MenuBar.Item.Background": {"background_color": 0},
    "Menu.Item.Background": {"background_color": 0}
}
VIEWPORT_CAMERA_STYLE = {
    "Menu.Item.Icon::Expand": {
        "image_url": f"{ICON_PATH}/caret_s2_right_dark.svg",
        "color": cl.viewport_menubar_light
    },
    "Menu.Item.Icon::Expand:checked": {
        "image_url":
        f"{ICON_PATH}/caret_s2_left_dark.svg"
    },
}


class MenubarHelper:
    """Helper class to manage menubar settings and style."""
    def __init__(self):
        self._settings = carb.settings.get_settings()

        # Set menubar background and style
        try:
            instance = get_menubar_instance()
            if not instance:  # pragma: no cover
                return

            default_menubar = instance.get_menubar(DEFAULT_MENUBAR_NAME)
            default_menubar.background_visible = True
            default_menubar.style.update(VIEW_MENUBAR_STYLE)
            default_menubar.show_separator = True
        except ImportError:  # pragma: no cover
            carb.log_warn("Viewport menubar not found!")

        try:
            import omni.kit.viewport.menubar.camera  # type: ignore
            self._camera_menubar_instance = \
                omni.kit.viewport.menubar.camera.get_instance()
            if not self._camera_menubar_instance:  # pragma: no cover
                return

            # Change expand button icon
            self._camera_menubar_instance._camera_menu._style.update(
                VIEWPORT_CAMERA_STYLE
            )
            # New menu item for camera speed
            self._camera_menubar_instance.register_menu_item(
                self._create_camera_speed, order=100
            )
            self._camera_menubar_instance.deregister_menu_item(
                self._camera_menubar_instance._camera_menu._build_create_camera
            )
        except ImportError:
            carb.log_warn("Viewport menubar not found!")
            self._camera_menubar_instance = None
        except AttributeError:  # pragma: no cover
            self._camera_menubar_instance = None

        # Hide default render and settings menubar
        self._settings.set(
            "/persistent/exts/omni.kit.viewport.menubar.render/visible", False
        )
        self._settings.set(
            "/persistent/exts/omni.kit.viewport.menubar.settings/visible", False
        )

    def destroy(self):
        """Remove the camera speed menu item."""
        if self._camera_menubar_instance:
            self._camera_menubar_instance.deregister_menu_item(
                self._create_camera_speed
            )

    def _create_camera_speed(self, _vc, _r: ui.Menu):
        """Create a menu item for camera speed."""
        ui.MenuItem(
            "Speed",
            hide_on_click=False,
            delegate=SliderMenuDelegate(
                model=SettingModel(
                    "/persistent/app/viewport/camMoveVelocity", draggable=True
                ),
                min=self._settings.get_as_float(
                    "/persistent/app/viewport/camVelocityMin"
                ) or 0.01,
                max=self._settings.get_as_float(
                    "/persistent/app/viewport/camVelocityMax"
                ),
                tooltip="Set the Fly Mode navigation speed",
                width=0,
                reserve_status=True,
            ),
        )
