"""
Lipton rotation debug script — paste into Kit Script Editor.

Kit: Window → Script Editor → paste this → Run

This script finds all /World/lipton_milktea* prims and applies a test
Y-rotation on top of the existing orient so you can find the correct
facing angle without restarting Kit.

CHANGE THIS VALUE and re-run until the box faces the shelf aisle:
"""
TEST_Y_ANGLE = 90   # try: 0, 90, -90, 180

# ── nothing to change below this line ─────────────────────────────────────
import omni.usd
from pxr import Gf, Usd, UsdGeom

stage = omni.usd.get_context().get_stage()
world = stage.GetPrimAtPath("/World")
if not world:
    print("ERROR: /World prim not found")
else:
    targets = [
        c for c in world.GetChildren()
        if c.GetName().startswith("lipton_milktea")
    ]
    if not targets:
        print("No lipton_milktea prims found on stage. Run a replace first.")
    else:
        y_rot = Gf.Rotation(Gf.Vec3d(0, 1, 0), TEST_Y_ANGLE)
        qy = y_rot.GetQuaternion()
        q_new = Gf.Quatd(qy.GetReal(), Gf.Vec3d(qy.GetImaginary()))

        for prim in targets:
            xform = UsdGeom.Xform(prim)
            ops = xform.GetOrderedXformOps()

            # Find existing orient op
            orient_op = next(
                (op for op in ops if op.GetOpType() == UsdGeom.XformOp.TypeOrient),
                None
            )
            if orient_op is not None:
                existing_q = orient_op.Get(Usd.TimeCode.Default())
                # Compose: existing_q * y_correction
                existing_rot = Gf.Rotation(existing_q)
                composed = existing_rot * y_rot
                cq = composed.GetQuaternion()
                new_q = Gf.Quatd(cq.GetReal(), Gf.Vec3d(cq.GetImaginary()))
                orient_op.Set(new_q)
                print(f"  {prim.GetPath()}  orient updated  (Y={TEST_Y_ANGLE}°)  q={new_q}")
            else:
                # No orient op yet — add one
                orient_op = xform.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
                orient_op.Set(q_new)
                print(f"  {prim.GetPath()}  orient added  (Y={TEST_Y_ANGLE}°)  q={q_new}")

        print(f"\nDone. Change TEST_Y_ANGLE and re-run to try a different angle.")
        print("Once correct, update ASSET_SPAWN_ROTATION_CORRECTION in usd_spawner.py:")
        print(f'    "lipton_milktea": [')
        print(f'        ((0, 0, 1), -90),')
        print(f'        ((0, 1, 0), <correct_angle>),')
        print(f'    ],')
