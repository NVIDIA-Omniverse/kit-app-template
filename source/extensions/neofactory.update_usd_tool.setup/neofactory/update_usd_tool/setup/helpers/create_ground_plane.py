import omni.kit.commands
import omni.usd
from pxr import Gf, Sdf, UsdGeom, UsdShade


def create_ground_plane(stage, plane_scale: float):
    prim_type = "Plane"
    prim_path = f"/World/{prim_type}"

    omni.kit.commands.execute(
        "CreateMeshPrim",
        prim_path=prim_path,
        prim_type=prim_type,
        select_new_prim=False,
    )

    prim = stage.GetPrimAtPath(prim_path)
    xform = UsdGeom.Xformable(prim)
    xform_ops = {op.GetBaseName(): op for op in xform.GetOrderedXformOps()}
    scale = xform_ops["scale"]
    scale.Set(Gf.Vec3d(plane_scale, 1, plane_scale))