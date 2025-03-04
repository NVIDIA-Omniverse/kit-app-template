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
from math import floor, ceil

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
    cnc_prim = False
    cnc_asset_name = "UMA"
    cnc_asset_path = f"{asset_library_path}cell/UMC500/UMC500.usd"
    start_location = Gf.Vec3d(starting_coordinate_x, 202.92, 0.00)
    cnc_spacing = 50
    cnc_x_extent = 340
    for i in range(scene_data.cnc_machine_count):
        prim_path = omni.usd.get_stage_next_free_path(
            stage,
            f"/{cell_asset_name}/{cnc_asset_name}",
            True
        )
        cnc_prim = UsdGeom.Xform.Define(stage, prim_path)
        cnc_prim.GetPrim().GetReferences().AddReference(cnc_asset_path)
        cnc_translate = cnc_prim.AddTranslateOp()
        cnc_translate.Set(start_location -  Gf.Vec3d((cnc_spacing + cnc_x_extent) * i, 0, 0))
        cnc_rotate = cnc_prim.AddRotateXYZOp()
        cnc_rotate.Set((0, 0, 90))

    # Add CMM next to last CNC
    if scene_data.include_cmm:
        cmm_asset_name = "HexagonGlobalS"
        cmm_asset_path = f"{asset_library_path}cell/Hexagon Global/HexagonGlobalS_USD/HexagonGlobalS.usd"
        cmm_prim_path = f"{cell_asset_path}/{cmm_asset_name}"
        cmm_prim = UsdGeom.Xform.Define(stage, cmm_prim_path)
        cmm_prim.GetPrim().GetReferences().AddReference(cmm_asset_path)
        if cnc_prim:
            last_cnc_location = cnc_prim.GetPrim().GetProperty("xformOp:translate").Get()
            cmm_translation = Gf.Vec3d(cnc_spacing + (cnc_x_extent / 2), -125, 0)
        else:
            last_cnc_location = start_location
            cmm_translation = Gf.Vec3d(-100, 0, 0)
        cmm_translate = cmm_prim.AddTranslateOp()
        cmm_translate.Set(last_cnc_location - cmm_translation)
        cmm_rotate = cmm_prim.AddRotateXYZOp()
        cmm_rotate.Set((0, 0, -90))
        cmm_scale = cmm_prim.AddScaleOp()
        cmm_scale.Set((1.4, 1.4, 1.4))

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

    # Add Tables and Tools
    if scene_data.cnc_machine_count > 0 or scene_data.include_cmm:
        starting_x_buffer = 150
        additional_tables = 0
        # first add tool station
        if scene_data.include_tool_station:
            additional_tables = 2
            # tool_cell_asset_name = "toolCell"
            # tool_cell_asset_path = f"{cell_asset_path}/{tool_cell_asset_name}"
            # tool_cell_prim = UsdGeom.Xform.Define(stage, tool_cell_asset_path)
            tool_table_asset_name = "toolTable"
            tool_table_library_path = f"{asset_library_path}cell/tools/toolCell.usd"
            tool_table_asset_path = f"{cell_asset_path}/{tool_table_asset_name}"
            tool_table_prim = UsdGeom.Xform.Define(stage, tool_table_asset_path)
            tool_table_prim.GetPrim().GetReferences().AddReference(tool_table_library_path)
            # Calculate tool extent
            tool_range = compute_bbox(tool_table_prim)
            tool_width = tool_range.GetSize()[2]
            # Transate tools
            tool_table_translate = tool_table_prim.AddTranslateOp()
            tool_table_translate.Set(Gf.Vec3d(starting_coordinate_x + starting_x_buffer, -100, 0))
            tool_table_rotate = tool_table_prim.AddRotateXYZOp()
            tool_table_rotate.Set((0, 0, 180))
            starting_x_buffer = -18.3
        # Add first table
        middle_table_asset_name = "table"
        middle_table_library_path = f"{asset_library_path}cell/setupTable/setupTableGeo/New_Tables/setupTables/setupStationMiddle.usd"
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
        for i in range(1, floor(cell_width / table_width) - additional_tables):
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
        # Add kuka
        kuka_asset_name = "linear6AxisKuka"
        kuka_library_path = f"{asset_library_path}cell/kuka/linear6AxisKuka.usd"
        kuka_asset_path = f"{cell_asset_path}/{kuka_asset_name}"
        kuka_prim = UsdGeom.Xform.Define(stage, kuka_asset_path)
        # Add Track
        track_asset_name = "track"
        track_asset_path = f"{kuka_asset_path}/{track_asset_name}"
        track_prim = UsdGeom.Xform.Define(stage, track_asset_path)
        track_translate = track_prim.AddTranslateOp()
        track_translate.Set((0, 65, 9.3))
        track_rotate = track_prim.AddRotateXYZOp()
        track_rotate.Set((90, 0, 90))
        # Add single tracks
        single_track_asset_name = "singleTrack"
        single_track_library_path = f"{asset_library_path}cell/kuka/trackSingle/trackSingle.usd"
        single_track_asset_path = f"{track_asset_path}/{single_track_asset_name}"
        single_track_prim = UsdGeom.Xform.Define(stage, single_track_asset_path)
        single_track_prim.GetPrim().GetReferences().AddReference(single_track_library_path)
        # Transate first table
        single_track_translate = single_track_prim.AddTranslateOp()
        single_track_translate.Set(Gf.Vec3d(0, 0, starting_coordinate_x + 110))
        # Calculate track extent
        single_track_range = compute_bbox(single_track_prim)
        print(single_track_range.GetSize())
        single_track_width = table_range.GetSize()[2]
        # Add single tracks
        single_track_buffer = 87
        for i in range(1, floor(cell_width / (single_track_width + single_track_buffer))):
            prim_path = omni.usd.get_stage_next_free_path(
                stage,
                single_track_asset_path,
                False
            )
            single_track_prim = UsdGeom.Xform.Define(stage, prim_path)
            single_track_prim.GetPrim().GetReferences().AddReference(single_track_library_path)
            single_track_translate = single_track_prim.AddTranslateOp()
            single_track_translate.Set(
                Gf.Vec3d(
                    0,
                    0,
                    starting_coordinate_x + 120 - ((single_track_width + single_track_buffer)* i),
                    )
                )
        # Add kuka
        kuka_demo_asset_name = "kuka_demo"
        kuka_demo_path = f"{kuka_asset_path}/{kuka_demo_asset_name}"
        kuka_demo_prim = UsdGeom.Xform.Define(stage, kuka_demo_path)
        kuka_demo_library_path = f"{asset_library_path}KUKA_demo/kuka_demo.usd"
        kuka_demo_prim.GetPrim().GetReferences().AddReference(kuka_demo_library_path)
        kuka_demo_translate = kuka_demo_prim.AddTranslateOp()
        kuka_demo_translate.Set((527, 70, 30))
        kuka_demo_rotate = kuka_demo_prim.AddRotateXYZOp()
        kuka_demo_rotate.Set((90, 0, -90))
        # xformable_kuka = UsdGeom.Xformable(kuka_prim)
        # Transate kuka
        # kuka_xform_ops = kuka_prim.GetOrderedXformOps()
        # for xform_op in kuka_xform_ops:
        #     if xform_op.GetOpName() == "xformOp:translate":
        #         xform_op.Set((940.95, 112.719, 36.96))
        #     if xform_op.GetOpName() == "xformOp:rotateXYZ":
        #         xform_op.Set((90, 0, -90))
        # track_prim = kuka_prim.GetPrim().GetChild("track")
        # for track_single in track_prim.GetPrim().GetAllChildren():
        #     print(track_single)

        # kuka_translate = kuka_prim.AddTranslateOp()
        # kuka_translate.Set(Gf.Vec3d(starting_coordinate_x + starting_x_buffer, -100, 0))
        # kuka_rotate = xformable_kuka.AddRotateXYZOp()
        # print('*'*79)
        # print(dir(kuka_prim))
        # print(kuka_prim.GetXformOpOrderAttr())
        # print('*'*79)
        # print(kuka_xform_ops)
        # print(kuka_xform_ops[1].GetOpName())
        # print(dir(kuka_xform_ops[0]))
        # kuka_rotate = xformable_kuka.GetRotateXYZOp()
        # kuka_rotate = kuka_prim.GetProperty("xformOp:rotateXYZ")







    # save stage
    # asset_file_path = str(Path(scene_data.asset_write_location).joinpath(f"{scene_data.asset_name}.usda"))
    asset_file_path = f"{scene_write_path}{scene_data.scene_asset_name}.usda"

    stage.GetRootLayer().Export(asset_file_path)
    msg = f"tutorial.service.setup Wrote a scene to this path: {asset_file_path}"
    print(msg)
    return msg
