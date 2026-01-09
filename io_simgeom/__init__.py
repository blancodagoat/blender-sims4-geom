# Copyright (C) 2019 SmugTomato
# Updated for Sims 4 support
# 
# This file is part of BlenderGeom.
# 
# BlenderGeom is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# BlenderGeom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with BlenderGeom.  If not, see <http://www.gnu.org/licenses/>.

# Set Current Working Directory to addon root folder
# This needs to be done to find the included data files

import os

import bpy

from io_simgeom.io.geom_export    import SIMGEOM_OT_export_geom
from io_simgeom.io.geom_import    import SIMGEOM_OT_import_geom
from io_simgeom.io.morph_import   import SIMGEOM_OT_import_morph
from io_simgeom.io.rig_import     import SIMGEOM_OT_import_rig
from io_simgeom.io.package_import import (
    SIMGEOM_OT_import_package,
    SIMGEOM_OT_select_package_geoms,
    SIMGEOM_OT_export_rle_textures,
    SIMGEOM_OT_reload_textures,
    SIMGEOM_OT_batch_export_geom,
    SIMGEOM_OT_generate_lods
)
from io_simgeom.ui                import (
    SIMGEOM_PT_utility_panel,
    SIMGEOM_PT_sidebar_panel,
    SIMGEOM_PT_sidebar_textures,
    SIMGEOM_PT_sidebar_vertex_ids,
    register_rig_enum
)
from io_simgeom.operators         import *

# Sollumz Bridge (GTA V integration)
from io_simgeom.bridge import operators as bridge_operators
from io_simgeom.bridge import ui as bridge_ui
from io_simgeom.bridge import check_sollumz


class SIMGEOM_OT_check_updates(bpy.types.Operator):
    """Check for addon updates on GitHub"""
    bl_idname = "simgeom.check_updates"
    bl_label = "Check for Updates"
    
    def execute(self, context):
        # Run synchronous check
        try:
            req = Request(
                GITHUB_API_URL,
                headers={'User-Agent': 'Blender-Sims4-GEOM-Addon'}
            )
            response = urlopen(req, timeout=10)
            data = json.loads(response.read().decode('utf-8'))
            
            latest_tag = data.get('tag_name', '')
            latest_version = parse_version(latest_tag)
            current_version = bl_info['version']
            
            Globals.CURRENT_VERSION = current_version
            Globals.LATEST_VERSION = latest_version
            Globals.LATEST_VERSION_STR = latest_tag
            Globals.UPDATE_URL = data.get('html_url', f'https://github.com/{GITHUB_REPO}/releases/latest')
            
            if latest_version > current_version:
                Globals.OUTDATED = CHECK_OUTDATED
                self.report({'INFO'}, f"Update available: {latest_tag}")
            else:
                Globals.OUTDATED = CHECK_UPDATED
                self.report({'INFO'}, f"You have the latest version (v{'.'.join(map(str, current_version))})")
                
        except Exception as e:
            Globals.OUTDATED = CHECK_FAILED
            self.report({'WARNING'}, f"Update check failed: {e}")
        
        return {'FINISHED'}
from io_simgeom.util.globals      import Globals

from urllib.request import urlopen, Request
from urllib.error import URLError
import json
import threading

bl_info = {
    "name": "Sims 4 GEOM Tools",
    "author": "blancodagoat",
    "category": "Import-Export",
    "version": (3, 1, 4),
    "blender": (2, 80, 0),
    "location": "3D View > Sidebar > Sims 4",
    "description": "Importer and exporter for Sims 4 GEOM and Package files"
}

# GitHub repository for update checks
GITHUB_REPO = "blancodagoat/blender-sims4-geom"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

classes = [
    # Panels
    SIMGEOM_PT_sidebar_panel,
    SIMGEOM_PT_sidebar_textures,
    SIMGEOM_PT_sidebar_vertex_ids,
    SIMGEOM_PT_utility_panel,
    # Operators - Import
    SIMGEOM_OT_import_rig,
    SIMGEOM_OT_import_geom,
    SIMGEOM_OT_import_package,
    SIMGEOM_OT_select_package_geoms,
    SIMGEOM_OT_import_morph,
    # Operators - Export
    SIMGEOM_OT_export_geom,
    SIMGEOM_OT_export_rle_textures,
    SIMGEOM_OT_batch_export_geom,
    SIMGEOM_OT_generate_lods,
    # Operators - Utility
    SIMGEOM_OT_import_rig_helper,
    SIMGEOM_OT_reload_textures,
    SIMGEOM_OT_check_updates,
    SIMGEOM_OT_rebuild_bone_database,
    SIMGEOM_OT_rename_bone_groups,
    SIMGEOM_OT_reset_id_margin,
    SIMGEOM_OT_recalc_ids,
    SIMGEOM_OT_remove_ids,
    SIMGEOM_OT_copy_data,
    SIMGEOM_OT_make_morph
]

