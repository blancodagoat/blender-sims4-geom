# Converters between Sims 4 GEOM and GTA V YDR formats

import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix
from typing import Optional, List, Tuple, Dict, Any

def is_sollumz_available():
    """Get current Sollumz availability"""
    from . import SOLLUMZ_AVAILABLE
    return SOLLUMZ_AVAILABLE


def copy_mesh_data(source_obj: bpy.types.Object) -> Dict[str, Any]:
    """
    Extract mesh data from a Blender object in a format-agnostic way.
    This can be used as intermediate data for conversion.
    """
    if source_obj.type != 'MESH':
        raise ValueError(f"Object {source_obj.name} is not a mesh")
    
    mesh = source_obj.data
    
    # Ensure mesh is up to date
    mesh.calc_loop_triangles()
    
    data = {
        'name': source_obj.name,
        'vertices': [],
        'normals': [],
        'uvs': {},  # UV layer name -> list of UVs per vertex
        'colors': {},  # Color layer name -> list of colors per vertex
        'faces': [],
        'materials': [],
        'vertex_groups': {},  # Group name -> list of (vertex_index, weight)
        'custom_properties': dict(source_obj.items()),
    }
    
    # Vertices and normals
    for vert in mesh.vertices:
        data['vertices'].append(tuple(vert.co))
        data['normals'].append(tuple(vert.normal))
    
    # UV layers
    for uv_layer in mesh.uv_layers:
        uvs = []
        for loop in mesh.loops:
            uv = uv_layer.data[loop.index].uv
            uvs.append((uv[0], uv[1]))
        data['uvs'][uv_layer.name] = uvs
    
    # Vertex colors
    for color_layer in mesh.color_attributes:
        colors = []
        if color_layer.domain == 'POINT':
            for i in range(len(mesh.vertices)):
                color = color_layer.data[i].color
                colors.append(tuple(color))
        elif color_layer.domain == 'CORNER':
            for loop in mesh.loops:
                color = color_layer.data[loop.index].color
                colors.append(tuple(color))
        data['colors'][color_layer.name] = colors
    
    # Faces (triangulated)
    for tri in mesh.loop_triangles:
        data['faces'].append(tuple(tri.vertices))
    
    # Materials
    for mat in mesh.materials:
        if mat:
            data['materials'].append(mat.name)
        else:
            data['materials'].append(None)
    
    # Vertex groups (bone weights)
    for group in source_obj.vertex_groups:
        weights = []
        for vert in mesh.vertices:
            try:
                weight = group.weight(vert.index)
                if weight > 0:
                    weights.append((vert.index, weight))
            except RuntimeError:
                pass
        data['vertex_groups'][group.name] = weights
    
    return data


