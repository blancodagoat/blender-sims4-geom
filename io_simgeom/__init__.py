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
from io_simgeom.io.package_import import SIMGEOM_OT_import_package, SIMGEOM_OT_select_package_geoms, SIMGEOM_OT_export_rle_textures
from io_simgeom.ui                import SIMGEOM_PT_utility_panel
from io_simgeom.operators         import *
from io_simgeom.util.globals      import Globals

from urllib.request import urlopen, Request
from urllib.error import URLError
import json

bl_info = {
    "name": "Sims 4 GEOM Tools",
    "author": "SmugTomato (updated for TS4)",
    "category": "Import-Export",
    "version": (3, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import/Export",
    "description": "Importer and exporter for Sims 4 GEOM (.simgeom) files"
}

classes = [
    SIMGEOM_PT_utility_panel,
    SIMGEOM_OT_import_rig,
    SIMGEOM_OT_import_geom,
    SIMGEOM_OT_import_package,
    SIMGEOM_OT_select_package_geoms,
    SIMGEOM_OT_export_rle_textures,
    SIMGEOM_OT_export_geom,
    SIMGEOM_OT_import_rig_helper,
    SIMGEOM_OT_import_morph,
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


def check_version():
    # Version checking disabled for this fork
    return CHECK_UPDATED


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(SIMGEOM_OT_import_package.bl_idname, text="Sims 4 Package (.package)")
    self.layout.operator(SIMGEOM_OT_import_geom.bl_idname, text="Sims 4 GEOM (.simgeom)")
    self.layout.operator(SIMGEOM_OT_import_morph.bl_idname, text="Sims 4 Morph (.simgeom)")
    self.layout.operator(SIMGEOM_OT_import_rig.bl_idname, text="Sims 4 Rig (.grannyrig)")


def menu_func_export(self, context):
    self.layout.operator(SIMGEOM_OT_export_geom.bl_idname, text="Sims 4 GEOM (.simgeom)")
    self.layout.operator(SIMGEOM_OT_export_rle_textures.bl_idname, text="Sims 4 Textures (RLE → DDS)")


def register():
    for item in classes:
        bpy.utils.register_class(item)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

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
    for item in classes:
        bpy.utils.unregister_class(item)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    del bpy.types.Object.morph_link
    del bpy.types.Object.morph_name


if __name__ == "__main__":
    register()

rootdir = os.path.dirname(os.path.realpath(__file__))
Globals.init(rootdir, check_version())
