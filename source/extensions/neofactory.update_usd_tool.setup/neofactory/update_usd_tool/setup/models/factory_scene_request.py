from pydantic import BaseModel, Field

class FactorySceneRequest(BaseModel):
    """
    Model describing the request payload for generating a neofactory scene.
    """

    scene_asset_name: str = Field(
        default="scene",
        title="Scene Asset Name",
        description="Name of the USD asset to be generated ('.usda' will be appended)."
    )

    cnc_machine_count: int = Field(
        default=5,
        ge=0,
        le=7,
        title="CNC Machine Count",
        description="Number of CNC machines to include in the scene."
    )

    include_cmm: bool = Field(
        default=False,
        title="Include CMM",
        description="If True, a Coordinate Measuring Machine (CMM) will be included."
    )

    include_tool_station: bool = Field(
        default=False,
        title="Include Tool Station",
        description="If True, a tool station will be included in the factory layout."
    )
