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
from math import floor

import omni.kit.commands
import omni.usd
from omni.services.core.routers import ServiceAPIRouter
from pxr import Gf, Sdf, UsdGeom, UsdShade
from .models.factory_scene_request import FactorySceneRequest
from .helpers.create_optimus import create_optimus
from .helpers.compute_bbox import compute_bbox


router = ServiceAPIRouter(tags=["Neofactory Update USD Tool Setup"])
asset_library_path = "omniverse://sim01/Library/"
scene_write_path = "omniverse://sim01/Users/schumacher/"

@router.post(
    "/generate_scene",
    summary="Generate a scene of neofactory primitives",
    description="An endpoint to generate a usda file containing Optimuses, Cells, Setup Tables, Kukas, and CNC Machines",
)
async def generate_scene(scene_data: FactorySceneRequest):
    print("[neofactory.update_usd_tool.setup] generate_scene was called")

    # Create a new stage
    usd_context = omni.usd.get_context()
    usd_context.new_stage()
    stage = omni.usd.get_context().get_stage()

    # Set the default prim
    default_prim_path = "/World"
    stage.DefinePrim(default_prim_path, "Xform")
    prim = stage.GetPrimAtPath(default_prim_path)
    stage.SetDefaultPrim(prim)

    # Load Environment
    asset_stage_path = "/World"
    asset_path = f"{asset_library_path}environments/Environment.usd"
    asset_prim = stage.DefinePrim(asset_stage_path, "Xform")
    asset_prim.GetReferences().AddReference(asset_path)

    # Load Building
    building_asset_name = "building"
    building_asset_path = f"{asset_library_path}FactoryBuilding/building.usd"
    building_prim = UsdGeom.Xform.Define(stage, f"{default_prim_path}")#/{building_asset_name}")
    building_prim.GetPrim().GetReferences().AddReference(building_asset_path)
    building_translate = building_prim.AddTranslateOp()
    building_translate.Set(Gf.Vec3d(0, 0, -411.3204593132448))

    # Add Optimuses
    create_optimus(stage, "Optimus", 1, 1, 1, asset_library_path)

    # Add Cell
    starting_coordinate_x = 431.0
    cell_asset_name = "cellA"
    cell_asset_path = f"{default_prim_path}/{cell_asset_name}"
    cell_prim = UsdGeom.Xform.Define(stage, cell_asset_path)
    cell_translate = cell_prim.AddTranslateOp()
    cell_translate.Set(Gf.Vec3d(0, 0, -252.78161174741186))
    cell_rotate = cell_prim.AddRotateXYZOp()
    cell_rotate.Set((0, -90, -90))

    # Add CNCs
    cnc_asset_name = "UMA"
    cnc_asset_path = f"{asset_library_path}cell/UMC500/UMC500.usd"
    start_location = Gf.Vec3d(starting_coordinate_x, 202.92, 0.00)
    cmc_spacing = 50
    cmc_x_extent = 340
    for i in range(scene_data.cnc_machine_count):
        prim_path = omni.usd.get_stage_next_free_path(
            stage,
            f"/{cell_asset_name}/{cnc_asset_name}",
            True
        )
        cnc_prim = UsdGeom.Xform.Define(stage, prim_path)
        cnc_prim.GetPrim().GetReferences().AddReference(cnc_asset_path)
        cnc_translate = cnc_prim.AddTranslateOp()
        cnc_translate.Set(start_location -  Gf.Vec3d((cmc_spacing + cmc_x_extent) * i, 0, 0))
        cnc_rotate = cnc_prim.AddRotateXYZOp()
        cnc_rotate.Set((0, 0, 90))

    # Calculate Cell Width
    cell_range = compute_bbox(cell_prim)
    cell_width = cell_range.GetSize()[2]

    # Add Setup Tables
    setup_table_asset_name = "setupTable"
    setup_table_asset_path = f"{cell_asset_path}/{setup_table_asset_name}"
    setup_table_prim = UsdGeom.Xform.Define(stage, setup_table_asset_path)
    # setup_table_translate = setup_table_prim.AddTranslateOp()
    # setup_table_translate.Set(Gf.Vec3d(0, 0, -252.78161174741186))
    # setup_table_rotate = setup_table_prim.AddRotateXYZOp()
    # setup_table_rotate.Set((0, -90, -90))

    # Add Middle Table
    if scene_data.cnc_machine_count > 0:
        starting_x_buffer = 150
        middle_table_asset_name = "table"
        middle_table_library_path = f"{asset_library_path}cell/setupTable/setupTableGeo/New_Tables/setupTables/st_Midle.usd"
        middle_table_asset_path = f"{setup_table_asset_path}/{middle_table_asset_name}"
        middle_table_prim = UsdGeom.Xform.Define(stage, middle_table_asset_path)
        middle_table_prim.GetPrim().GetReferences().AddReference(middle_table_library_path)
        # Calculate table extent
        table_range = compute_bbox(middle_table_prim)
        table_width = table_range.GetSize()[2]
        # Transate first table
        middle_table_translate = middle_table_prim.AddTranslateOp()
        middle_table_translate.Set(Gf.Vec3d(starting_coordinate_x + starting_x_buffer, -100, 0))
        middle_table_rotate = middle_table_prim.AddRotateXYZOp()
        middle_table_rotate.Set((0, 0, 180))
        # Add additional tables
        for i in range(1, floor(cell_width / table_width)):
            prim_path = omni.usd.get_stage_next_free_path(
                stage,
                middle_table_asset_path,
                False
            )
            table_prim = UsdGeom.Xform.Define(stage, prim_path)
            table_prim.GetPrim().GetReferences().AddReference(middle_table_library_path)
            table_translate = table_prim.AddTranslateOp()
            table_translate.Set(
                Gf.Vec3d(
                    starting_coordinate_x + starting_x_buffer - (table_width * i),
                    -100,
                    0
                    )
                )
            table_rotate = table_prim.AddRotateXYZOp()
            table_rotate.Set((0, 0, 180))


        # Add CMM
        if scene_data.include_cmm:
            cmm_asset_name = "HexagonGlobalS"
            cmm_asset_path = f"{asset_library_path}cell/Hexagon Global/HexagonGlobalS_USD/HexagonGlobalS.usd"
            cmm_prim_path = f"/{cell_asset_name}/{cmm_asset_name}"
            cmm_prim = UsdGeom.Xform.Define(stage, cmm_prim_path)
            cmm_prim.GetPrim().GetReferences().AddReference(cmm_asset_path)
            cmm_translate = cmm_prim.AddTranslateOp()
            cmm_translate.Set(Gf.Vec3d(-100, 0, 0))
            cmm_rotate = cmm_prim.AddRotateXYZOp()
            cmm_rotate.Set((-90, 0, 0))








    # save stage
    # asset_file_path = str(Path(scene_data.asset_write_location).joinpath(f"{scene_data.asset_name}.usda"))
    asset_file_path = f"{scene_write_path}{scene_data.scene_asset_name}.usda"

    stage.GetRootLayer().Export(asset_file_path)
    msg = f"tutorial.service.setup Wrote a scene to this path: {asset_file_path}"
    print(msg)
    return msg
