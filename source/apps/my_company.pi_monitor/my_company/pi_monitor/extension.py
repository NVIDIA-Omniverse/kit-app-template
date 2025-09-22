import omni.ext
import traceback

class PIMonitorExtension(omni.ext.IExt):
    """Extension that automatically starts PI monitoring when enabled"""
    
    def on_startup(self, ext_id):
        print("[PI Monitor] Extension starting up...")
        try:
            print("[PI Monitor] About to import PIMonitor...")
            from .pi_sync import PIMonitor
            print("[PI Monitor] Import successful, creating PIMonitor instance...")
            
            self._pi_monitor = PIMonitor()
            print("[PI Monitor] PIMonitor created, starting monitoring...")
            
            self._pi_monitor.start()
            print("[PI Monitor] Extension ready - PI monitoring started automatically")
            
        except ImportError as e:
            print(f"[PI Monitor] Import Error: {e}")
            print(f"[PI Monitor] Full traceback: {traceback.format_exc()}")
        except Exception as e:
            print(f"[PI Monitor] Startup Error: {e}")
            print(f"[PI Monitor] Full traceback: {traceback.format_exc()}")
    
    def on_shutdown(self):
        print("[PI Monitor] Extension shutting down...")
        if hasattr(self, '_pi_monitor'):
            self._pi_monitor.stop()
        print("[PI Monitor] Extension shutdown complete")