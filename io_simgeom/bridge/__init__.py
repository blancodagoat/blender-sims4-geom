# Sollumz Bridge - Integration between Sims 4 GEOM Tools and Sollumz (GTA V)
# This module provides conversion between Sims 4 and GTA V mesh formats

import bpy
import sys
from typing import Optional

# Check if Sollumz is available
SOLLUMZ_AVAILABLE = False
SOLLUMZ_VERSION = None
_SOLLUMZ_CHECKED = False  # Only print log once


def check_sollumz() -> bool:
    """Check if Sollumz addon is installed and enabled"""
    global SOLLUMZ_AVAILABLE, SOLLUMZ_VERSION, _SOLLUMZ_CHECKED
    
    # Quick check - if already detected via property, just verify it's still there
    if SOLLUMZ_AVAILABLE and hasattr(bpy.types.Object, 'sollum_type'):
        return True
    
    was_available = SOLLUMZ_AVAILABLE
    SOLLUMZ_AVAILABLE = False
    SOLLUMZ_VERSION = None
    
    # Method 1: Check if sollum_type property is registered (most reliable runtime check)
    if hasattr(bpy.types.Object, 'sollum_type'):
        SOLLUMZ_AVAILABLE = True
    
    # Method 2: Check traditional addons
    if not SOLLUMZ_AVAILABLE:
        try:
            for addon_name in bpy.context.preferences.addons.keys():
                if 'sollumz' in addon_name.lower():
                    SOLLUMZ_AVAILABLE = True
                    break
        except:
            pass
    
    # Method 3: Check sys.modules for any sollumz modules
    if not SOLLUMZ_AVAILABLE:
        try:
            for module_name in sys.modules.keys():
                if 'sollumz' in module_name.lower():
                    SOLLUMZ_AVAILABLE = True
                    break
        except:
            pass
    
    # Log only on first detection or status change
    if SOLLUMZ_AVAILABLE and (not _SOLLUMZ_CHECKED or not was_available):
        print("[Sims 4 GEOM] Sollumz detected")
        _SOLLUMZ_CHECKED = True
    
    # Try to get version if available
    if SOLLUMZ_AVAILABLE and SOLLUMZ_VERSION is None:
        try:
            for addon_name in bpy.context.preferences.addons.keys():
                if 'sollumz' in addon_name.lower():
                    addon = bpy.context.preferences.addons.get(addon_name)
                    if addon and addon.module:
                        mod = sys.modules.get(addon.module)
                        if mod and hasattr(mod, 'bl_info'):
                            SOLLUMZ_VERSION = mod.bl_info.get('version')
                            break
        except:
            pass
    
    return SOLLUMZ_AVAILABLE


def get_sollumz_module():
    """Find and return the sollumz_properties module regardless of installation method"""
    # Try direct import first
    try:
        import sollumz_properties
        return sollumz_properties
    except ImportError:
        pass
    
    # Search in sys.modules for the correct module path
    for module_name, module in sys.modules.items():
        if module and 'sollumz_properties' in module_name:
            return module
    
    # Try to find by package name patterns (extensions use different paths)
    for module_name in list(sys.modules.keys()):
        if 'sollumz' in module_name.lower() and module_name.endswith('sollumz_properties'):
            return sys.modules.get(module_name)
    
    return None


def get_sollumz_status() -> str:
    """Get human-readable Sollumz status"""
    if SOLLUMZ_AVAILABLE:
        if SOLLUMZ_VERSION:
            ver_str = '.'.join(map(str, SOLLUMZ_VERSION)) if isinstance(SOLLUMZ_VERSION, tuple) else str(SOLLUMZ_VERSION)
            return f"Sollumz v{ver_str} detected"
        return "Sollumz detected"
    return "Sollumz not found"
