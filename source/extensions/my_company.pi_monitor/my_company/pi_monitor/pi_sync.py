import asyncio, datetime, os, tempfile, time, traceback
import requests, urllib3
from decimal import Decimal, ROUND_HALF_UP
from requests.auth import HTTPBasicAuth

from omni.usd import get_context
from pxr import Sdf, UsdShade, UsdGeom

# Import Pillow with auto-install fallback
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import omni.kit.pipapi as pipapi
    pipapi.install("Pillow")
    from PIL import Image, ImageDraw, ImageFont

class PIMonitor:
    """Main PI monitoring class - adapted for Omniverse Kit Extension"""
    
    def __init__(self):
        # Configuration
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self.USERNAME = r"win-lqin09i7rg4\administrator"
        self.PASSWORD = "Brungy509@"
        self.AUTH = HTTPBasicAuth(self.USERNAME, self.PASSWORD)
        
        self.BASE_URL = "https://192.168.74.128/piwebapi"
        self.ATTR_URL = f"{self.BASE_URL}/elements/F1EmQmqOHC3i_kyP3ytLaQ6cSACt0PThFj8BGgrwAMKdv39AV0lOLUxRSU4wOUk3Ukc0XERBVEFCQVNFMVxB5Y2AXOWGt-awo-apnzE/attributes"
        
        # Your existing ATTR_MAP
        self.ATTR_MAP = {
            "temperature": {"prim_path": "/World/P5D_panel/Main_NS800N_/Geometry/C063N4FM_3D_simplified_0/HANDLE_ASSY_C063N320FM_3D_23/HANDLE_ASSY_C063N320FM_24/Mesh_11", "attribute": "temp_01"},
            "TemperatureSetpoint": {"prim_path": "/World/P5D_panel/RD_district_NS800N/Geometry/C063N4FM_3D_simplified_0/COVER_ASSY_C063N320FM_3D_21/COVER_ASSY_C063N320FM_C_1_22/Mesh_10", "attribute": "temp_02"},
            "PowerUsage": {"prim_path": "/World/P5D_panel/AC5D_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_03"},
            "Current": {"prim_path": "/World/P5D_panel/E5D_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_04"},
            "internalCalculOutput": {"prim_path": "/World/P5D_panel/R5D_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_05"},
            "temp_06": {"prim_path": "/World/P5D_panel/L5D_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_06"},
            "temp_07": {"prim_path": "/World/P5D_panel/SC3_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_07"},
            "temp_08": {"prim_path": "/World/P5D_panel/SC1_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_08"},
            "temp_09": {"prim_path": "/World/P5D_panel/SC2_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_09"},
            "temp_10": {"prim_path": "/World/P5D_panel/AC1_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_10"},
            "temp_11": {"prim_path": "/World/P5D_panel/AC2_NSX_100N/Geometry/MCADPP0000044_3D_simplified_0/C25W35E250_3D_SIMPLIFIED_1/Mesh_0", "attribute": "temp_11"},
        }
        
        self.STATIC_LABELS = [
            "Temp 01 (°C):", "Temp 02 (°C):", "Temp 03 (°C):", "Temp 04 (°C):",
            "Temp 05 (°C):", "Temp 06 (°C):", "Temp 07 (°C):", "Temp 08 (°C):",
            "Temp 09 (°C):", "Temp 10 (°C):", "Temp 11 (°C):",
        ]
        
        # Config
        self.TARGET_PRIM = "/World/Monitor/shell"
        self.MAT_PATH = "/World/Monitor/PI_PanelMat"
        self.POLL_SEC = 30.0
        self.IMG_SIZE = (1024, 768)
        self.BG_RGBA = (0, 0, 0, 180)
        self.FONT_SIZE = 45
        
        # Setup directories
        self.PNG_DIR = os.path.join(tempfile.gettempdir(), "pi_panel")
        os.makedirs(self.PNG_DIR, exist_ok=True)
        
        # Initialize session
        self._session = requests.Session()
        self._session.auth = self.AUTH
        self._session.verify = False
        
        # State variables
        self._font = None
        self._mat_ready = False
        self._last_values = {}
        self._texture_path = None
        self._task = None
        self._stage_sub = None
        
        print("[PI Monitor] Initialized")
    
    def fmt2(self, v):
        return str(Decimal(str(v)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))
    
    def to_float2(self, v):
        return float(Decimal(str(v)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))
    
    def get_element_attributes(self):
        r = self._session.get(self.ATTR_URL, timeout=5)
        r.raise_for_status()
        return r.json()["Items"]
    
    def get_attribute_value(self, webid):
        r = self._session.get(f"{self.BASE_URL}/streams/{webid}/value", timeout=5)
        r.raise_for_status()
        return r.json()["Value"]
    
    def update_usd_prim(self, prim_path, attr_name, value):
        stage = get_context().get_stage()
        if not stage:
            return False, "No stage available"
        
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            return False, f"Prim not found: {prim_path}"
        
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid():
            attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Float)
        
        attr.Set(self.to_float2(value))
        return True, f"{attr_name}:{self.fmt2(value)}"
    
    def ensure_uv(self):
        stage = get_context().get_stage()
        if not stage:
            return False
        
        prim = stage.GetPrimAtPath(self.TARGET_PRIM)
        mesh = UsdGeom.Mesh(prim)
        if not mesh:
            print("[PI Monitor] Mesh not found:", self.TARGET_PRIM)
            return False

        pv_api = UsdGeom.PrimvarsAPI(prim)
        st = pv_api.GetPrimvar("st")
        if st and st.IsDefined():
            return True

        pts = mesh.GetPointsAttr().Get()
        if not pts:
            return False
        
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        spanx = maxx-minx or 1.0
        spany = maxy-miny or 1.0
        uvs = [((p[0]-minx)/spanx, (p[1]-miny)/spany) for p in pts]

        st = pv_api.CreatePrimvar("st",
                                  Sdf.ValueTypeNames.TexCoord2fArray,
                                  UsdGeom.Tokens.vertex)
        st.Set(uvs)
        print("[PI Monitor] UV created (planar).")
        return True
    
    def _ensure_font(self):
        if self._font:
            return self._font
        try:
            self._font = ImageFont.truetype("arial.ttf", self.FONT_SIZE)
        except Exception:
            self._font = ImageFont.load_default()
        return self._font
    
    def _draw_png(self, values_dict, timestamp, path):
        """Draw PNG with static labels and dynamic values"""
        img = Image.new("RGBA", self.IMG_SIZE, (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        font = self._ensure_font()
        
        # Simple design
        corner_radius = 15
        bg_color = (35, 35, 35, 200)
        text_color = (255, 255, 255, 255)
        
        margin = 8
        x1, y1 = margin, margin
        x2, y2 = self.IMG_SIZE[0] - margin, self.IMG_SIZE[1] - margin
        
        temp_img = Image.new("RGBA", self.IMG_SIZE, (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.rounded_rectangle([x1, y1, x2, y2], radius=corner_radius, fill=bg_color)
        
        img = Image.alpha_composite(img, temp_img)
        d = ImageDraw.Draw(img)
        
        # Header
        header = f"PI Sync {timestamp}"
        d.text((40, 30), header, fill=text_color, font=font)
        
        # Temperature readings
        y = 92
        line_spacing = 62
        
        ordered_attrs = ["temperature", "TemperatureSetpoint", "PowerUsage", "Current", 
                        "internalCalculOutput", "temp_06", "temp_07", "temp_08", 
                        "temp_09", "temp_10", "temp_11"]
        
        for i, attr_name in enumerate(ordered_attrs):
            if i < len(self.STATIC_LABELS):
                label = self.STATIC_LABELS[i]
                value = values_dict.get(attr_name, "N/A")
                if value != "N/A":
                    value = self.fmt2(value)
                line = f"{label} {value}"
                d.text((40, y), line, fill=text_color, font=font)
                y += line_spacing
        
        img.save(path, "PNG")
        print(f"[PI Monitor] PNG created: {path}")
    
    def rebuild_material(self, force=False):
        """Create material with single stable texture file"""
        if self._mat_ready and not force:
            return

        # Set up the texture path
        self._texture_path = os.path.join(self.PNG_DIR, "panel_display.png")

        stage = get_context().get_stage()
        if not stage:
            print("[PI Monitor] No stage available")
            return
            
        if force and stage.GetPrimAtPath(self.MAT_PATH):
            stage.RemovePrim(self.MAT_PATH)

        mat_prim = stage.DefinePrim(self.MAT_PATH, "Material")
        mat = UsdShade.Material(mat_prim)

        # primvar reader
        uv_reader = UsdShade.Shader.Define(stage, f"{self.MAT_PATH}/UVReader")
        uv_reader.CreateIdAttr("UsdPrimvarReader_float2")
        uv_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        uv_out = uv_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

        # texture
        tex = UsdShade.Shader.Define(stage, f"{self.MAT_PATH}/Tex")
        tex.CreateIdAttr("UsdUVTexture")
        tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(self._texture_path)
        tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(uv_out)
        tex_rgb = tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

        # preview surface
        prev = UsdShade.Shader.Define(stage, f"{self.MAT_PATH}/Preview")
        prev.CreateIdAttr("UsdPreviewSurface")
        prev.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.3)
        prev.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        prev.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex_rgb)
        prev.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex_rgb)
        surf_out = prev.CreateOutput("surface", Sdf.ValueTypeNames.Token)

        mat.CreateSurfaceOutput().ConnectToSource(surf_out)

        UsdShade.MaterialBindingAPI.Apply(stage.GetPrimAtPath(self.TARGET_PRIM)).Bind(mat)

        self._mat_ready = True
        print("[PI Monitor] Material created (stable PNG method).")
    
    def refresh_texture(self, values_dict, force_update=False):
        """Update texture - ONLY when values actually change"""
        # Compare only the numeric values
        values_only = {k: self.fmt2(v) for k, v in values_dict.items()}
        last_values_only = {k: self.fmt2(v) for k, v in self._last_values.items()}
        
        if values_only == last_values_only and not force_update:
            print("[PI Monitor] Sensor values unchanged, keeping current display")
            return
        
        print("[PI Monitor] Sensor values changed, updating display...")
        
        # Create the new texture
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._draw_png(values_dict, timestamp, self._texture_path)
        
        # Store current values
        self._last_values = values_dict.copy()
        
        print(f"[PI Monitor] Display updated with new sensor data at {timestamp}")
    
    async def _one_cycle(self):
        """Process one update cycle"""
        updated = 0
        values_dict = {}
        
        ordered_attrs = ["temperature", "TemperatureSetpoint", "PowerUsage", "Current", 
                        "internalCalculOutput", "temp_06", "temp_07", "temp_08", 
                        "temp_09", "temp_10", "temp_11"]
        
        try:
            all_attrs = {item["Name"]: item["WebId"] for item in self.get_element_attributes()}
            
            for name in ordered_attrs:
                if name in all_attrs and name in self.ATTR_MAP:
                    webid = all_attrs[name]
                    val = self.get_attribute_value(webid)
                    cfg = self.ATTR_MAP[name]
                    ok, _ = self.update_usd_prim(cfg["prim_path"], cfg["attribute"], val)
                    if ok:
                        updated += 1
                        values_dict[name] = val
        except Exception:
            print("[PI Monitor] >>> _one_cycle error:\n", traceback.format_exc())

        if values_dict:
            try:
                self.refresh_texture(values_dict)
            except Exception:
                print("[PI Monitor] >>> refresh_texture error:\n", traceback.format_exc())

        print(f"[PI Monitor] [{datetime.datetime.now().strftime('%H:%M:%S')}] processed {updated} sensors")
        return updated
    
    async def _polling_loop(self, period=30.0):
        print("[PI Monitor] Starting PI monitoring with stable PNG display")
        try:
            self.ensure_uv()
            self.rebuild_material(force=True)
            # Initial display
            test_values = {}
            ordered_attrs = ["temperature", "TemperatureSetpoint", "PowerUsage", "Current", 
                            "internalCalculOutput", "temp_06", "temp_07", "temp_08", 
                            "temp_09", "temp_10", "temp_11"]
            for attr in ordered_attrs:
                test_values[attr] = 0.0
            self.refresh_texture(test_values, force_update=True)
        except Exception:
            print("[PI Monitor] >>> init error:\n", traceback.format_exc())

        while True:
            try:
                await self._one_cycle()
            except Exception:
                print("[PI Monitor] >>> polling_loop error:\n", traceback.format_exc())
            await asyncio.sleep(period)
    
    def start(self):
        """Start automatic updates"""
        if self._task and not self._task.done():
            print("[PI Monitor] Already running.")
            return
        
        print(f"[PI Monitor] Starting PI monitoring ({self.POLL_SEC}s intervals)")
        self._task = asyncio.ensure_future(self._polling_loop(self.POLL_SEC))
        
    def stop(self):
        """Stop automatic updates"""
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        print("[PI Monitor] Stopped.")
    
    def force_refresh(self):
        """Run one update cycle immediately"""
        asyncio.ensure_future(self._one_cycle())
    
    def test_png(self):
        """Generate test texture"""
        self.ensure_uv()
        self.rebuild_material(force=True)
        test_values = {}
        ordered_attrs = ["temperature", "TemperatureSetpoint", "PowerUsage", "Current", 
                        "internalCalculOutput", "temp_06", "temp_07", "temp_08", 
                        "temp_09", "temp_10", "temp_11"]
        for i, attr in enumerate(ordered_attrs):
            test_values[attr] = 25.0 + i * 2.5
        
        self.refresh_texture(test_values, force_update=True)
        print("[PI Monitor] Test display created successfully")
    
    def diag(self):
        """Diagnostic function"""
        stage = get_context().get_stage()
        if not stage:
            print("[PI Monitor] No stage available")
            return
            
        tex = UsdShade.Shader.Get(stage, f"{self.MAT_PATH}/Tex")
        print("[PI Monitor] == Diagnostics ==")
        print("Texture path:", self._texture_path)
        if self._texture_path and os.path.exists(self._texture_path):
            print(f"Texture file exists, size: {os.path.getsize(self._texture_path)} bytes")
        else:
            print("Texture file missing")
        print("Material exists:", stage.GetPrimAtPath(self.MAT_PATH).IsValid())
        print("Task running:", self._task and not self._task.done())
        print("Last sensor values:", {k: self.fmt2(v) for k, v in self._last_values.items()})