CHECK_FAILED = -1
CHECK_UPDATED = 0
CHECK_OUTDATED = 1


def parse_version(version_str: str) -> tuple:
    """Parse version string like 'v3.1.0' or '3.1.0' into tuple (3, 1, 0)"""
    try:
        # Remove 'v' prefix if present
        version_str = version_str.lstrip('vV')
        parts = version_str.split('.')
        return tuple(int(p) for p in parts[:3])
    except:
        return (0, 0, 0)


def check_version_async():
    """Check for updates in background thread"""
    try:
        req = Request(
            GITHUB_API_URL,
            headers={'User-Agent': 'Blender-Sims4-GEOM-Addon'}
        )
        response = urlopen(req, timeout=5)
        data = json.loads(response.read().decode('utf-8'))
        
        latest_tag = data.get('tag_name', '')
        latest_version = parse_version(latest_tag)
        current_version = bl_info['version']
        
        # Store in Globals
        Globals.CURRENT_VERSION = current_version
        Globals.LATEST_VERSION = latest_version
        Globals.LATEST_VERSION_STR = latest_tag
        Globals.UPDATE_URL = data.get('html_url', f'https://github.com/{GITHUB_REPO}/releases/latest')
        
        # Compare versions
        if latest_version > current_version:
            Globals.OUTDATED = CHECK_OUTDATED
            print(f"[Sims 4 GEOM Tools] Update available: {latest_tag} (current: v{'.'.join(map(str, current_version))})")
        else:
            Globals.OUTDATED = CHECK_UPDATED
            
    except Exception as e:
        print(f"[Sims 4 GEOM Tools] Update check failed: {e}")
        Globals.OUTDATED = CHECK_FAILED


def check_version():
    """Start async version check and return current state"""
    # Store current version
    Globals.CURRENT_VERSION = bl_info['version']
    
    # Start background check (non-blocking)
    thread = threading.Thread(target=check_version_async, daemon=True)
    thread.start()
    
    return CHECK_UPDATED  # Return updated initially, async will update Globals


# File menu entries (minimal - main UI is in N-Panel)
def menu_func_import(self, context):
    self.layout.operator(SIMGEOM_OT_import_package.bl_idname, text="Sims 4 Package (.package)")


def menu_func_export(self, context):
    self.layout.operator(SIMGEOM_OT_export_geom.bl_idname, text="Sims 4 GEOM (.simgeom)")


def register():
    # Register rig type enum
    register_rig_enum()
    
    for item in classes:
        bpy.utils.register_class(item)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    
    # Register Sollumz bridge
    bridge_operators.register()
    bridge_ui.register()
    
    # Check Sollumz availability
    check_sollumz()

    # Links morph to it's main geom mesh
    bpy.types.Object.morph_link = bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, ob : ob.type == 'MESH',
        name="Linked to",
        description="The base GEOM this morph should be applied to"
    )

    # Name for morph meshes, added as suffix on export
    bpy.types.Object.morph_name = bpy.props.StringProperty(
        default="",
        name="Morph Name",
        description="Will be added as a suffix to the linked GEOM's exported filename"
    )

    # Vertex ID Margin
    bpy.types.Scene.v_id_margin = bpy.props.FloatProperty(
        name="Margin",
        description="How far away vertices are allowed to be for them to still be considered in identical locations",
        min=0.0,
        soft_min=0.0,
        max=0.1,
        soft_max=0.1,
        default=0.00001,
        precision=6
    )


def unregister():
    # Unregister Sollumz bridge
    bridge_ui.unregister()
    bridge_operators.unregister()
    
    for item in classes:
        bpy.utils.unregister_class(item)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    del bpy.types.Object.morph_link
    del bpy.types.Object.morph_name
    del bpy.types.Scene.simgeom_rig_type


if __name__ == "__main__":
    register()

rootdir = os.path.dirname(os.path.realpath(__file__))
Globals.init(rootdir, check_version())
