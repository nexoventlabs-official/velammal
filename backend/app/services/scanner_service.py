"""
Scanner service using Windows WIA (Windows Image Acquisition).
This allows direct scanner control from Python - FREE!
"""
import os
import uuid
from typing import List, Optional
from app.config import settings

# Windows-only imports
SCANNER_AVAILABLE = False
wia = None

try:
    import win32com.client
    wia = win32com.client
    SCANNER_AVAILABLE = True
    print("INFO: WIA Scanner service initialized (Windows)")
except ImportError:
    print("WARNING: pywin32 not available - scanner service disabled")
except Exception as e:
    print(f"WARNING: Scanner service init error: {e}")


# WIA Constants
WIA_DEVICE_TYPE_SCANNER = 1
WIA_INTENT_IMAGE_TYPE_COLOR = 1
WIA_INTENT_IMAGE_TYPE_GRAYSCALE = 2
WIA_IMG_FORMAT_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
WIA_IMG_FORMAT_JPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"


def get_available_scanners() -> List[dict]:
    """Get list of connected scanners."""
    if not SCANNER_AVAILABLE:
        return []
    
    try:
        device_manager = wia.client.Dispatch("WIA.DeviceManager")
        scanners = []
        
        for i in range(1, device_manager.DeviceInfos.Count + 1):
            device_info = device_manager.DeviceInfos.Item(i)
            if device_info.Type == WIA_DEVICE_TYPE_SCANNER:
                scanners.append({
                    "id": device_info.DeviceID,
                    "name": device_info.Properties("Name").Value,
                    "index": len(scanners)
                })
        
        return scanners
    except Exception as e:
        print(f"Error getting scanners: {e}")
        return []


def scan_document(
    scanner_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    color_mode: str = "color",  # "color" or "grayscale"
    dpi: int = 200
) -> dict:
    """
    Scan a document from the connected scanner.
    
    Returns:
        {
            "success": bool,
            "file_path": str or None,
            "error": str or None
        }
    """
    if not SCANNER_AVAILABLE:
        return {"success": False, "file_path": None, "error": "Scanner service not available"}
    
    try:
        device_manager = wia.client.Dispatch("WIA.DeviceManager")
        
        # Find scanner
        scanner_device = None
        for i in range(1, device_manager.DeviceInfos.Count + 1):
            device_info = device_manager.DeviceInfos.Item(i)
            if device_info.Type == WIA_DEVICE_TYPE_SCANNER:
                if scanner_id is None or device_info.DeviceID == scanner_id:
                    scanner_device = device_info.Connect()
                    break
        
        if not scanner_device:
            return {"success": False, "file_path": None, "error": "No scanner found"}
        
        # Get scanner item (first scan source)
        scanner_item = scanner_device.Items(1)
        
        # Set scan properties
        try:
            # Color mode
            if color_mode == "grayscale":
                scanner_item.Properties("6146").Value = WIA_INTENT_IMAGE_TYPE_GRAYSCALE
            else:
                scanner_item.Properties("6146").Value = WIA_INTENT_IMAGE_TYPE_COLOR
            
            # DPI
            scanner_item.Properties("6147").Value = dpi  # Horizontal DPI
            scanner_item.Properties("6148").Value = dpi  # Vertical DPI
        except Exception as prop_err:
            print(f"Warning: Could not set scan properties: {prop_err}")
        
        # Perform scan
        image = scanner_item.Transfer(WIA_IMG_FORMAT_PNG)
        
        # Save to file
        if output_dir is None:
            output_dir = settings.UPLOAD_DIR
        os.makedirs(output_dir, exist_ok=True)
        
        file_name = f"scan_{uuid.uuid4().hex[:8]}.png"
        file_path = os.path.join(output_dir, file_name)
        
        image.SaveFile(file_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "error": None
        }
        
    except Exception as e:
        error_msg = str(e)
        if "0x80210006" in error_msg:
            error_msg = "Scanner is busy or paper not loaded"
        elif "0x80210001" in error_msg:
            error_msg = "Scanner not ready - check connection"
        elif "0x80210003" in error_msg:
            error_msg = "Scanner cover is open"
        
        return {
            "success": False,
            "file_path": None,
            "error": error_msg
        }


def is_scanner_available() -> bool:
    """Check if any scanner is connected."""
    scanners = get_available_scanners()
    return len(scanners) > 0