def geom_to_sollumz(geom_obj: bpy.types.Object) -> Optional[bpy.types.Object]:
    """
    Convert a Sims 4 GEOM mesh to Sollumz drawable geometry format.
    
    Args:
        geom_obj: A Blender mesh object imported from Sims 4 GEOM
        
    Returns:
        A new object configured as Sollumz drawable geometry, or None if conversion fails
    """
    if not is_sollumz_available():
        print("Sollumz not available - cannot convert")
        return None
    
    # Get SollumType enum from Sollumz module
    from . import get_sollumz_module
    sollumz_props = get_sollumz_module()
    if sollumz_props is None:
        print("Could not find Sollumz properties module")
        return None
    
    SollumType = getattr(sollumz_props, 'SollumType', None)
    if SollumType is None:
        print("Could not find SollumType in Sollumz properties")
        return None
    
    # Create a copy of the mesh
    new_mesh = geom_obj.data.copy()
    new_mesh.name = f"{geom_obj.name}_ydr"
    
    new_obj = bpy.data.objects.new(f"{geom_obj.name}_drawable", new_mesh)
    bpy.context.collection.objects.link(new_obj)
    
    # Set Sollumz type
    new_obj.sollum_type = SollumType.DRAWABLE_GEOMETRY
    
    # Copy transform
    new_obj.matrix_world = geom_obj.matrix_world.copy()
    
    # Handle UV mapping differences
    # Sims 4 uses flipped V coordinates, GTA V uses standard
    mesh = new_obj.data
    for uv_layer in mesh.uv_layers:
        for loop_idx in range(len(mesh.loops)):
            uv = uv_layer.data[loop_idx].uv
            # V coordinate may need flipping depending on source
            # uv_layer.data[loop_idx].uv = (uv[0], 1.0 - uv[1])
    
    # Rename UV layers to Sollumz convention
    if mesh.uv_layers:
        for i, uv_layer in enumerate(mesh.uv_layers):
            uv_layer.name = f"UVMap {i}"
    
    # Copy vertex colors
    # Sollumz uses "Colour0", "Colour1" naming
    for i, color_attr in enumerate(mesh.color_attributes):
        color_attr.name = f"Colour{i}"
    
    # Copy materials (will need shader conversion)
    # For now, just keep the existing materials
    
    # Copy vertex groups (bone weights)
    for group in geom_obj.vertex_groups:
        new_group = new_obj.vertex_groups.new(name=group.name)
        for vert in mesh.vertices:
            try:
                weight = group.weight(vert.index)
                if weight > 0:
                    new_group.add([vert.index], weight, 'REPLACE')
            except RuntimeError:
                pass
    
    # Store original GEOM data as custom properties
    if 'geom_instance' in geom_obj:
        new_obj['original_geom_instance'] = geom_obj['geom_instance']
    if 'package_path' in geom_obj:
        new_obj['original_package'] = geom_obj['package_path']
    
    print(f"Converted {geom_obj.name} to Sollumz drawable geometry: {new_obj.name}")
    return new_obj


def sollumz_to_geom(sollumz_obj: bpy.types.Object) -> Optional[bpy.types.Object]:
    """
    Convert a Sollumz drawable geometry to Sims 4 GEOM compatible mesh.
    
    Args:
        sollumz_obj: A Blender mesh object with Sollumz drawable geometry type
        
    Returns:
        A new object configured for Sims 4 GEOM export, or None if conversion fails
    """
    if sollumz_obj.type != 'MESH':
        print(f"Object {sollumz_obj.name} is not a mesh")
        return None
    
    # Create a copy of the mesh
    new_mesh = sollumz_obj.data.copy()
    new_mesh.name = f"{sollumz_obj.name}_geom"
    
    new_obj = bpy.data.objects.new(f"{sollumz_obj.name}_simgeom", new_mesh)
    bpy.context.collection.objects.link(new_obj)
    
    # Copy transform
    new_obj.matrix_world = sollumz_obj.matrix_world.copy()
    
    mesh = new_obj.data
    
    # Handle UV mapping - Sims 4 uses flipped V
    for uv_layer in mesh.uv_layers:
        for loop_idx in range(len(mesh.loops)):
            uv = uv_layer.data[loop_idx].uv
            uv_layer.data[loop_idx].uv = (uv[0], 1.0 - uv[1])
    
    # Rename UV layers to GEOM convention
    for i, uv_layer in enumerate(mesh.uv_layers):
        uv_layer.name = f"uv_{i}"
    
    # Rename color attributes
    for i, color_attr in enumerate(mesh.color_attributes):
        color_attr.name = f"color_{i}"
    
    # Copy vertex groups
    for group in sollumz_obj.vertex_groups:
        new_group = new_obj.vertex_groups.new(name=group.name)
        for vert in mesh.vertices:
            try:
                weight = group.weight(vert.index)
                if weight > 0:
                    new_group.add([vert.index], weight, 'REPLACE')
            except RuntimeError:
                pass
    
    # Mark as GEOM compatible
    new_obj['simgeom_converted'] = True
    new_obj['source_type'] = 'sollumz'
    
    # Store original Sollumz data
    if hasattr(sollumz_obj, 'sollum_type'):
        new_obj['original_sollum_type'] = str(sollumz_obj.sollum_type)
    
    print(f"Converted {sollumz_obj.name} to GEOM format: {new_obj.name}")
    return new_obj


