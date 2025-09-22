# simple_pi_updater.py
# Updates texture files that can be referenced by USD materials
# No USD Python API required

import json
import datetime
import os
import tempfile
import time
import traceback
import requests
import urllib3
from decimal import Decimal, ROUND_HALF_UP
from requests.auth import HTTPBasicAuth
from pathlib import Path

# Pillow for texture generation
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing Pillow...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

class SimplePIMonitor:
    """Simplified PI monitor that creates texture files for USD scenes"""
    
    def __init__(self, output_dir="pi_data"):
        # Configuration
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.USERNAME = r"win-lqin09i7rg4\administrator"
        self.PASSWORD = "Brungy509@"
        self.AUTH = HTTPBasicAuth(self.USERNAME, self.PASSWORD)
        
        self.BASE_URL = "https://192.168.74.128/piwebapi"
        self.ATTR_URL = f"{self.BASE_URL}/elements/F1EmQmqOHC3i_kyP3ytLaQ6cSACt0PThFj8BGgrwAMKdv39AV0lOLUxRSU4wOUk3Ukc0XERBVEFCQVNFMVxB5Y2AXOWGt-awo-apnzE/attributes"
        
        self.STATIC_LABELS = [
            "Temp 01 (°C):", "Temp 02 (°C):", "Temp 03 (°C):", "Temp 04 (°C):",
            "Temp 05 (°C):", "Temp 06 (°C):", "Temp 07 (°C):", "Temp 08 (°C):",
            "Temp 09 (°C):", "Temp 10 (°C):", "Temp 11 (°C):",
        ]
        
        # Config
        self.POLL_SEC = 30.0
        self.IMG_SIZE = (1024, 768)
        self.FONT_SIZE = 45
        
        # Output files
        self.texture_path = self.output_dir / "panel_display.png"
        self.data_path = self.output_dir / "pi_data.json"
        
        # Initialize session
        self._session = requests.Session()
        self._session.auth = self.AUTH
        self._session.verify = False
        
        # State variables
        self._font = None
        self._last_values = {}
        self._running = False
        
        print(f"[PI Monitor] Initialized - Output directory: {self.output_dir.absolute()}")
        print(f"[PI Monitor] Texture file: {self.texture_path}")
        print(f"[PI Monitor] Data file: {self.data_path}")
    
    def fmt2(self, v):
        return str(Decimal(str(v)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))
    
    def get_element_attributes(self):
        r = self._session.get(self.ATTR_URL, timeout=5)
        r.raise_for_status()
        return r.json()["Items"]
    
    def get_attribute_value(self, webid):
        r = self._session.get(f"{self.BASE_URL}/streams/{webid}/value", timeout=5)
        r.raise_for_status()
        return r.json()["Value"]
    
    def _ensure_font(self):
        if self._font:
            return self._font
        try:
            self._font = ImageFont.truetype("arial.ttf", self.FONT_SIZE)
        except Exception:
            self._font = ImageFont.load_default()
        return self._font
    
    def create_display_texture(self, values_dict, timestamp):
        """Create the PI display texture PNG"""
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
        
        img.save(self.texture_path, "PNG")
        print(f"[PI Monitor] Texture updated: {self.texture_path}")
    
    def save_data_file(self, values_dict, timestamp):
        """Save PI data to JSON file"""
        data = {
            "timestamp": timestamp,
            "last_updated": datetime.datetime.now().isoformat(),
            "values": {k: self.fmt2(v) for k, v in values_dict.items()}
        }
        
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"[PI Monitor] Data saved: {self.data_path}")
    
    def one_cycle(self):
        """Process one update cycle"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[PI Monitor] Starting update cycle at {timestamp}")
        
        values_dict = {}
        
        ordered_attrs = ["temperature", "TemperatureSetpoint", "PowerUsage", "Current", 
                        "internalCalculOutput", "temp_06", "temp_07", "temp_08", 
                        "temp_09", "temp_10", "temp_11"]
        
        # Fetch PI data
        try:
            all_attrs = {item["Name"]: item["WebId"] for item in self.get_element_attributes()}
            
            for name in ordered_attrs:
                if name in all_attrs:
                    webid = all_attrs[name]
                    val = self.get_attribute_value(webid)
                    values_dict[name] = val
            
            print(f"[PI Monitor] Fetched {len(values_dict)} values from PI system")
            
        except Exception as e:
            print(f"[PI Monitor] Error fetching PI data: {e}")
            # Use test values if PI connection fails
            for i, attr in enumerate(ordered_attrs):
                values_dict[attr] = 25.0 + i * 2.5
            print("[PI Monitor] Using test values due to PI connection error")
        
        # Update files
        if values_dict:
            self.create_display_texture(values_dict, timestamp)
            self.save_data_file(values_dict, timestamp)
            self._last_values = values_dict.copy()
            
            print(f"[PI Monitor] Updated files with {len(values_dict)} sensor values")
    
    def start(self):
        """Start the monitoring loop"""
        self._running = True
        print(f"[PI Monitor] Starting monitoring (polling every {self.POLL_SEC} seconds)")
        print("[PI Monitor] Press Ctrl+C to stop")
        print()
        print("=" * 60)
        print("SETUP INSTRUCTIONS FOR USD VIEWER:")
        print("=" * 60)
        print(f"1. Set your monitor material texture to: {self.texture_path}")
        print(f"2. The texture will update every {self.POLL_SEC} seconds")
        print(f"3. PI data is also saved to: {self.data_path}")
        print("=" * 60)
        print()
        
        try:
            while self._running:
                self.one_cycle()
                time.sleep(self.POLL_SEC)
        except KeyboardInterrupt:
            print("\n[PI Monitor] Stopped by user")
        except Exception as e:
            print(f"[PI Monitor] Error: {e}")
            traceback.print_exc()
    
    def stop(self):
        """Stop the monitoring loop"""
        self._running = False


if __name__ == "__main__":
    try:
        # Create monitor with output in current directory
        monitor = SimplePIMonitor("pi_data")
        monitor.start()
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()