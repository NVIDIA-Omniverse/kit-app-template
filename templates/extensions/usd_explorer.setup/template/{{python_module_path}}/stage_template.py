# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import carb
import omni.ext
import omni.kit.commands
from omni.kit.stage_templates import register_template, unregister_template
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux


class SunnySkyStage:
    """Stage template for a sunny sky."""
    def __init__(self):
        register_template("SunnySky", self.new_stage)

    def __del__(self):
        """Unregister the template when the object is deleted."""
        unregister_template("SunnySky")

    def new_stage(self, _rootname, usd_context_name):
        """Create a new stage with a sunny sky."""
        # Create basic DistantLight
        usd_context = omni.usd.get_context(usd_context_name)
        stage = usd_context.get_stage()
        # get up axis
        up_axis = UsdGeom.GetStageUpAxis(stage)
        with Usd.EditContext(stage, stage.GetRootLayer()):
            # create Environment
            omni.kit.commands.execute(
                "CreatePrim",
                prim_path="/Environment",
                prim_type="Xform",
                select_new_prim=False,
                create_default_xform=True,
                context_name=usd_context_name
            )

            texture_path = carb.tokens.get_tokens_interface().resolve("${omni.light_rigs}/light_rig_data/light_rigs/HDR/partly_cloudy.hdr")

            # create Sky
            omni.kit.commands.execute(
                "CreatePrim",
                prim_path="/Environment/Sky",
                prim_type="DomeLight",
                select_new_prim=False,
                attributes={
                            UsdLux.Tokens.inputsIntensity: 1000,
                            UsdLux.Tokens.inputsTextureFile: texture_path,
                            UsdLux.Tokens.inputsTextureFormat: UsdLux.Tokens.latlong,
                            UsdLux.Tokens.inputsSpecular: 1,
                            UsdGeom.Tokens.visibility: "inherited",
                            } if hasattr(UsdLux.Tokens, 'inputsIntensity') else \
                            {
                            UsdLux.Tokens.intensity: 1000,
                            UsdLux.Tokens.textureFile: texture_path,
                            UsdLux.Tokens.textureFormat: UsdLux.Tokens.latlong,
                            UsdGeom.Tokens.visibility: "inherited",
                            },
                create_default_xform=True,
                context_name=usd_context_name
            )
            prim = stage.GetPrimAtPath("/Environment/Sky")
            prim.CreateAttribute(
                "xformOp:scale", Sdf.ValueTypeNames.Double3, False
            ).Set(Gf.Vec3d(1, 1, 1))
            prim.CreateAttribute(
                "xformOp:translate", Sdf.ValueTypeNames.Double3, False
            ).Set(Gf.Vec3d(0, 0, 0))
            if up_axis == "Y":
                prim.CreateAttribute(
                    "xformOp:rotateXYZ", Sdf.ValueTypeNames.Double3, False
                ).Set(Gf.Vec3d(270, 0, 0))
            else:
                prim.CreateAttribute(
                    "xformOp:rotateXYZ", Sdf.ValueTypeNames.Double3, False
                ).Set(Gf.Vec3d(0, 0, 90))
            prim.CreateAttribute(
                "xformOpOrder", Sdf.ValueTypeNames.String, False
            ).Set(["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"])

            # create DistantLight
            omni.kit.commands.execute(
                "CreatePrim",
                prim_path="/Environment/DistantLight",
                prim_type="DistantLight",
                select_new_prim=False,
                attributes={
                    UsdLux.Tokens.inputsAngle: 4.3,
                    UsdLux.Tokens.inputsIntensity: 3000,
                    UsdGeom.Tokens.visibility: "inherited",
                    } if hasattr(UsdLux.Tokens, 'inputsIntensity') else
                    {
                    UsdLux.Tokens.angle: 4.3,
                    UsdLux.Tokens.intensity: 3000,
                    UsdGeom.Tokens.visibility: "inherited",
                    },
                create_default_xform=True,
                context_name=usd_context_name
            )
            prim = stage.GetPrimAtPath("/Environment/DistantLight")
            prim.CreateAttribute(
                "xformOp:scale", Sdf.ValueTypeNames.Double3, False
            ).Set(Gf.Vec3d(1, 1, 1))
            prim.CreateAttribute(
                "xformOp:translate", Sdf.ValueTypeNames.Double3, False
            ).Set(Gf.Vec3d(0, 0, 0))
            if up_axis == "Y":
                prim.CreateAttribute(
                    "xformOp:rotateXYZ", Sdf.ValueTypeNames.Double3, False
                    ).Set(
                        Gf.Vec3d(
                            310.6366313590111,
                            -125.93251524567805,
                            0.8821359067542289
                            )
                        )
            else:
                prim.CreateAttribute(
                    "xformOp:rotateXYZ", Sdf.ValueTypeNames.Double3, False
                ).Set(
                    Gf.Vec3d(
                        41.35092544555664,
                        0.517652153968811,
                        -35.92928695678711
                        )
                    )
            prim.CreateAttribute(
                "xformOpOrder", Sdf.ValueTypeNames.String, False).Set(
                    ["xformOp:translate", "xformOp:rotateXYZ", "xformOp:scale"]
                )