def copy_materials_geom_to_sollumz(
    source_obj: bpy.types.Object,
    target_obj: bpy.types.Object
) -> int:
    """
    Copy and convert materials from a GEOM object to a Sollumz object.
    Attempts to create equivalent Sollumz shader materials.
    
    Returns the number of materials converted.
    """
    if not is_sollumz_available():
        return 0
    
    count = 0
    source_mesh = source_obj.data
    target_mesh = target_obj.data
    
    # Clear target materials
    target_mesh.materials.clear()
    
    for mat in source_mesh.materials:
        if mat is None:
            target_mesh.materials.append(None)
            continue
        
        # Create a new Sollumz-compatible material
        new_mat = mat.copy()
        new_mat.name = f"{mat.name}_sollumz"
        
        # Try to set Sollumz material type
        try:
            from . import get_sollumz_module
            sollumz_props = get_sollumz_module()
            if sollumz_props:
                MaterialType = getattr(sollumz_props, 'MaterialType', None)
                if MaterialType:
                    new_mat.sollum_type = MaterialType.SHADER
        except:
            pass
        
        target_mesh.materials.append(new_mat)
        count += 1
    
    return count


def copy_materials_sollumz_to_geom(
    source_obj: bpy.types.Object,
    target_obj: bpy.types.Object
) -> int:
    """
    Copy and convert materials from a Sollumz object to a GEOM object.
    Creates standard PBR materials compatible with Sims 4.
    
    Returns the number of materials converted.
    """
    count = 0
    source_mesh = source_obj.data
    target_mesh = target_obj.data
    
    # Clear target materials
    target_mesh.materials.clear()
    
    for mat in source_mesh.materials:
        if mat is None:
            target_mesh.materials.append(None)
            continue
        
        # Create a simplified copy for GEOM
        new_mat = bpy.data.materials.new(name=f"{mat.name}_geom")
        new_mat.use_nodes = True
        
        # Try to copy textures from Sollumz material
        if mat.use_nodes:
            _copy_texture_nodes(mat, new_mat)
        
        target_mesh.materials.append(new_mat)
        count += 1
    
    return count


def _copy_texture_nodes(source_mat: bpy.types.Material, target_mat: bpy.types.Material):
    """Copy texture image nodes from source to target material"""
    source_tree = source_mat.node_tree
    target_tree = target_mat.node_tree
    
    # Find texture nodes in source
    tex_nodes = [n for n in source_tree.nodes if n.type == 'TEX_IMAGE']
    
    if not tex_nodes:
        return
    
    # Get the principled BSDF in target
    bsdf = None
    for node in target_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            bsdf = node
            break
    
    if not bsdf:
        return
    
    # Copy diffuse texture
    for tex_node in tex_nodes:
        if tex_node.image:
            # Check if it's a diffuse texture by name or link
            is_diffuse = 'diffuse' in tex_node.label.lower() or 'diffuse' in tex_node.name.lower()
            is_connected_to_base = False
            
            for link in tex_node.outputs['Color'].links:
                if link.to_node.type == 'BSDF_PRINCIPLED':
                    if 'Base Color' in link.to_socket.name:
                        is_diffuse = True
                        is_connected_to_base = True
                        break
            
            if is_diffuse or not is_connected_to_base:
                # Create texture node in target
                new_tex = target_tree.nodes.new('ShaderNodeTexImage')
                new_tex.image = tex_node.image
                new_tex.location = (-300, 300)
                
                # Link to BSDF
                target_tree.links.new(new_tex.outputs['Color'], bsdf.inputs['Base Color'])
                target_tree.links.new(new_tex.outputs['Alpha'], bsdf.inputs['Alpha'])
                
                # Only copy one diffuse
                break
