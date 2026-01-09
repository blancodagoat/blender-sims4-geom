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

import bpy
from io_simgeom.util.globals      import Globals


# Sims 4 rigs enum (defined once, used by panels)
def register_rig_enum():
    bpy.types.Scene.simgeom_rig_type = bpy.props.EnumProperty(
        name = "Choose Rig:",
        description = "Rig to import alongside the mesh",
        items = [
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
        default = 'yfRig'
    )


class SIMGEOM_PT_sidebar_panel(bpy.types.Panel):
    """Sims 4 GEOM Tools - N-Panel in 3D View"""
    bl_label = "Sims 4 GEOM"
    bl_idname = "SIMGEOM_PT_sidebar_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sims 4"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object

        # Update notification
        if Globals.OUTDATED == 1:
            box = layout.box()
            box.alert = True
            col = box.column(align=True)
            col.label(text="Update Available!", icon='INFO')
            current = '.'.join(map(str, Globals.CURRENT_VERSION))
            latest = Globals.LATEST_VERSION_STR or '.'.join(map(str, Globals.LATEST_VERSION))
            col.label(text=f"v{current} -> {latest}")
            col.operator("wm.url_open", text="Download Update", icon='IMPORT').url = Globals.UPDATE_URL
        elif Globals.OUTDATED == -1:
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Update check failed", icon='ERROR')
            col.operator("simgeom.check_updates", text="Retry", icon='FILE_REFRESH')

        # Import Section
        box = layout.box()
        box.label(text="Import", icon='IMPORT')
        col = box.column(align=True)
        col.operator("simgeom.import_package", text="Package (.package)", icon='PACKAGE')
        col.separator()
        col.operator("simgeom.import_geom", text="GEOM (.simgeom)", icon='MESH_DATA')
        col.operator("simgeom.import_morph", text="Morph (.simgeom)", icon='MOD_SIMPLEDEFORM')
        col.separator()
        row = col.row(align=True)
        row.operator("simgeom.import_rig_helper", text="Rig", icon='ARMATURE_DATA')
        row.prop(scene, "simgeom_rig_type", text="")

        # Export Section
        box = layout.box()
        box.label(text="Export", icon='EXPORT')
        col = box.column(align=True)
        col.operator("simgeom.export_geom", text="GEOM (.simgeom)", icon='MESH_DATA')
        col.operator("simgeom.batch_export_geom", text="Batch Export GEOMs", icon='EXPORT')
        col.separator()
        col.operator("simgeom.export_rle_textures", text="Textures (RLE to DDS)", icon='TEXTURE')

        # Tools Section (context-sensitive)
        if obj is not None:
            if obj.type == 'ARMATURE' and obj.get('__S4_RIG__', 0):
                box = layout.box()
                box.label(text="Rig Tools", icon='TOOL_SETTINGS')
                box.operator("simgeom.rebuild_bone_database", icon='FILE_REFRESH')

            if obj.get('__S4_GEOM__', 0):
                box = layout.box()
                box.label(text="GEOM Tools", icon='TOOL_SETTINGS')
                col = box.column(align=True)
                col.operator("simgeom.generate_lods", text="Generate LODs", icon='MOD_DECIM')
                col.operator("simgeom.rename_bone_groups", icon='GROUP_BONE')
                col.operator("simgeom.copy_data", text="Transfer GEOM Data", icon='PASTEFLIPDOWN')
                col.operator("simgeom.make_morph", icon='MOD_SIMPLEDEFORM')
                
                # Texture reload (only if imported from package)
                if obj.get('package_path'):
                    col.separator()
                    col.operator("simgeom.reload_textures", icon='FILE_REFRESH')

            if obj.get('__S4_GEOM_MORPH__', 0):
                box = layout.box()
                box.label(text="Morph Data", icon='MOD_SIMPLEDEFORM')
                col = box.column(align=True)
                col.prop(obj, "morph_name")
                col.prop(obj, "morph_link")


class SIMGEOM_PT_sidebar_textures(bpy.types.Panel):
    """Texture preview sub-panel"""
    bl_label = "Textures"
    bl_idname = "SIMGEOM_PT_sidebar_textures"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sims 4"
    bl_parent_id = "SIMGEOM_PT_sidebar_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH' and 
                obj.data.materials and len(obj.data.materials) > 0)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object        

        # Count textures across all materials
        textures = []
        for mat in obj.data.materials:
            if not mat or not mat.use_nodes:
                continue
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    textures.append((node.label or node.image.name, node.image, mat.name))
        
        if not textures:
            layout.label(text="No textures found", icon='INFO')
            return
        
        layout.label(text=f"{len(textures)} texture(s) loaded")
        
        # Show texture thumbnails
        for label, img, mat_name in textures:
            box = layout.box()
            row = box.row()
            
            # Thumbnail preview
            row.template_icon(icon_value=img.preview.icon_id if img.preview else 0, scale=3)
            
            col = row.column(align=True)
            col.label(text=label[:20] if len(label) > 20 else label)
            col.label(text=f"{img.size[0]}x{img.size[1]}", icon='TEXTURE')
            col.label(text=mat_name[:15], icon='MATERIAL')
        
        # Source package info
        package_path = obj.get('package_path')
        if package_path:
            layout.separator()
            box = layout.box()
            box.label(text="Source Package:", icon='PACKAGE')
            import os
            box.label(text=os.path.basename(package_path)[:30])


class SIMGEOM_PT_sidebar_vertex_ids(bpy.types.Panel):
    """Vertex ID sub-panel"""
    bl_label = "Vertex IDs"
    bl_idname = "SIMGEOM_PT_sidebar_vertex_ids"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sims 4"
    bl_parent_id = "SIMGEOM_PT_sidebar_panel"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.get('__S4_GEOM__', 0)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object 

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(obj, '["start_id"]', text="Start ID")
        
        vert_ids = obj.get('vert_ids')
        if vert_ids:
            uniques = len(vert_ids)
            end_id = obj.get('start_id', 0) + uniques
            col.label(text=f"End ID: {end_id} ({uniques} unique)")
        
        col.separator()
        col.operator("simgeom.recalc_ids", text="Recalculate IDs", icon='FILE_REFRESH')
        col.operator("simgeom.remove_ids", text="Remove IDs", icon='X')
        
        col.separator()
        row = col.row(align=True)
        row.prop(context.scene, 'v_id_margin')
        row.operator("simgeom.reset_id_margin", text="", icon='LOOP_BACK')


class SIMGEOM_PT_utility_panel(bpy.types.Panel):
    """Creates a Panel in the Object properties window (legacy)"""
    bl_label = "Sims 4 GEOM Tools"
    bl_idname = "SIMGEOM_PT_utility_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Use the Sims 4 tab in the N-Panel (3D View)")
        layout.label(text="Press N in 3D View to open sidebar")
        
        layout.separator()
        
        # Version info
        current = '.'.join(map(str, Globals.CURRENT_VERSION)) if Globals.CURRENT_VERSION else "?"
        layout.label(text=f"Version: v{current}")
        layout.operator("simgeom.check_updates", icon='URL')
    

