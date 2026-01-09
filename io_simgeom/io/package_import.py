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
import tempfile
from typing import List

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty
from bpy.types import Operator, PropertyGroup
from rna_prop_ui import rna_idprop_ui_create

import json

from io_simgeom.io.package_load import PackageReader, GEOM_TYPE, DDS_TYPE, RLE2_TYPE, RLES_TYPE
from io_simgeom.io.geom_load import GeomLoader
from io_simgeom.util.globals import Globals

# Try to load s4pi for RLE conversion
_s4pi_available = False
_RLEResource = None

def _init_s4pi():
    """Initialize s4pi.ImageResource for RLE to DDS conversion"""
    global _s4pi_available, _RLEResource
    
    if _s4pi_available:
        return True
    
    try:
        import clr
        import sys
        
        # Try multiple locations for s4pe folder
        possible_paths = []
        
        # 1. Adjacent to io_simgeom package (workspace/addon folder)
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        possible_paths.append(os.path.join(addon_dir, "s4pe"))
        
        # 2. One level up from addon
        possible_paths.append(os.path.join(os.path.dirname(addon_dir), "s4pe"))
        
        # 3. Common locations
        possible_paths.append(r"D:\downloads\MTS_SmugTomato_2019382_BlenderGeom_2.1.4\s4pe")
        
        s4pe_dir = None
        for path in possible_paths:
            if os.path.exists(path) and os.path.isfile(os.path.join(path, "s4pi.ImageResource.dll")):
                s4pe_dir = path
                break
        
        if not s4pe_dir:
            # Don't spam the console, just return False silently
            return False
        
        # Add to path and load assemblies
        if s4pe_dir not in sys.path:
            sys.path.append(s4pe_dir)
        
        # Load required assemblies
        clr.AddReference(os.path.join(s4pe_dir, "s4pi.Interfaces.dll"))
        clr.AddReference(os.path.join(s4pe_dir, "s4pi.ImageResource.dll"))
        
        from s4pi.ImageResource import RLEResource
        _RLEResource = RLEResource
        _s4pi_available = True
        print(f"  s4pi.ImageResource loaded from {s4pe_dir}")
        return True
        
    except Exception as e:
        print(f"  Failed to load s4pi: {e}")
        return False


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
        name="Import All LODs",
        description="Import all LOD versions (unchecked = highest quality only)",
        default=False
    )
    
    import_materials: BoolProperty(
        name="Import Materials",
        description="Auto-create materials from textures in the package",
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
        
        # Import GEOMs - either all LODs or just the highest quality
        if self.import_all:
            # Import all GEOMs including lower LODs
            geoms_to_import = geom_entries
            self.report({'INFO'}, f"Importing all {len(geoms_to_import)} GEOM(s)")
        else:
            # Find and import only the LARGEST GEOM (highest LOD) per unique mesh
            geoms_to_import = self._get_largest_geoms(package, geom_entries)
            self.report({'INFO'}, f"Importing {len(geoms_to_import)} highest-LOD GEOM(s)")
        
        for i, entry in enumerate(geoms_to_import):
            self._import_geom(context, package, entry, i)
        
        return {'FINISHED'}
    
    def _get_largest_geoms(self, package, geom_entries):
        """
        Filter to only return the largest GEOM for each unique mesh.
        Packages often contain multiple LODs (Level of Detail) versions.
        We want only the highest quality (largest) one.
        """
        # Group by unique identifiers - GEOMs with same Group ID are usually LODs
        groups = {}
        for entry in geom_entries:
            # Use (type, group) as key to group LODs together
            # Different instance IDs with same group are typically LOD variants
            key = (entry.resource_type, entry.resource_group)
            
            # Get decompressed size to compare
            data = package.get_resource_data(entry)
            size = len(data) if data else 0
            
            if key not in groups:
                groups[key] = (entry, size)
            elif size > groups[key][1]:
                # Found a larger version - keep this one
                groups[key] = (entry, size)
        
        # Return just the entries (not sizes)
        return [entry for entry, size in groups.values()]
    
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

        # Create materials from textures if enabled
        if self.import_materials:
            materials = self._create_materials(package, geomdata, entry.instance_hex)
            for material in materials:
                obj.data.materials.append(material)

        return True
    
    def _create_materials(self, package: PackageReader, geomdata, instance_hex: str):
        """
        Create Blender materials from GEOM texture references
        
        Creates a SEPARATE material for each texture so user can easily switch between them.
        Returns a list of materials.
        """
        materials = []
        
        # Debug: show available texture resources in package
        dds_resources = package.get_dds_resources()
        rle_resources = package.get_rle_resources()
        
        print(f"  Package texture summary:")
        print(f"    DDS (0x00B2D882): {len(dds_resources)}")
        print(f"    RLE (0x3453CF95/0xBA856C78): {len(rle_resources)}")
        
        if rle_resources:
            print(f"  RLE texture instances:")
            for rle in rle_resources[:5]:
                print(f"    - {rle.instance_hex} (type {rle.type_hex})")
            if len(rle_resources) > 5:
                print(f"    ... and {len(rle_resources) - 5} more")
        
        # Create temp directory for textures
        temp_dir = tempfile.mkdtemp(prefix="simgeom_tex_")
        
        # Collect all available textures in the package
        all_textures = dds_resources + rle_resources
        
        if not all_textures:
            # Create a basic material if no textures
            mat = bpy.data.materials.new(name=f"Mat_{instance_hex}")
            mat.use_nodes = True
            print(f"  Created basic material (no textures)")
            return [mat]
        
        print(f"  Creating separate materials for {len(all_textures)} texture(s)")
        
        # Load ALL textures - categorize by type
        rle2_textures = [t for t in all_textures if t.resource_type == RLE2_TYPE]
        rles_textures = [t for t in all_textures if t.resource_type == RLES_TYPE]
        dds_textures = [t for t in all_textures if t.resource_type == DDS_TYPE]
        
        print(f"    RLE2 (diffuse): {len(rle2_textures)}")
        print(f"    RLES (specular): {len(rles_textures)}")
        print(f"    DDS: {len(dds_textures)}")
        
        # Get first specular texture (shared across diffuse materials)
        specular_img = None
        if rles_textures:
            spec_entry = rles_textures[0]
            print(f"  Converting specular texture ({spec_entry.instance_hex})...")
            spec_data = self._convert_rle_to_dds(package.get_resource_data(spec_entry))
            if spec_data:
                spec_filename = f"specular_{spec_entry.instance:016X}.dds"
                spec_path = os.path.join(temp_dir, spec_filename)
                try:
                    with open(spec_path, 'wb') as f:
                        f.write(spec_data)
                    specular_img = bpy.data.images.load(spec_path)
                    specular_img.colorspace_settings.name = 'Non-Color'
                    print(f"    Loaded specular texture")
                except Exception as e:
                    print(f"    Failed to load specular: {e}")
        
        # Create a material for EACH RLE2 (diffuse) texture
        for i, tex_entry in enumerate(rle2_textures):
            print(f"  Converting RLE2 texture {i+1}/{len(rle2_textures)} ({tex_entry.instance_hex})...")
            tex_data = self._convert_rle_to_dds(package.get_resource_data(tex_entry))
            if not tex_data:
                print(f"    Failed to convert")
                continue
            
            dds_filename = f"diffuse_{tex_entry.instance:016X}.dds"
            dds_path = os.path.join(temp_dir, dds_filename)
            
            try:
                with open(dds_path, 'wb') as f:
                    f.write(tex_data)
            except Exception as e:
                print(f"    Failed to save: {e}")
                continue
            
            try:
                img = bpy.data.images.load(dds_path)
            except Exception as e:
                print(f"    Failed to load: {e}")
                continue
            
            # Create material for this diffuse texture
            mat_name = f"Diffuse_{i+1}_{tex_entry.instance:08X}"
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            mat.blend_method = 'HASHED'
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            
            # Clear default nodes
            nodes.clear()
            
            # Create output and BSDF nodes
            output_node = nodes.new('ShaderNodeOutputMaterial')
            output_node.location = (400, 0)
            
            bsdf_node = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf_node.location = (0, 0)
            links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            # Add diffuse texture
            tex_node = nodes.new('ShaderNodeTexImage')
            tex_node.location = (-400, 300)
            tex_node.label = "Diffuse"
            tex_node.image = img
            links.new(tex_node.outputs['Color'], bsdf_node.inputs['Base Color'])
            links.new(tex_node.outputs['Alpha'], bsdf_node.inputs['Alpha'])
            
            # Add specular texture if available
            if specular_img:
                spec_node = nodes.new('ShaderNodeTexImage')
                spec_node.location = (-400, 0)
                spec_node.label = "Specular"
                spec_node.image = specular_img
                links.new(spec_node.outputs['Color'], bsdf_node.inputs['Specular IOR Level'])
            
            materials.append(mat)
            print(f"    Created material: {mat_name}")
        
        # Create materials for additional specular textures (if more than 1)
        for i, tex_entry in enumerate(rles_textures[1:], start=2):
            print(f"  Converting RLES texture {i}/{len(rles_textures)} ({tex_entry.instance_hex})...")
            tex_data = self._convert_rle_to_dds(package.get_resource_data(tex_entry))
            if not tex_data:
                print(f"    Failed to convert")
                continue
            
            dds_filename = f"specular_{tex_entry.instance:016X}.dds"
            dds_path = os.path.join(temp_dir, dds_filename)
            
            try:
                with open(dds_path, 'wb') as f:
                    f.write(tex_data)
                img = bpy.data.images.load(dds_path)
                img.colorspace_settings.name = 'Non-Color'
            except Exception as e:
                print(f"    Failed to load: {e}")
                continue
            
            # Create material for this specular texture
            mat_name = f"Specular_{i}_{tex_entry.instance:08X}"
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            
            output_node = nodes.new('ShaderNodeOutputMaterial')
            output_node.location = (400, 0)
            
            bsdf_node = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf_node.location = (0, 0)
            links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            spec_node = nodes.new('ShaderNodeTexImage')
            spec_node.location = (-400, 0)
            spec_node.label = "Specular"
            spec_node.image = img
            links.new(spec_node.outputs['Color'], bsdf_node.inputs['Specular IOR Level'])
            
            materials.append(mat)
            print(f"    Created material: {mat_name}")
        
        # Create materials for DDS textures
        for i, tex_entry in enumerate(dds_textures):
            print(f"  Loading DDS texture {i+1}/{len(dds_textures)} ({tex_entry.instance_hex})...")
            tex_data = package.get_resource_data(tex_entry)
            if not tex_data:
                continue
            
            dds_filename = f"texture_{tex_entry.instance:016X}.dds"
            dds_path = os.path.join(temp_dir, dds_filename)
            
            try:
                with open(dds_path, 'wb') as f:
                    f.write(tex_data)
                img = bpy.data.images.load(dds_path)
            except Exception as e:
                print(f"    Failed to load: {e}")
                continue
            
            mat_name = f"DDS_{i+1}_{tex_entry.instance:08X}"
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            
            output_node = nodes.new('ShaderNodeOutputMaterial')
            output_node.location = (400, 0)
            
            bsdf_node = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf_node.location = (0, 0)
            links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            tex_node = nodes.new('ShaderNodeTexImage')
            tex_node.location = (-400, 300)
            tex_node.label = "Texture"
            tex_node.image = img
            links.new(tex_node.outputs['Color'], bsdf_node.inputs['Base Color'])
            
            materials.append(mat)
            print(f"    Created material: {mat_name}")
        
        print(f"  Created {len(materials)} material(s) total")
        return materials if materials else [self._create_basic_material(instance_hex)]
    
    def _create_basic_material(self, instance_hex: str):
        """Create a basic material with no textures"""
        mat = bpy.data.materials.new(name=f"Mat_{instance_hex}")
        mat.use_nodes = True
        return mat
    
    def _convert_rle_to_dds(self, rle_data: bytes) -> bytes:
        """
        Convert Sims 4 RLE texture to standard DDS format
        
        First tries to use s4pi.ImageResource.dll if available,
        falls back to manual conversion.
        """
        if not rle_data or len(rle_data) < 16:
            return None
        
        # Try using s4pi first (most reliable)
        if _init_s4pi():
            try:
                return self._convert_rle_with_s4pi(rle_data)
            except Exception as e:
                print(f"    s4pi conversion failed: {e}, trying manual...")
        
        # Fall back to manual conversion
        return self._convert_rle_manual(rle_data)
    
    def _convert_rle_with_s4pi(self, rle_data: bytes) -> bytes:
        """Use s4pi.ImageResource to convert RLE to DDS"""
        import clr
        from System.IO import MemoryStream
        
        # Create a MemoryStream from the RLE data
        ms_in = MemoryStream(rle_data)
        
        # Create RLEResource and get DDS data
        rle_res = _RLEResource(0, ms_in)
        
        # Get the DDS stream
        ms_out = MemoryStream()
        rle_res.ToDDS().CopyTo(ms_out)
        
        # Convert to bytes
        dds_bytes = bytes(ms_out.ToArray())
        print(f"    s4pi converted RLE to DDS ({len(dds_bytes)} bytes)")
        return dds_bytes
    
    def _convert_rle_manual(self, rle_data: bytes) -> bytes:
        """
        Manual RLE to DDS conversion (fallback)
        
        RLE format header (16 bytes):
        - 4 bytes: FourCC (DXT5 = 0x35545844)
        - 4 bytes: Version (RLE2 = 0x32454C52, RLES = 0x53454C52)
        - 2 bytes: Width
        - 2 bytes: Height  
        - 2 bytes: MipCount
        - 2 bytes: Unknown (0)
        """
        try:
            import struct
            from io import BytesIO
            
            reader = BytesIO(rle_data)
            
            # Read RLE header
            fourcc = struct.unpack('<I', reader.read(4))[0]
            version = struct.unpack('<I', reader.read(4))[0]
            width = struct.unpack('<H', reader.read(2))[0]
            height = struct.unpack('<H', reader.read(2))[0]
            mip_count = struct.unpack('<H', reader.read(2))[0]
            unknown = struct.unpack('<H', reader.read(2))[0]
            
            print(f"    RLE: {width}x{height}, {mip_count} mips, version 0x{version:08X}")
            
            # Check if valid RLE
            RLE2_VERSION = 0x32454C52
            RLES_VERSION = 0x53454C52
            
            if version not in (RLE2_VERSION, RLES_VERSION):
                print(f"    Unknown RLE version: 0x{version:08X}")
                return None
            
            is_rles = (version == RLES_VERSION)
            header_size = 24 if is_rles else 20  # Per mip header size
            
            # Read mip headers
            mip_headers = []
            for i in range(mip_count):
                mip = {
                    'command_offset': struct.unpack('<I', reader.read(4))[0],
                    'offset2': struct.unpack('<I', reader.read(4))[0],
                    'offset3': struct.unpack('<I', reader.read(4))[0],
                    'offset0': struct.unpack('<I', reader.read(4))[0],
                    'offset1': struct.unpack('<I', reader.read(4))[0],
                }
                if is_rles:
                    mip['offset4'] = struct.unpack('<I', reader.read(4))[0]
                mip_headers.append(mip)
            
            # Calculate end offsets for last mip
            if mip_count > 0:
                last_mip = {
                    'command_offset': mip_headers[0]['offset2'],
                    'offset2': mip_headers[0]['offset3'],
                    'offset3': mip_headers[0]['offset0'],
                    'offset0': mip_headers[0]['offset1'],
                }
                if is_rles:
                    last_mip['offset1'] = mip_headers[0]['offset4']
                    last_mip['offset4'] = len(rle_data)
                else:
                    last_mip['offset1'] = len(rle_data)
                mip_headers.append(last_mip)
            
            # Build DDS output
            output = BytesIO()
            
            # DDS Signature
            output.write(struct.pack('<I', 0x20534444))  # "DDS "
            
            # DDS Header (124 bytes)
            output.write(struct.pack('<I', 124))  # Header size
            output.write(struct.pack('<I', 0x000A1007))  # Flags (CAPS|HEIGHT|WIDTH|PIXELFORMAT|MIPMAPCOUNT|LINEARSIZE)
            output.write(struct.pack('<I', height))
            output.write(struct.pack('<I', width))
            
            # Calculate pitch/linear size
            block_size = 16  # DXT5
            pitch = max(1, (width + 3) // 4) * block_size
            output.write(struct.pack('<I', pitch))
            
            output.write(struct.pack('<I', 1))  # Depth
            output.write(struct.pack('<I', mip_count))  # Mip count
            output.write(b'\x00' * 44)  # Reserved
            
            # Pixel format (32 bytes)
            output.write(struct.pack('<I', 32))  # Size
            output.write(struct.pack('<I', 0x04))  # Flags (FOURCC)
            output.write(b'DXT5')  # FourCC
            output.write(struct.pack('<I', 0))  # RGB bit count
            output.write(struct.pack('<I', 0))  # R mask
            output.write(struct.pack('<I', 0))  # G mask
            output.write(struct.pack('<I', 0))  # B mask
            output.write(struct.pack('<I', 0))  # A mask
            
            # Caps
            output.write(struct.pack('<I', 0x00401008))  # Caps1 (COMPLEX|MIPMAP|TEXTURE)
            output.write(struct.pack('<I', 0))  # Caps2
            output.write(b'\x00' * 12)  # Reserved
            
            # Decode RLE blocks
            full_transparent_alpha = bytes([0x00, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            full_opaque_alpha = bytes([0x00, 0x05, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
            
            for mip_idx in range(mip_count):
                mip = mip_headers[mip_idx]
                next_mip = mip_headers[mip_idx + 1]
                
                offset2 = mip['offset2']
                offset3 = mip['offset3']
                offset0 = mip['offset0']
                offset1 = mip['offset1']
                
                cmd_offset = mip['command_offset']
                while cmd_offset < next_mip['command_offset']:
                    command = struct.unpack('<H', rle_data[cmd_offset:cmd_offset+2])[0]
                    cmd_offset += 2
                    
                    op = command & 3
                    count = command >> 2
                    
                    if op == 0:  # Transparent
                        for _ in range(count):
                            output.write(full_transparent_alpha)
                            output.write(full_transparent_alpha)
                    elif op == 1:  # Translucent
                        for _ in range(count):
                            output.write(rle_data[offset0:offset0+2])
                            output.write(rle_data[offset1:offset1+6])
                            output.write(rle_data[offset2:offset2+4])
                            output.write(rle_data[offset3:offset3+4])
                            offset0 += 2
                            offset1 += 6
                            offset2 += 4
                            offset3 += 4
                    elif op == 2:  # Opaque
                        for _ in range(count):
                            output.write(full_opaque_alpha)
                            output.write(rle_data[offset2:offset2+4])
                            output.write(rle_data[offset3:offset3+4])
                            offset2 += 4
                            offset3 += 4
                    else:
                        print(f"    Unknown RLE op: {op}")
                        return None
            
            return output.getvalue()
            
        except Exception as e:
            print(f"    RLE conversion error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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


class SIMGEOM_OT_export_rle_textures(Operator, ImportHelper):
    """Export all RLE textures from a .package file as DDS"""
    bl_idname = "simgeom.export_rle_textures"
    bl_label = "Export RLE Textures to DDS"
    bl_options = {'REGISTER'}
    
    # ImportHelper for selecting the .package file
    filename_ext = ".package"
    filter_glob: StringProperty(default="*.package", options={'HIDDEN'})
    
    # Output directory
    output_directory: StringProperty(
        name="Output Folder",
        description="Folder to save extracted DDS textures",
        default="",
        subtype='DIR_PATH'
    )
    
    # Export options
    export_rle2: BoolProperty(
        name="Export RLE2 (Diffuse)",
        description="Export RLE2 format textures (typically diffuse maps)",
        default=True
    )
    
    export_rles: BoolProperty(
        name="Export RLES (Specular)",
        description="Export RLES format textures (typically specular maps)",
        default=True
    )
    
    export_dds: BoolProperty(
        name="Export DDS (Raw)",
        description="Export raw DDS textures (no conversion needed)",
        default=True
    )
    
    # Internal state - track whether we're ready to export
    _ready_to_export: bool = False
    _package_path: str = ""
    _rle2_count: int = 0
    _rles_count: int = 0
    _dds_count: int = 0
    
    def invoke(self, context, event):
        # Reset state
        self._ready_to_export = False
        # First, open file browser to select package
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        # If ready to export, do the export
        if self._ready_to_export:
            return self._do_export(context)
        
        # Load package and count textures
        package = PackageReader(self.filepath)
        if not package.load():
            self.report({'ERROR'}, "Failed to load package file")
            return {'CANCELLED'}
        
        rle_resources = package.get_rle_resources()
        dds_resources = package.get_dds_resources()
        
        rle2_textures = [t for t in rle_resources if t.resource_type == RLE2_TYPE]
        rles_textures = [t for t in rle_resources if t.resource_type == RLES_TYPE]
        
        total_textures = len(rle2_textures) + len(rles_textures) + len(dds_resources)
        
        if total_textures == 0:
            self.report({'WARNING'}, "No textures found in package")
            return {'CANCELLED'}
        
        # Store for dialog
        self._package_path = self.filepath
        self._rle2_count = len(rle2_textures)
        self._rles_count = len(rles_textures)
        self._dds_count = len(dds_resources)
        
        # Set default output directory to same folder as package
        if not self.output_directory:
            self.output_directory = os.path.dirname(self.filepath)
        
        # Mark ready for export on next execute call
        self._ready_to_export = True
        
        # Show confirmation dialog
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        
        # Show texture counts
        box = layout.box()
        box.label(text="Textures Found:", icon='TEXTURE')
        col = box.column(align=True)
        col.label(text=f"  RLE2 (Diffuse): {self._rle2_count}")
        col.label(text=f"  RLES (Specular): {self._rles_count}")
        col.label(text=f"  DDS (Raw): {self._dds_count}")
        col.label(text=f"  Total: {self._rle2_count + self._rles_count + self._dds_count}")
        
        layout.separator()
        
        # Export options
        box = layout.box()
        box.label(text="Export Options:", icon='EXPORT')
        col = box.column(align=True)
        col.prop(self, "export_rle2")
        col.prop(self, "export_rles")
        col.prop(self, "export_dds")
        
        layout.separator()
        
        # Output folder
        layout.prop(self, "output_directory")
    
    def check(self, context):
        # Allow property updates
        return True
    
    def cancel(self, context):
        self._ready_to_export = False
    
    def _do_export(self, context):
        """Perform the actual texture export"""
        if not self.output_directory:
            self.report({'ERROR'}, "Please select an output folder")
            return {'CANCELLED'}
        
        # Create output directory if needed
        output_dir = bpy.path.abspath(self.output_directory)
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to create output folder: {e}")
                return {'CANCELLED'}
        
        # Load package
        package = PackageReader(self._package_path)
        if not package.load():
            self.report({'ERROR'}, "Failed to reload package file")
            return {'CANCELLED'}
        
        rle_resources = package.get_rle_resources()
        dds_resources = package.get_dds_resources()
        
        exported_count = 0
        failed_count = 0
        
        # Export RLE2 textures
        if self.export_rle2:
            rle2_textures = [t for t in rle_resources if t.resource_type == RLE2_TYPE]
            for tex in rle2_textures:
                success = self._export_rle_texture(package, tex, output_dir, "diffuse")
                if success:
                    exported_count += 1
                else:
                    failed_count += 1
        
        # Export RLES textures
        if self.export_rles:
            rles_textures = [t for t in rle_resources if t.resource_type == RLES_TYPE]
            for tex in rles_textures:
                success = self._export_rle_texture(package, tex, output_dir, "specular")
                if success:
                    exported_count += 1
                else:
                    failed_count += 1
        
        # Export raw DDS textures
        if self.export_dds:
            for tex in dds_resources:
                success = self._export_dds_texture(package, tex, output_dir)
                if success:
                    exported_count += 1
                else:
                    failed_count += 1
        
        # Report results
        if failed_count > 0:
            self.report({'WARNING'}, f"Exported {exported_count} textures, {failed_count} failed")
        else:
            self.report({'INFO'}, f"Successfully exported {exported_count} textures to {output_dir}")
        
        return {'FINISHED'}
    
    def _export_rle_texture(self, package, tex_entry, output_dir: str, prefix: str) -> bool:
        """Export a single RLE texture as DDS"""
        try:
            rle_data = package.get_resource_data(tex_entry)
            if not rle_data:
                print(f"  Failed to get data for {tex_entry.instance_hex}")
                return False
            
            # Convert RLE to DDS
            dds_data = self._convert_rle_to_dds(rle_data)
            if not dds_data:
                print(f"  Failed to convert {tex_entry.instance_hex}")
                return False
            
            # Save to file
            filename = f"{prefix}_{tex_entry.instance:016X}.dds"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(dds_data)
            
            print(f"  Exported: {filename} ({len(dds_data)} bytes)")
            return True
            
        except Exception as e:
            print(f"  Error exporting {tex_entry.instance_hex}: {e}")
            return False
    
    def _export_dds_texture(self, package, tex_entry, output_dir: str) -> bool:
        """Export a raw DDS texture"""
        try:
            dds_data = package.get_resource_data(tex_entry)
            if not dds_data:
                print(f"  Failed to get data for {tex_entry.instance_hex}")
                return False
            
            filename = f"texture_{tex_entry.instance:016X}.dds"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(dds_data)
            
            print(f"  Exported: {filename} ({len(dds_data)} bytes)")
            return True
            
        except Exception as e:
            print(f"  Error exporting {tex_entry.instance_hex}: {e}")
            return False
    
    def _convert_rle_to_dds(self, rle_data: bytes) -> bytes:
        """Convert RLE texture to DDS format"""
        if not rle_data or len(rle_data) < 16:
            return None
        
        # Try s4pi first
        if _init_s4pi():
            try:
                import clr
                from System.IO import MemoryStream
                
                ms_in = MemoryStream(rle_data)
                rle_res = _RLEResource(0, ms_in)
                ms_out = MemoryStream()
                rle_res.ToDDS().CopyTo(ms_out)
                return bytes(ms_out.ToArray())
            except Exception as e:
                print(f"    s4pi failed: {e}")
        
        # Fall back to manual conversion
        return self._convert_rle_manual(rle_data)
    
    def _convert_rle_manual(self, rle_data: bytes) -> bytes:
        """Manual RLE to DDS conversion"""
        try:
            import struct
            from io import BytesIO
            
            reader = BytesIO(rle_data)
            
            fourcc = struct.unpack('<I', reader.read(4))[0]
            version = struct.unpack('<I', reader.read(4))[0]
            width = struct.unpack('<H', reader.read(2))[0]
            height = struct.unpack('<H', reader.read(2))[0]
            mip_count = struct.unpack('<H', reader.read(2))[0]
            unknown = struct.unpack('<H', reader.read(2))[0]
            
            RLE2_VERSION = 0x32454C52
            RLES_VERSION = 0x53454C52
            
            if version not in (RLE2_VERSION, RLES_VERSION):
                return None
            
            is_rles = (version == RLES_VERSION)
            
            # Read mip headers
            mip_headers = []
            for i in range(mip_count):
                mip = {
                    'command_offset': struct.unpack('<I', reader.read(4))[0],
                    'offset2': struct.unpack('<I', reader.read(4))[0],
                    'offset3': struct.unpack('<I', reader.read(4))[0],
                    'offset0': struct.unpack('<I', reader.read(4))[0],
                    'offset1': struct.unpack('<I', reader.read(4))[0],
                }
                if is_rles:
                    mip['offset4'] = struct.unpack('<I', reader.read(4))[0]
                mip_headers.append(mip)
            
            if mip_count > 0:
                last_mip = {
                    'command_offset': mip_headers[0]['offset2'],
                    'offset2': mip_headers[0]['offset3'],
                    'offset3': mip_headers[0]['offset0'],
                    'offset0': mip_headers[0]['offset1'],
                }
                if is_rles:
                    last_mip['offset1'] = mip_headers[0]['offset4']
                    last_mip['offset4'] = len(rle_data)
                else:
                    last_mip['offset1'] = len(rle_data)
                mip_headers.append(last_mip)
            
            output = BytesIO()
            
            # DDS Header
            output.write(struct.pack('<I', 0x20534444))
            output.write(struct.pack('<I', 124))
            output.write(struct.pack('<I', 0x000A1007))
            output.write(struct.pack('<I', height))
            output.write(struct.pack('<I', width))
            
            block_size = 16
            pitch = max(1, (width + 3) // 4) * block_size
            output.write(struct.pack('<I', pitch))
            
            output.write(struct.pack('<I', 1))
            output.write(struct.pack('<I', mip_count))
            output.write(b'\x00' * 44)
            
            output.write(struct.pack('<I', 32))
            output.write(struct.pack('<I', 0x04))
            output.write(b'DXT5')
            output.write(struct.pack('<I', 0))
            output.write(struct.pack('<I', 0))
            output.write(struct.pack('<I', 0))
            output.write(struct.pack('<I', 0))
            output.write(struct.pack('<I', 0))
            
            output.write(struct.pack('<I', 0x00401008))
            output.write(struct.pack('<I', 0))
            output.write(b'\x00' * 12)
            
            full_transparent_alpha = bytes([0x00, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            full_opaque_alpha = bytes([0x00, 0x05, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
            
            for mip_idx in range(mip_count):
                mip = mip_headers[mip_idx]
                next_mip = mip_headers[mip_idx + 1]
                
                offset2 = mip['offset2']
                offset3 = mip['offset3']
                offset0 = mip['offset0']
                offset1 = mip['offset1']
                
                cmd_offset = mip['command_offset']
                while cmd_offset < next_mip['command_offset']:
                    command = struct.unpack('<H', rle_data[cmd_offset:cmd_offset+2])[0]
                    cmd_offset += 2
                    
                    op = command & 3
                    count = command >> 2
                    
                    if op == 0:
                        for _ in range(count):
                            output.write(full_transparent_alpha)
                            output.write(full_transparent_alpha)
                    elif op == 1:
                        for _ in range(count):
                            output.write(rle_data[offset0:offset0+2])
                            output.write(rle_data[offset1:offset1+6])
                            output.write(rle_data[offset2:offset2+4])
                            output.write(rle_data[offset3:offset3+4])
                            offset0 += 2
                            offset1 += 6
                            offset2 += 4
                            offset3 += 4
                    elif op == 2:
                        for _ in range(count):
                            output.write(full_opaque_alpha)
                            output.write(rle_data[offset2:offset2+4])
                            output.write(rle_data[offset3:offset3+4])
                            offset2 += 4
                            offset3 += 4
                    else:
                        return None
            
            return output.getvalue()
            
        except Exception as e:
            print(f"    RLE conversion error: {e}")
            return None
