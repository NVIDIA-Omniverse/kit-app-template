import omni.kit.commands
import omni.usd


def apply_material(stage):
    prim = stage.GetPrimAtPath('/World/Sphere')
    materials_path = "/World/Looks"
    material_path = f"{materials_path}/OmniPBR"

    omni.kit.commands.execute('CreatePrim',
        prim_path=materials_path,
        prim_type="Scope",
        select_new_prim=False,
    )

    omni.kit.commands.execute('CreateMdlMaterialPrim',
        mtl_url="OmniPBR.mdl",
        mtl_name="OmniPBR",
        mtl_path=material_path,
        select_new_prim=True,
    )


    custom_shader = UsdShade.Shader(stage.GetPrimAtPath(f"{material_path}/Shader"))
    custom_shader.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.46, .73, 0))
    custom_shader.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(.25)

    omni.kit.commands.execute(
        "BindMaterial",
        prim_path=prim.GetPrimPath(),
        material_path=material_path
    )