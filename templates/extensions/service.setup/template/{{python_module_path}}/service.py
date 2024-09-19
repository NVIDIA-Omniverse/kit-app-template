# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from pathlib import Path
from pydantic import BaseModel, Field

import omni.kit.commands
import omni.usd
from omni.services.core.routers import ServiceAPIRouter

router = ServiceAPIRouter(tags=["{{ extension_display_name }}"])


class CubeDataModel(BaseModel):
    """Model of a request for generating a cube."""

    asset_write_location: str = Field(
        default="/asset_write_path",
        title="Asset Path",
        description="Location on device to write generated asset",
    )

    asset_name: str = Field(
        default="cube",
        title="Asset Name",
        description="Name of the asset to be generated, .usda will be appended to the name",
    )

    cube_scale: float = Field(
        default=100,
        title="Cube Scale",
        description="Scale of the cube",
    )


@router.post(
    "/generate_cube",
    summary="Generate a cube",
    description="An endpoint to generate a usda file containing a cube of given scale",
)
async def generate_cube(cube_data: CubeDataModel):
    print("[{{ extension_name }}] generate_cube was called")

    # Create a new stage
    usd_context = omni.usd.get_context()
    usd_context.new_stage()
    stage = omni.usd.get_context().get_stage()

    # Set the default prim
    default_prim_path = "/World"
    stage.DefinePrim(default_prim_path, "Xform")
    prim = stage.GetPrimAtPath(default_prim_path)
    stage.SetDefaultPrim(prim)

    # Create cube
    prim_type = "Cube"
    prim_path = f"/World/{prim_type}"

    omni.kit.commands.execute(
        "CreatePrim",
        prim_path=prim_path,
        prim_type=prim_type,
        attributes={"size": cube_data.cube_scale},
        select_new_prim=False,
    )

    # save stage
    asset_file_path = str(Path(
        cube_data.asset_write_location).joinpath(f"{cube_data.asset_name}.usda")
    )
    stage.GetRootLayer().Export(asset_file_path)
    msg = f"[{{ extension_name }}] Wrote a cube to this path: {asset_file_path}"
    print(msg)
    return msg
