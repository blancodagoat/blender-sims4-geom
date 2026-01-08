# Copyright (C) 2019 SmugTomato
# Package import support added 2024
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

"""
Sims 4 .package file importer for Blender

Allows importing GEOM meshes directly from .package files without
needing external tools like S4PE to extract them first.
"""

import os
from typing import List

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty
from bpy.types import Operator, PropertyGroup
from rna_prop_ui import rna_idprop_ui_create

import json

from io_simgeom.io.package_load import PackageReader, GEOM_TYPE
from io_simgeom.io.geom_load import GeomLoader
from io_simgeom.util.globals import Globals


# Global storage for GEOM entries found in package
_package_geoms = []
_current_package_path = ""


class SIMGEOM_OT_import_package(Operator, ImportHelper):
    """Import GEOM meshes from a Sims 4 .package file"""
    bl_idname = "simgeom.import_package"
    bl_label = "Import from .package"
    bl_options = {'REGISTER', 'UNDO'}

    # ImportHelper mixin class uses this
    filename_ext = ".package"
    filter_glob: StringProperty(default="*.package", options={'HIDDEN'})

    # Sims 4 rig options
    rig_type: EnumProperty(
        name="Choose Rig:",
        description="Rig to import alongside the mesh",
        items=[
            ('None', 'None', 'None'),
            ('yfRig', 'Adult Female', 'yfRig'),
            ('ymRig', 'Adult Male', 'ymRig'),
            ('cfRig', 'Child Female', 'cfRig'),
            ('cmRig', 'Child Male', 'cmRig'),
            ('puRig', 'Toddler', 'puRig'),
            ('cuRig', 'Infant', 'cuRig'),
            ('adRig', 'Dog Adult', 'adRig'),
            ('alRig', 'Dog Small', 'alRig'),
            ('cdRig', 'Dog Child', 'cdRig'),
            ('acRig', 'Cat Adult', 'acRig'),
            ('ccRig', 'Cat Child', 'ccRig'),
        ],
        default='None'
    )
    
    do_import_normals: BoolProperty(
        name="Preserve Normals",
        description="Import the original normals as custom split normals (recommended)",
        default=True
    )
    
    import_all: BoolProperty(
        name="Import All GEOMs",
        description="Import all GEOM meshes found in the package",
        default=True
    )

    def execute(self, context):
        global _package_geoms, _current_package_path
        
        # Load the package
        package = PackageReader(self.filepath)
        if not package.load():
            self.report({'ERROR'}, "Failed to load package file")
            return {'CANCELLED'}
        
        # Find GEOM resources
        geom_entries = package.get_geom_resources()
        
        if not geom_entries:
            self.report({'WARNING'}, "No GEOM meshes found in this package")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Found {len(geom_entries)} GEOM(s) in package")
        
        # Import rig if requested
        if self.rig_type != 'None':
            rigpath = Globals.ROOTDIR + '/data/rigs/' + self.rig_type + '.grannyrig'
            if os.path.exists(rigpath):
                bpy.ops.simgeom.import_rig(filepath=rigpath)
        
        # Import GEOMs
        if self.import_all:
            for i, entry in enumerate(geom_entries):
                self._import_geom(context, package, entry, i)
        else:
            # Store for selection dialog
            _package_geoms = geom_entries
            _current_package_path = self.filepath
            # Show selection popup
            bpy.ops.simgeom.select_package_geoms('INVOKE_DEFAULT')
        
        return {'FINISHED'}
    
    def _import_geom(self, context, package: PackageReader, entry, index: int):
        """Import a single GEOM from the package"""
        # Get decompressed data
        geom_data = package.get_resource_data(entry)
        if geom_data is None:
            print(f"Failed to extract GEOM {entry.instance_hex}")
            return False
        
        try:
            geomdata = GeomLoader.readGeomFromBytes(geom_data)
        except Exception as e:
            print(f"Failed to parse GEOM {entry.instance_hex}: {e}")
            return False
        
        # Fill a Dictionary with hexed Vertex ID as key and List of vertex indices
        lowest_id = 0x7fffffff
        ids = {}
        if geomdata.element_data[0].vertex_id:
            for i, v in enumerate(geomdata.element_data):
                if v.vertex_id[0] < lowest_id:
                    lowest_id = v.vertex_id[0]
                if not hex(v.vertex_id[0]) in ids:
                    ids[hex(v.vertex_id[0])] = [i]
                else:
                    ids[hex(v.vertex_id[0])].append(i)

        # Build vertex array and get face array to build the mesh
        vertices = [(v.position[0], -v.position[2], v.position[1]) for v in geomdata.element_data]
        faces = geomdata.faces
        
        # Create mesh with instance ID as name
        mesh_name = f"geom_{entry.instance_hex}"
        mesh = bpy.data.meshes.new(mesh_name)
        obj = bpy.data.objects.new(mesh_name, mesh)
        mesh.from_pydata(vertices, [], faces)

        # Shade smooth before applying custom normals
        for poly in mesh.polygons:
            poly.use_smooth = True

        # Add custom split normals layer if enabled
        if geomdata.element_data[0].normal:
            normals = [(v.normal[0], -v.normal[2], v.normal[1]) for v in geomdata.element_data]
            mesh.normals_split_custom_set_from_vertices(normals)
            if hasattr(mesh, 'use_auto_smooth'):
                mesh.use_auto_smooth = True

        # Link the newly created object to the active collection
        context.view_layer.active_layer_collection.collection.objects.link(obj)
        
        # Deselect everything but newly imported mesh, then make it the active object
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        # Set Vertex Groups
        if geomdata.bones:
            for bone in geomdata.bones:
                obj.vertex_groups.new(name=bone)
        
        # Set Vertex Group Weights
        skip_counter = 0
        if geomdata.element_data[0].assignment and geomdata.bones:
            for i, vert in enumerate(geomdata.element_data):
                for j in range(4):
                    group_index = vert.assignment[j]
                    if group_index >= len(geomdata.bones):
                        skip_counter += 1
                        continue
                    groupname = geomdata.bones[group_index]
                    vertgroup = obj.vertex_groups[groupname]
                    weight = vert.weights[j] if vert.weights else 0
                    if weight > 0:
                        vertgroup.add([i], weight, 'ADD')
        
        if skip_counter > 0:
            print(f"Skipped {skip_counter} bone assignments that were out of range.")
        
        # Set UV Coordinates for every UV channel
        if geomdata.element_data[0].uv:
            for i in range(len(geomdata.element_data[0].uv)):
                mesh.uv_layers.new(name='UV_' + str(i))
                mesh.uv_layers.active = mesh.uv_layers['UV_' + str(i)]

                for j, polygon in enumerate(mesh.polygons):
                    for k, loopindex in enumerate(polygon.loop_indices):
                        meshuvloop = mesh.uv_layers.active.data[loopindex]
                        vertex_index = geomdata.faces[j][k]
                        uv = geomdata.element_data[vertex_index].uv[i]
                        meshuvloop.uv = (uv[0], -uv[1] + 1)
            mesh.uv_layers.active = mesh.uv_layers['UV_0']

        bpy.ops.object.mode_set(mode='OBJECT')

        # Set Vertex Colors
        if geomdata.element_data[0].tagvalue:
            float_colors = []
            for el in geomdata.element_data:
                float_color = []
                for val in el.tagvalue:
                    float_color.append(val / 255)
                float_colors.append(float_color)
            
            vcol_layer = mesh.vertex_colors.new(name="SIMGEOM_TAGVAL", do_init=False)
            for poly in mesh.polygons:
                for vert_index, loop_index in zip(poly.vertices, poly.loop_indices):
                    vcol_layer.data[loop_index].color = float_colors[vert_index]

        # Set Custom Properties
        self._add_prop(obj, '__S4_GEOM__', 1)
        self._add_prop(obj, 'geom_version', geomdata.version if geomdata.version else 14)
        self._add_prop(obj, 'rcol_chunks', geomdata.internal_chunks if geomdata.internal_chunks else [])
        self._add_prop(obj, 'rcol_external', geomdata.external_resources if geomdata.external_resources else [])
        self._add_prop(obj, 'shaderdata', geomdata.shaderdata if geomdata.shaderdata else [])
        self._add_prop(obj, 'mergegroup', geomdata.merge_group if geomdata.merge_group else 0)
        self._add_prop(obj, 'sortorder', geomdata.sort_order if geomdata.sort_order else 0)
        self._add_prop(obj, 'skincontroller', geomdata.skin_controller_index if geomdata.skin_controller_index else 0)
        self._add_prop(obj, 'tgis', geomdata.tgi_list if geomdata.tgi_list else [])
        self._add_prop(obj, 'embedded_id', geomdata.embeddedID if geomdata.embeddedID else "0x0")
        self._add_prop(obj, 'vert_ids', ids)
        
        # Store package instance ID for reference
        self._add_prop(obj, 'package_instance', entry.instance_hex)
        
        start_id_descript = "Starting Vertex ID"
        for key, value in Globals.CAS_INDICES.items():
            start_id_descript += "\n" + str(key) + " - " + str(value)
        self._add_prop(obj, 'start_id', lowest_id if lowest_id != 0x7fffffff else 0, descript=start_id_descript)

        return True
    
    def _add_prop(self, obj, key, value, minmax: List[int] = [0, 2147483647], descript: str = "prop"):
        try:
            if isinstance(value, dict) or (isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict)):
                obj[key] = json.dumps(value)
            elif isinstance(value, (int, float, str)):
                rna_idprop_ui_create(obj, key, default=value, min=minmax[0], max=minmax[1], 
                                    soft_min=minmax[0], soft_max=minmax[1], description=descript)
            else:
                obj[key] = value

            for area in bpy.context.screen.areas:
                area.tag_redraw()
        except Exception as e:
            print(f"--- Property '{key}' stored without UI metadata: {e}")
            obj[key] = json.dumps(value) if isinstance(value, (dict, list)) else value


class GeomEntryItem(PropertyGroup):
    """Property group for GEOM entries in selection list"""
    name: StringProperty(name="Name")
    instance: StringProperty(name="Instance ID")
    selected: BoolProperty(name="Import", default=True)
    index: bpy.props.IntProperty()


class SIMGEOM_OT_select_package_geoms(Operator):
    """Select which GEOMs to import from package"""
    bl_idname = "simgeom.select_package_geoms"
    bl_label = "Select GEOMs to Import"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    def execute(self, context):
        # This operator shows a popup for selection
        # Implementation depends on how you want the UI to work
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Found {len(_package_geoms)} GEOM(s)")
        
        box = layout.box()
        for i, entry in enumerate(_package_geoms):
            row = box.row()
            row.label(text=f"GEOM {i+1}: {entry.instance_hex}")
