import omni.kit.commands
import omni.usd


def create_optimus(stage, prim_type: str, quantity: int, spacing: float, prim_scale: float, asset_library_path: str):

    # Offset Cubes and Spheres
    if prim_type == "Optimus":
        start = (prim_scale * 2, prim_scale, 0)
        asset_path = f"{asset_library_path}Optimus_Rig_Demo/Demo4_Pick_and_Place/Optimus_Demo4.usd"
    else:  # if prim_type == "Sphere":
        start = (-prim_scale * 2, prim_scale, 0)

    for i in range(quantity):
        prim_path = omni.usd.get_stage_next_free_path(
            stage,
            f"/World/{prim_type}",
            False
        )

        # Load Optimus
        asset_prim = stage.DefinePrim(prim_path, "Xform")
        asset_prim.GetReferences().AddReference(asset_path)

        translation = (start[0], start[1], start[2] + (i * spacing))
        scale = (prim_scale, prim_scale, prim_scale)
        omni.kit.commands.execute(
            "TransformPrimSRT",
            path=prim_path,
            new_translation=translation,
            new_scale=scale,
        )